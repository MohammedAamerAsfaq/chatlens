import logging
from django.db.models import F
from django.utils.dateparse import parse_datetime
from ..models import (
    WhatsAppAccount, WhatsAppContact, WhatsAppChat,
    WhatsAppMessage, ChatType, SyncLog,
)

logger = logging.getLogger(__name__)


class IngestionService:

    def ingest_message(self, payload: dict) -> WhatsAppMessage:
        worker_session_id = payload['worker_session_id']
        account = WhatsAppAccount.objects.get(pk=worker_session_id)

        contact = self._upsert_contact(account, payload)
        chat = self._upsert_chat(account, contact, payload)
        message = self._insert_message(account, chat, contact, payload)

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
        }
        SyncLog.objects.create(
            account=account,
            event_type='message_ingest',
            status='success',
            metadata={k: v for k, v in _meta.items() if v is not None},
        )

        return message

    def _upsert_contact(self, account: WhatsAppAccount, payload: dict) -> WhatsAppContact:
        sender_number = payload.get('sender_number', '')
        chat_type = payload.get('chat_type', ChatType.INDIVIDUAL)

        # For individual chats the contact JID is the chat JID.
        # For groups the contact JID is the sender's JID.
        if chat_type == ChatType.INDIVIDUAL:
            wa_contact_id = payload.get('chat_id', sender_number)
        else:
            wa_contact_id = f"{sender_number}@s.whatsapp.net" if sender_number else payload.get('chat_id', '')

        is_lid = wa_contact_id.endswith('@lid')
        push_name = payload.get('push_name', '')
        direction = payload.get('direction', 'inbound')

        # Fields to set on both create and update
        defaults = {}
        if push_name and direction == 'inbound':
            defaults['push_name'] = push_name
            defaults['display_name'] = push_name

        # For non-LID contacts, always keep phone_number current.
        # For LID contacts, never overwrite phone_number on update — the contacts.set sync
        # may have already resolved the real phone number via the Baileys lid→phone mapping,
        # and the LID local part is NOT a real phone number.
        if not is_lid:
            defaults['phone_number'] = sender_number

        # create_defaults: only applied when creating a new record, not on update.
        create_defaults = {'phone_number': ''} if is_lid else {}

        contact, _ = WhatsAppContact.objects.update_or_create(
            account=account,
            wa_contact_id=wa_contact_id,
            defaults=defaults,
            create_defaults=create_defaults,
        )
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
            'last_message_at': message_time,
        }
        group_name = payload.get('group_name', '')
        if group_name:
            defaults['name'] = group_name

        chat, _ = WhatsAppChat.objects.update_or_create(
            account=account,
            wa_chat_id=wa_chat_id,
            defaults=defaults,
        )
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
        return message
