import logging
from django.utils.dateparse import parse_datetime
from ..models import (
    WhatsAppAccount, WhatsAppContact, WhatsAppChat,
    WhatsAppMessage, ChatType, SyncLog,
)

logger = logging.getLogger(__name__)


class IngestionService:

    def ingest_message(self, payload: dict) -> WhatsAppMessage:
        worker_session_id = payload['worker_session_id']
        account = WhatsAppAccount.objects.get(worker_session_id=worker_session_id)

        contact = self._upsert_contact(account, payload)
        chat = self._upsert_chat(account, contact, payload)
        message = self._insert_message(account, chat, contact, payload)

        SyncLog.objects.create(
            account=account,
            event_type='message_ingest',
            status='success',
            metadata={'provider_message_id': payload.get('provider_message_id')},
        )

        return message

    def _upsert_contact(self, account: WhatsAppAccount, payload: dict) -> WhatsAppContact:
        sender_number = payload.get('sender_number', '')
        wa_contact_id = payload.get('chat_id', sender_number)

        contact, _ = WhatsAppContact.objects.update_or_create(
            account=account,
            wa_contact_id=wa_contact_id,
            defaults={
                'phone_number': sender_number,
            },
        )
        return contact

    def _upsert_chat(
        self, account: WhatsAppAccount, contact: WhatsAppContact, payload: dict
    ) -> WhatsAppChat:
        wa_chat_id = payload['chat_id']
        chat_type = payload.get('chat_type', ChatType.INDIVIDUAL)
        message_time = parse_datetime(payload['message_time'])

        chat, _ = WhatsAppChat.objects.update_or_create(
            account=account,
            wa_chat_id=wa_chat_id,
            defaults={
                'chat_type': chat_type,
                'contact': contact if chat_type == ChatType.INDIVIDUAL else None,
                'last_message_at': message_time,
            },
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
                'raw_payload': payload.get('raw_payload'),
            },
        )
        return message
