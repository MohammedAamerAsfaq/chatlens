from rest_framework import serializers
from apps.whatsapp_bridge.models import (
    WhatsAppAccount, WhatsAppChat, WhatsAppMessage, WhatsAppContact, SyncLog,
)


class WhatsAppAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = WhatsAppAccount
        fields = [
            'id', 'display_name', 'phone_number', 'session_status',
            'worker_session_id', 'last_connected_at', 'last_disconnected_at',
            'is_active', 'created_at',
        ]
        read_only_fields = [
            'id', 'session_status', 'worker_session_id',
            'last_connected_at', 'last_disconnected_at', 'created_at',
        ]


class ContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = WhatsAppContact
        fields = ['id', 'phone_number', 'display_name', 'push_name', 'wa_contact_id', 'is_business']


class ChatSerializer(serializers.ModelSerializer):
    contact = ContactSerializer(read_only=True)
    display_name = serializers.SerializerMethodField()
    last_message_preview = serializers.SerializerMethodField()
    last_message_direction = serializers.SerializerMethodField()
    message_count = serializers.SerializerMethodField()

    class Meta:
        model = WhatsAppChat
        fields = [
            'id', 'wa_chat_id', 'chat_type', 'name', 'contact',
            'display_name', 'last_message_at', 'last_message_preview',
            'last_message_direction', 'message_count', 'unread_count',
        ]

    def get_display_name(self, obj):
        if obj.name:
            return obj.name
        if obj.contact:
            return (
                obj.contact.display_name
                or obj.contact.push_name
                or obj.contact.phone_number
                or obj.wa_chat_id
            )
        return obj.wa_chat_id

    def get_last_message_preview(self, obj):
        msg = obj.messages.order_by('-message_time').first()
        if not msg:
            return ''
        if msg.message_text:
            return msg.message_text[:80]
        return f'[{msg.message_type}]'

    def get_last_message_direction(self, obj):
        msg = obj.messages.order_by('-message_time').first()
        return msg.direction if msg else None

    def get_message_count(self, obj):
        return obj.messages.count()


class SyncLogSerializer(serializers.ModelSerializer):
    account_name = serializers.SerializerMethodField()

    class Meta:
        model = SyncLog
        fields = ['id', 'event_type', 'status', 'message', 'metadata', 'created_at', 'account_name']

    def get_account_name(self, obj):
        return obj.account.display_name or obj.account.phone_number or f'Account #{obj.account.pk}'


class MessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.SerializerMethodField()

    class Meta:
        model = WhatsAppMessage
        fields = [
            'id', 'sender_number', 'sender_name', 'direction', 'message_type',
            'message_text', 'message_time', 'has_media',
            'media_mime_type', 'media_file_name', 'media_url',
        ]

    def get_sender_name(self, obj):
        if obj.contact:
            return (
                obj.contact.display_name
                or obj.contact.push_name
                or obj.contact.phone_number
                or obj.sender_number
            )
        return obj.sender_number
