import logging
import threading
from django.db import IntegrityError, connection as _db_conn
from django.db.models import F, Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from ..models import (
    WhatsAppAccount, WhatsAppContact, WhatsAppChat,
    WhatsAppMessage, ChatType, SyncLog, DroppedMessage, WorkerAlert,
    WhatsAppUnresolvedMessage, ResolutionStatus,
)


def _resolve_dropped_message(account: WhatsAppAccount, msg_id: str) -> None:
    """Mark any earlier drop for this msg_id as recovered.

    A message can arrive as decryptable content after previously showing up
    empty (Baileys retry-requested a resend and the sender's device complied).
    Same provider_message_id, so this closes the loop on the original drop
    instead of leaving it looking like permanent loss.
    """
    if not msg_id:
        return
    DroppedMessage.objects.filter(
        account=account, msg_id=msg_id, resolved_at__isnull=True,
    ).update(resolved_at=timezone.now())

logger = logging.getLogger(__name__)

DUPLICATE_BROADCAST_WINDOW_MINUTES   = 60
DUPLICATE_BROADCAST_SIMILARITY_THRESHOLD = 0.92  # same bar as inquiry_service's layer-2 match

# A match against a message in the SAME chat only counts as a duplicate within this tight
# window — an accidental double-paste/double-send. Beyond it, two similarly-worded messages
# in the same chat are far more likely to be genuinely distinct sequential requests (e.g.
# same model, different region/storage/qty — "Silver Japan 10pc" then "Silver USA 15pc" ten
# minutes later) than a repost of the same ask. Cross-chat matches keep the full
# DUPLICATE_BROADCAST_WINDOW_MINUTES — that's this check's actual intended case (the same
# list posted to several different groups), where a wider window is exactly the point.
DUPLICATE_BROADCAST_SAME_CHAT_WINDOW_SECONDS = 60


def _is_duplicate_group_broadcast(message) -> bool:
    """
    Traders often post the identical WTB/WTS list to many different WhatsApp groups
    within minutes of each other — each one otherwise triggers its own AI classification
    call and its own Inquiry row to triage separately, even though it's the same ask.

    If a message from ANY group (not just this one, not scoped to the same contact —
    a repost from a different sender/group still counts) already produced a genuine
    inquiry (is_inquiry=True) via AI classification within the last hour, and this
    message's embedding is a close semantic match, skip classifying this one again.
    A same-chat match is held to a much tighter time window — see
    DUPLICATE_BROADCAST_SAME_CHAT_WINDOW_SECONDS above.

    Only applies to GROUP chats — direct 1:1 messages are never dropped this way, and
    if this message has no embedding yet (embedding provider lagged/failed), we fail
    open (return False) rather than risk silently dropping a real inquiry.
    """
    from django.utils.timezone import now
    from datetime import timedelta

    if message.chat.chat_type != ChatType.GROUP:
        return False

    try:
        from apps.message_intelligence.models import MessageEmbedding
        from pgvector.django import CosineDistance

        my_emb = MessageEmbedding.objects.filter(message=message).first()
        if not my_emb or my_emb.embedding is None:
            return False

        window = now() - timedelta(minutes=DUPLICATE_BROADCAST_WINDOW_MINUTES)
        candidate = (
            MessageEmbedding.objects
            .filter(
                message__account_id=message.account_id,
                message__chat__chat_type=ChatType.GROUP,
                message__classification__is_inquiry=True,
                message__message_time__gte=window,
                embedding__isnull=False,
            )
            .exclude(message_id=message.pk)
            .select_related('message')
            .annotate(distance=CosineDistance('embedding', my_emb.embedding))
            .order_by('distance')
            .first()
        )
        if not candidate or candidate.distance > (1 - DUPLICATE_BROADCAST_SIMILARITY_THRESHOLD):
            return False

        if candidate.message.chat_id == message.chat_id:
            gap_seconds = abs((message.message_time - candidate.message.message_time).total_seconds())
            if gap_seconds > DUPLICATE_BROADCAST_SAME_CHAT_WINDOW_SECONDS:
                return False

        logger.info(
            'duplicate_group_broadcast | message_id=%s matches earlier message_id=%s | distance=%.4f',
            message.pk, candidate.message_id, candidate.distance,
        )
        return True
    except Exception:
        logger.debug('duplicate_group_broadcast | check failed, failing open', exc_info=True)
    return False


def _base_eligibility_skip_reason(message) -> str | None:
    """Checks shared by both AI classification and automation-rule matching:
    must have text, be inbound, and not be a history-sync message older than 24h."""
    from django.utils.timezone import now
    if not message.message_text:
        return 'no_text'
    if message.direction != 'inbound':
        return 'outbound'
    age_seconds = (now() - message.message_time).total_seconds()
    if age_seconds > 86400:  # older than 24 h — history-sync message
        return 'too_old'
    return None


def _classify_skip_reason(message) -> str | None:
    """Return the AiParsingLog skip_reason code, or None if the message should
    be sent for AI classification.

    Tri-state per-chat override: chat.ai_parsing=True forces on, False forces off,
    None inherits account.ai_parsing_enabled global toggle.
    """
    reason = _base_eligibility_skip_reason(message)
    if reason:
        return reason

    # Tri-state: per-chat setting takes priority over account global.
    chat_override = getattr(message.chat, 'ai_parsing', None)
    if chat_override is False:
        return 'chat_disabled'
    if chat_override is None:
        account_enabled = getattr(message.account, 'ai_parsing_enabled', True)
        if not account_enabled:
            return 'account_disabled'

    # Cross-group broadcast dedup — checked last since it's the most expensive check
    # (a DB similarity query), so cheaper/cheaper-to-decide skip reasons short-circuit first.
    if _is_duplicate_group_broadcast(message):
        return 'duplicate_broadcast'

    return None


def _automation_skip_reason(message) -> str | None:
    """Eligibility gate for automation-rule matching. Deliberately does NOT
    check the chat/account ai_parsing toggle — that toggle controls whether a
    chat's messages get classified as inquiries, which is a separate concern
    from whether a specifically-configured watch rule should fire on it. A
    rule watching a contact inside a group where AI classification is off
    (e.g. an internal staff group) must still be able to fire."""
    reason = _base_eligibility_skip_reason(message)
    if reason:
        return reason
    if _is_duplicate_group_broadcast(message):
        return 'duplicate_broadcast'
    return None


def _log_ai_parsing_and_classify(message) -> None:
    """Record the sent/skipped routing decision for this message, then classify
    it if it wasn't skipped. Single source of truth for the AI Parsing Log page.
    """
    from apps.trading.models import AiParsingLog
    reason = _classify_skip_reason(message)
    AiParsingLog.objects.update_or_create(
        message=message,
        defaults={
            'account': message.account,
            'chat': message.chat,
            'status': 'skipped' if reason else 'sent',
            'skip_reason': reason or '',
            'message_preview': (message.message_text or '')[:200],
        },
    )
    if not reason:
        from apps.trading.services.classification_service import classify_message
        classify_message(message)

    # Automated Price Update rules (Product Price Update > Sale Price) — gated
    # independently of AI classification (see _automation_skip_reason) so a rule
    # can still fire inside a chat that has AI classification turned off. Never
    # allowed to break ingestion/classification on failure.
    if not _automation_skip_reason(message):
        try:
            from apps.trading.services.price_update_automation import check_automation_rules
            check_automation_rules(message)
        except Exception:
            logger.exception('check_automation_rules failed | message_id=%s', message.pk)


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


def _process_message_in_background(message_id: int, sync_log_id: int = None):
    """Embed then classify a single live message in one background thread.

    Keeps embed + classify in the same thread so classification runs immediately
    after the embedding is stored (needed for Layer-2 similarity dedup).
    """
    def _run():
        embedded = errors = 0
        try:
            from apps.whatsapp_bridge.models import WhatsAppMessage

            message = (
                WhatsAppMessage.objects
                .select_related('account', 'chat', 'contact')
                .get(pk=message_id)
            )

            if message.message_text:
                from apps.message_intelligence.services.embedding_service import embed_message
                try:
                    ok = embed_message(message_id)
                    embedded, errors = (1, 0) if ok else (0, 1)
                except Exception:
                    # A transient embedding-provider failure (rate limit, timeout, network
                    # blip) must never take classification down with it — they're
                    # independent concerns. Previously this exception propagated past this
                    # point and skipped _log_ai_parsing_and_classify() entirely, silently
                    # dropping the message from classification with zero trace anywhere.
                    logger.warning(
                        'embed_message failed for message_id=%s — continuing to '
                        'classification anyway', message_id, exc_info=True,
                    )
                    errors = 1

            _log_ai_parsing_and_classify(message)

        except Exception:
            logger.warning(
                'Background processing failed for message_id=%s', message_id, exc_info=True,
            )
            errors = 1
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
                    logger.debug('Could not update SyncLog %s with processing result', sync_log_id)
            _db_conn.close()

    threading.Thread(target=_run, daemon=True).start()


class IngestionService:

    def ingest_message(self, payload: dict) -> WhatsAppMessage:
        worker_session_id = payload['worker_session_id']
        account = WhatsAppAccount.objects.get(pk=worker_session_id)

        contact = self._upsert_contact(account, payload)
        chat = self._upsert_chat(account, contact, payload)
        message, created = self._insert_message(account, chat, contact, payload)
        _resolve_dropped_message(account, payload.get('provider_message_id'))

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

            # Live messages: embed + classify (or log why not) in the same background
            # thread. History batch messages use _embed_in_background (no classification,
            # no AiParsingLog — they'd all read as skipped:too_old and just add noise).
            _process_message_in_background(message.pk, sync_log_id=sync_log.pk)

        return message

    def recover_unresolved_for_lid(self, account: WhatsAppAccount, lid_jid: str, phone_jid: str) -> dict:
        """
        Reprocess every `WhatsAppUnresolvedMessage` pending for (account, lid_jid)
        now that lid_jid is known to resolve to phone_jid. Reuses the exact same
        contact/chat/message upsert path normal ingestion uses (`_upsert_contact`/
        `_upsert_chat`/`_insert_message`) — no separate business logic, per the
        "preferred structure" in the P0 message-preservation spec.

        Idempotent: if a row's provider_message_id already exists as a real
        WhatsAppMessage (e.g. Baileys successfully retried delivery on its own
        before this ran), the row is linked to that existing message instead of
        creating a duplicate — the account+provider_message_id uniqueness on
        WhatsAppMessage is the final backstop either way.

        A per-row failure never aborts the batch and never marks that row
        resolved without an actual WhatsAppMessage behind it — resolution_error
        is recorded and resolution_status stays 'pending' (retryable on the next
        successful mapping event) rather than being guessed at.
        """
        pending = list(
            WhatsAppUnresolvedMessage.objects.filter(
                account=account, lid_jid=lid_jid, resolution_status=ResolutionStatus.PENDING,
            )
        )
        recovered = 0
        failed = 0

        for row in pending:
            try:
                existing = None
                if row.provider_message_id:
                    existing = WhatsAppMessage.objects.filter(
                        account=account, provider_message_id=row.provider_message_id,
                    ).first()

                if existing:
                    message = existing
                else:
                    payload = dict(row.raw_payload or {})
                    payload['worker_session_id'] = account.pk
                    payload['chat_id'] = phone_jid
                    payload.setdefault('chat_type', ChatType.INDIVIDUAL)

                    contact = self._upsert_contact(account, payload)
                    chat = self._upsert_chat(account, contact, payload)
                    message, created = self._insert_message(account, chat, contact, payload)
                    _resolve_dropped_message(account, payload.get('provider_message_id'))

                    if created:
                        if row.is_history:
                            # History-sourced: same treatment as ingest_batch — embed only,
                            # never live-classified, so a resurfaced old message can't be
                            # mistaken for a fresh real-time inquiry.
                            if message.message_text:
                                _embed_in_background([message.pk])
                        else:
                            if payload.get('direction') == 'inbound':
                                WhatsAppChat.objects.filter(pk=chat.pk).update(unread_count=F('unread_count') + 1)
                            sync_log = SyncLog.objects.create(
                                account=account,
                                event_type='message_ingest',
                                status='success',
                                metadata={
                                    'provider_message_id': payload.get('provider_message_id'),
                                    'chat_id': phone_jid,
                                    'recovered_from_unresolved': True,
                                    'unresolved_message_id': row.pk,
                                },
                            )
                            _process_message_in_background(message.pk, sync_log_id=sync_log.pk)

                row.resolution_status = ResolutionStatus.RESOLVED
                row.resolved_contact = message.contact
                row.resolved_message = message
                row.resolution_error = ''
                row.resolved_at = timezone.now()
                row.save(update_fields=[
                    'resolution_status', 'resolved_contact', 'resolved_message',
                    'resolution_error', 'resolved_at', 'updated_at',
                ])
                recovered += 1
            except Exception as e:
                failed += 1
                logger.exception(
                    'recover_unresolved_for_lid failed | account=%s lid_jid=%s unresolved_id=%s',
                    account.pk, lid_jid, row.pk,
                )
                try:
                    row.resolution_error = str(e)
                    row.save(update_fields=['resolution_error', 'updated_at'])
                except Exception:
                    logger.exception(
                        'Failed to record resolution_error for unresolved_id=%s', row.pk,
                    )

        return {'total': len(pending), 'recovered': recovered, 'failed': failed}

    def preserve_unresolved_message(self, account: WhatsAppAccount, payload: dict) -> WhatsAppUnresolvedMessage:
        """
        Durably record a message whose LID couldn't be resolved to a phone JID,
        without discarding its content. Idempotent on (account, provider_message_id)
        when a provider_message_id is present — a worker retry of the same POST
        (e.g. it never saw our 200 due to a network blip) updates the same row
        instead of creating a duplicate pending record for identical content.
        """
        provider_message_id = payload.get('provider_message_id') or None
        message_time = parse_datetime(payload['message_time']) if payload.get('message_time') else None

        fields = {
            'raw_jid':              payload.get('raw_jid', ''),
            'participant_jid':      payload.get('participant_jid') or '',
            'lid_jid':              payload.get('lid_jid') or '',
            'from_me':              bool(payload.get('from_me')),
            'direction':            payload.get('direction') or '',
            'message_type':         payload.get('message_type') or 'unknown',
            'message_text':         payload.get('message_text') or '',
            'has_media':            bool(payload.get('has_media')),
            'message_time':         message_time,
            'push_name':            payload.get('push_name') or '',
            'is_history':           bool(payload.get('is_history')),
            'reason':               payload.get('reason') or 'unresolvable_lid',
            'raw_key':              payload.get('raw_key'),
            'raw_payload':          payload.get('raw_payload'),
        }

        if provider_message_id:
            obj, _ = WhatsAppUnresolvedMessage.objects.update_or_create(
                account=account,
                provider_message_id=provider_message_id,
                defaults=fields,
            )
        else:
            obj = WhatsAppUnresolvedMessage.objects.create(
                account=account, provider_message_id=None, **fields,
            )
        return obj

    def ingest_batch(self, worker_session_id, payloads: list, is_latest: bool = False, received: int = None) -> dict:
        """Process a list of messages (from history sync) in one call.

        Skips per-message SyncLog and unread_count updates — history messages are
        already-read messages from the user's phone. Always creates one batch SyncLog
        entry, even when payloads is empty: a narrow history_days window can filter an
        entire WhatsApp-delivered chunk down to zero, and the sync-progress UI needs
        that logged to tell "done, nothing in range" apart from "still hanging".
        """
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
                _resolve_dropped_message(account, payload.get('provider_message_id'))
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
                # The worker successfully delivered this message — if we fail to persist
                # it, the only record must not be a log line naming just the ID, with the
                # actual content gone. Store the full payload (not just raw_key's usual
                # msg.key shape) so the content is recoverable, same DroppedMessage table
                # the drop-log UI already reads.
                try:
                    DroppedMessage.objects.create(
                        account=account,
                        msg_id=payload.get('provider_message_id') or None,
                        raw_jid=payload.get('chat_id') or None,
                        from_me=payload.get('direction') == 'outbound',
                        has_message=True,
                        reason='batch_persist_failed',
                        raw_key={'payload': payload, 'error': str(e)},
                    )
                except Exception:
                    logger.exception(
                        'Failed to record batch_persist_failed drop for msg %s — content is now unrecoverable',
                        payload.get('provider_message_id'),
                    )

        sync_log = SyncLog.objects.create(
            account=account,
            event_type='history_sync',
            status='success' if not error_count else 'warning',
            metadata={
                'total': len(payloads),
                'received': received if received is not None else len(payloads),
                'created': created_count,
                'skipped': skipped_count,
                'errors': error_count,
                'is_latest': is_latest,
            },
        )

        if error_count:
            # No round-trip needed — Django can write its own WorkerAlert directly. The
            # per-message DroppedMessage rows above hold the content; this is the
            # aggregate signal that shows up in the same alert list/badge as worker-side
            # failures, since a batch that's silently 3-errors-out-of-100 is exactly the
            # kind of thing "admin should be notified" was about.
            try:
                WorkerAlert.objects.create(
                    account=account,
                    alert_type='batch_partial_failure',
                    severity='error',
                    message=f'{error_count} of {len(payloads)} messages in a history/live batch failed to persist',
                    context={'total': len(payloads), 'errors': error_count, 'sync_log_id': sync_log.pk},
                )
            except Exception:
                logger.exception('Failed to record batch_partial_failure WorkerAlert')

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

        # create_defaults is only applied when a new row is actually created — defaults
        # is NOT merged in on create, only on update. phone_number must be in both, or a
        # contact's very first-ever message creates them with a blank phone_number that
        # only self-heals once a second message arrives.
        create_defaults = {'phone_number': sender_number}
        if push_name:
            create_defaults['display_name'] = push_name

        try:
            contact, _ = WhatsAppContact.objects.update_or_create(
                account=account,
                wa_contact_id=wa_contact_id,
                defaults=defaults,
                create_defaults=create_defaults,
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
