import logging
import threading
from django.db import IntegrityError, connection as _db_conn
from django.db.models import F, Q
from django.utils.dateparse import parse_datetime
from ..models import (
    WhatsAppAccount, WhatsAppContact, WhatsAppChat,
    WhatsAppMessage, ChatType, SyncLog,
)

logger = logging.getLogger(__name__)


def _embed_in_background(message_ids: list, sync_log_id: int = None):
    """Fire-and-forget embedding in a daemon thread — never blocks the HTTP response.

    After embedding completes, patches the SyncLog entry (if sync_log_id provided)
    with { embedded: N, embed_errors: N } so the activity log reflects the result.
    """
    if not message_ids:
        return

    def _run():
        embedded = errors = 0
        try:
            if len(message_ids) == 1:
                from apps.message_intelligence.services.embedding_service import embed_message
                ok = embed_message(message_ids[0])
                embedded, errors = (1, 0) if ok else (0, 1)
            else:
                from apps.message_intelligence.services.embedding_service import embed_messages_batch
                result = embed_messages_batch(message_ids)
                embedded = result['embedded']
                errors = result['errors']
        except Exception:
            logger.warning('Background embedding failed for %d message(s)', len(message_ids), exc_info=True)
            errors = len(message_ids)
        finally:
            if sync_log_id:
                try:
                    log = SyncLog.objects.get(pk=sync_log_id)
                    meta = log.metadata or {}
                    meta['embedded'] = embedded
                    meta['embed_errors'] = errors
                    log.metadata = meta
                    log.save(update_fields=['metadata'])
                except Exception:
                    logger.debug('Could not update SyncLog %s with embedding result', sync_log_id)
            _db_conn.close()

    threading.Thread(target=_run, daemon=True).start()


class IngestionService:

    def ingest_message(self, payload: dict) -> WhatsAppMessage:
        worker_session_id = payload['worker_session_id']
        account = WhatsAppAccount.objects.get(pk=worker_session_id)

        contact = self._upsert_contact(account, payload)
        chat = self._upsert_chat(account, contact, payload)
        message, created = self._insert_message(account, chat, contact, payload)

        if created:
            if payload.get('direction') == 'inbound':
                WhatsAppChat.objects.filter(pk=chat.pk).update(unread_count=F('unread_count') + 1)

            _meta = {
                'provider_message_id': payload.get('provider_message_id'),
                'chat_id': payload.get('chat_id'),
                'sender_jid': payload.get('sender_number') or None,
                'push_name': payload.get('push_name') or None,
                'message_type': payload.get('message_type'),
                'message_text': (payload.get('message_text') or '')[:200] or None,
                'direction': payload.get('direction'),
                'group_name': payload.get('group_name') or None,
                'raw_payload': payload.get('raw_payload') or None,
            }
            sync_log = SyncLog.objects.create(
                account=account,
                event_type='message_ingest',
                status='success',
                metadata={k: v for k, v in _meta.items() if v is not None},
            )

            if message.message_text:
                _embed_in_background([message.pk], sync_log_id=sync_log.pk)

        return message

    def ingest_batch(self, payloads: list) -> dict:
        """Process a list of messages (from history sync) in one call.

        Skips per-message SyncLog and unread_count updates — history messages are
        already-read messages from the user's phone. Creates one batch SyncLog entry.
        """
        if not payloads:
            return {'total': 0, 'created': 0, 'skipped': 0, 'errors': 0}

        worker_session_id = payloads[0].get('worker_session_id')
        account = WhatsAppAccount.objects.get(pk=worker_session_id)

        created_count = 0
        skipped_count = 0
        error_count = 0

        new_message_ids = []
        for payload in payloads:
            try:
                contact = self._upsert_contact(account, payload)
                chat = self._upsert_chat(account, contact, payload)
                message, created = self._insert_message(account, chat, contact, payload)
                if created:
                    created_count += 1
                    if message.message_text:
                        new_message_ids.append(message.pk)
                else:
                    skipped_count += 1
            except Exception as e:
                error_count += 1
                logger.error(
                    'Batch ingest error for msg %s: %s',
                    payload.get('provider_message_id'), e,
                )

        sync_log = SyncLog.objects.create(
            account=account,
            event_type='history_sync',
            status='success' if not error_count else 'warning',
            metadata={
                'total': len(payloads),
                'created': created_count,
                'skipped': skipped_count,
                'errors': error_count,
            },
        )

        if new_message_ids:
            _embed_in_background(new_message_ids, sync_log_id=sync_log.pk)

        return {
            'total': len(payloads),
            'created': created_count,
            'skipped': skipped_count,
            'errors': error_count,
        }

    def _upsert_contact(self, account: WhatsAppAccount, payload: dict) -> WhatsAppContact:
        sender_number = payload.get('sender_number', '')
        chat_type = payload.get('chat_type', ChatType.INDIVIDUAL)
        push_name = payload.get('push_name', '')
        direction = payload.get('direction', 'inbound')

        # For individual chats the contact JID is the chat JID.
        # For group messages the contact JID is the sender's phone JID.
        if chat_type == ChatType.INDIVIDUAL:
            wa_contact_id = payload.get('chat_id', sender_number)
        else:
            wa_contact_id = f"{sender_number}@s.whatsapp.net" if sender_number else payload.get('chat_id', '')

        # The worker must always resolve LID → phone JID before forwarding.
        # A LID reaching ingestion means the pipeline is broken upstream.
        if wa_contact_id.endswith('@lid'):
            raise ValueError(
                f'Unresolved LID {wa_contact_id!r} reached ingestion for account {account.pk}. '
                'Worker must resolve LID to phone JID before forwarding.'
            )

        defaults = {'phone_number': sender_number}
        if push_name and direction == 'inbound':
            defaults['push_name'] = push_name

        try:
            contact, _ = WhatsAppContact.objects.update_or_create(
                account=account,
                wa_contact_id=wa_contact_id,
                defaults=defaults,
                # display_name seeded only on creation so users can customise it without
                # it being overwritten on every inbound message.
                create_defaults={'display_name': push_name} if push_name else {},
            )
        except IntegrityError:
            # Race condition: contacts-update and message-ingest run concurrently and both
            # attempt to create the same WhatsAppContact. The loser gets an IntegrityError
            # on the unique_together(account, wa_contact_id) constraint. Fall back to a
            # plain update so the ingestion proceeds without losing the message.
            WhatsAppContact.objects.filter(
                account=account, wa_contact_id=wa_contact_id,
            ).update(**defaults)
            contact = WhatsAppContact.objects.get(account=account, wa_contact_id=wa_contact_id)
        return contact

    def _upsert_chat(
        self, account: WhatsAppAccount, contact: WhatsAppContact, payload: dict
    ) -> WhatsAppChat:
        wa_chat_id = payload['chat_id']
        chat_type = payload.get('chat_type', ChatType.INDIVIDUAL)
        message_time = parse_datetime(payload['message_time'])

        defaults = {
            'chat_type': chat_type,
            'contact': contact if chat_type == ChatType.INDIVIDUAL else None,
        }
        group_name = payload.get('group_name', '')
        if group_name:
            defaults['name'] = group_name

        try:
            chat, created = WhatsAppChat.objects.update_or_create(
                account=account,
                wa_chat_id=wa_chat_id,
                defaults=defaults,
                create_defaults={'last_message_at': message_time},
            )
        except IntegrityError:
            # Race between concurrent message-ingest requests for the same chat
            # (e.g. history sync overlapping with a live message). Fall back to GET + UPDATE.
            chat = WhatsAppChat.objects.get(account=account, wa_chat_id=wa_chat_id)
            WhatsAppChat.objects.filter(pk=chat.pk).update(**defaults)
            chat.refresh_from_db()
            created = False

        # Only advance last_message_at — never let an older replayed message push it back.
        # History sync delivers messages out of chronological order, so without this guard
        # the chat sinks in the rail as stale timestamps overwrite fresh ones.
        if not created:
            WhatsAppChat.objects.filter(
                pk=chat.pk
            ).filter(
                Q(last_message_at__isnull=True) | Q(last_message_at__lt=message_time)
            ).update(last_message_at=message_time)
            chat.refresh_from_db(fields=['last_message_at'])

        return chat

    def _insert_message(
        self,
        account: WhatsAppAccount,
        chat: WhatsAppChat,
        contact: WhatsAppContact,
        payload: dict,
    ) -> WhatsAppMessage:
        message_time = parse_datetime(payload['message_time'])

        message, created = WhatsAppMessage.objects.get_or_create(
            account=account,
            provider_message_id=payload['provider_message_id'],
            defaults={
                'chat': chat,
                'contact': contact,
                'sender_number': payload.get('sender_number', ''),
                'direction': payload['direction'],
                'message_type': payload.get('message_type', 'text'),
                'message_text': payload.get('message_text', ''),
                'message_time': message_time,
                'has_media': payload.get('has_media', False),
                'media_mime_type': payload.get('media_mime_type', ''),
                'media_file_name': payload.get('media_file_name', ''),
                'media_url': payload.get('media_url') or '',
                'raw_payload': payload.get('raw_payload'),
            },
        )
        # Backfill empty fields if the existing record was stored without them
        update_fields = []
        if not created and not message.message_text and payload.get('message_text'):
            message.message_text = payload['message_text']
            message.message_type = payload.get('message_type', message.message_type)
            update_fields += ['message_text', 'message_type']
        if not created and not message.media_url and payload.get('media_url'):
            message.media_url = payload['media_url']
            update_fields.append('media_url')
        if update_fields:
            message.save(update_fields=update_fields)
        return message, created
