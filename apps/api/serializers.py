from rest_framework import serializers
from apps.whatsapp_bridge.models import (
    WhatsAppAccount, WhatsAppChat, WhatsAppMessage, WhatsAppContact, SyncLog, DroppedMessage,
    WhatsAppGroup, WhatsAppGroupParticipant, WorkerAlert, StuckReceipt, WhatsAppUnresolvedMessage,
)


class WhatsAppAccountSerializer(serializers.ModelSerializer):
    total_unread = serializers.SerializerMethodField()

    def get_total_unread(self, obj):
        return obj.chats.filter(unread_count__gt=0).count()

    class Meta:
        model = WhatsAppAccount
        fields = [
            'id', 'display_name', 'phone_number', 'session_status',
            'worker_session_id', 'last_connected_at', 'last_disconnected_at',
            'is_active', 'created_at', 'total_unread',
            'sync_history', 'history_days', 'idle_disconnect_minutes',
            'auto_download_media', 'ai_parsing_enabled',
            'connection_unhealthy', 'connection_unhealthy_reason', 'connection_unhealthy_since',
        ]
        read_only_fields = [
            'id', 'session_status', 'worker_session_id',
            'last_connected_at', 'last_disconnected_at', 'created_at',
            'connection_unhealthy', 'connection_unhealthy_reason', 'connection_unhealthy_since',
        ]


class ContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = WhatsAppContact
        fields = ['id', 'phone_number', 'display_name', 'push_name', 'wa_contact_id', 'is_business']


class ContactDetailSerializer(serializers.ModelSerializer):
    account_id    = serializers.IntegerField(source='account.pk', read_only=True)
    message_count = serializers.IntegerField(read_only=True, default=0)
    chat_id       = serializers.SerializerMethodField()
    chat_db_id    = serializers.SerializerMethodField()
    contact_type  = serializers.SerializerMethodField()
    ai_parsing    = serializers.SerializerMethodField()

    class Meta:
        model = WhatsAppContact
        fields = [
            'id', 'account_id', 'wa_contact_id', 'lid_jid', 'username', 'phone_number',
            'display_name', 'push_name', 'is_business', 'category',
            'contact_type', 'message_count', 'chat_id', 'chat_db_id', 'ai_parsing',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'account_id', 'wa_contact_id', 'lid_jid', 'username', 'phone_number',
            'push_name', 'is_business', 'contact_type',
            'message_count', 'chat_id', 'chat_db_id', 'ai_parsing',
            'created_at', 'updated_at',
        ]

    def _first_chat(self, obj):
        return next(iter(obj.chats.all()), None)

    def get_contact_type(self, obj):
        jid = obj.wa_contact_id
        if jid.endswith('@s.whatsapp.net'):
            return 'phone'
        if jid.endswith('@lid'):
            return 'lid'  # should be zero after migration; kept for observability
        if jid.endswith('@g.us'):
            return 'group'
        return 'unknown'

    def get_chat_id(self, obj):
        chat = self._first_chat(obj)
        return chat.wa_chat_id if chat else None

    def get_chat_db_id(self, obj):
        chat = self._first_chat(obj)
        return chat.pk if chat else None

    def get_ai_parsing(self, obj):
        chat = self._first_chat(obj)
        return chat.ai_parsing if chat else None


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
            'ai_parsing',
        ]

    def get_display_name(self, obj):
        if obj.name:
            return obj.name
        if obj.contact:
            name = obj.contact.display_name or obj.contact.push_name
            if name:
                return name
        # Derive label from JID type
        jid = obj.wa_chat_id
        local, _, server = jid.partition('@')
        if server == 's.whatsapp.net':
            return f'+{local}'
        if server == 'lid':
            # WhatsApp privacy-mode contact — no phone number available until name syncs
            return 'Unknown Contact'
        return jid

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
    account_id   = serializers.IntegerField(source='account.pk', read_only=True)

    class Meta:
        model = SyncLog
        fields = ['id', 'event_type', 'status', 'message', 'metadata', 'created_at', 'account_name', 'account_id']

    def get_account_name(self, obj):
        return obj.account.display_name or obj.account.phone_number or f'Account #{obj.account.pk}'


class DroppedMessageSerializer(serializers.ModelSerializer):
    account_name = serializers.SerializerMethodField()
    account_id   = serializers.IntegerField(source='account.pk', read_only=True)

    class Meta:
        model = DroppedMessage
        fields = ['id', 'account_id', 'account_name', 'msg_id', 'raw_jid',
                  'from_me', 'has_message', 'reason', 'raw_key', 'created_at', 'resolved_at']

    def get_account_name(self, obj):
        return obj.account.display_name or obj.account.phone_number or f'Account #{obj.account.pk}'


class WorkerAlertSerializer(serializers.ModelSerializer):
    account_name = serializers.SerializerMethodField()

    class Meta:
        model = WorkerAlert
        fields = ['id', 'account', 'account_name', 'alert_type', 'severity', 'message',
                  'context', 'created_at', 'acknowledged_at', 'acknowledged_by']
        read_only_fields = ['id', 'account', 'account_name', 'alert_type', 'severity',
                             'message', 'context', 'created_at', 'acknowledged_by']

    def get_account_name(self, obj):
        if not obj.account:
            return None
        return obj.account.display_name or obj.account.phone_number or f'Account #{obj.account.pk}'


class StuckReceiptSerializer(serializers.ModelSerializer):
    account_name = serializers.SerializerMethodField()

    class Meta:
        model = StuckReceipt
        fields = ['id', 'account', 'account_name', 'remote_jid', 'participant', 'message_id',
                  'from_me', 'context', 'occurrence_count', 'first_seen_at', 'last_seen_at',
                  'resolved_at', 'resolved_by']
        read_only_fields = ['id', 'account', 'account_name', 'remote_jid', 'participant',
                             'message_id', 'from_me', 'context', 'occurrence_count',
                             'first_seen_at', 'last_seen_at', 'resolved_by']

    def get_account_name(self, obj):
        if not obj.account:
            return None
        return obj.account.display_name or obj.account.phone_number or f'Account #{obj.account.pk}'

    def get_account_name(self, obj):
        if not obj.account:
            return ''
        return obj.account.display_name or obj.account.phone_number or f'Account #{obj.account.pk}'


class UnresolvedMessageSerializer(serializers.ModelSerializer):
    account_name = serializers.SerializerMethodField()
    message_preview = serializers.SerializerMethodField()

    class Meta:
        model = WhatsAppUnresolvedMessage
        fields = [
            'id', 'account', 'account_name', 'raw_jid', 'participant_jid', 'lid_jid',
            'from_me', 'direction', 'message_type', 'message_preview', 'has_media',
            'message_time', 'push_name', 'is_history', 'reason',
            'resolution_status', 'resolved_contact', 'resolved_message', 'resolution_error',
            'created_at', 'updated_at', 'resolved_at',
        ]
        read_only_fields = fields

    def get_account_name(self, obj):
        if not obj.account:
            return ''
        return obj.account.display_name or obj.account.phone_number or f'Account #{obj.account.pk}'

    def get_message_preview(self, obj):
        return (obj.message_text or '')[:200]


class GroupParticipantSerializer(serializers.ModelSerializer):
    display_name = serializers.SerializerMethodField()

    class Meta:
        model = WhatsAppGroupParticipant
        fields = ['id', 'wa_jid', 'role', 'is_active', 'display_name', 'joined_at', 'updated_at']

    def get_display_name(self, obj):
        if obj.contact:
            return obj.contact.display_name or obj.contact.push_name or obj.wa_jid
        return obj.wa_jid


class GroupSerializer(serializers.ModelSerializer):
    account_id      = serializers.IntegerField(source='account.pk', read_only=True)
    community_id    = serializers.IntegerField(source='community.pk', read_only=True, allow_null=True)
    community_name  = serializers.CharField(source='community.name', read_only=True, allow_null=True)
    sub_group_count = serializers.SerializerMethodField()
    chat_db_id      = serializers.SerializerMethodField()
    ai_parsing      = serializers.SerializerMethodField()

    class Meta:
        model = WhatsAppGroup
        fields = [
            'id', 'account_id', 'wa_group_id', 'name', 'description',
            'owner_jid', 'is_community', 'participant_count',
            'community_id', 'community_name', 'sub_group_count',
            'chat_db_id', 'ai_parsing',
            'created_at', 'updated_at',
        ]

    def get_sub_group_count(self, obj):
        if obj.is_community:
            return obj.sub_groups.count()
        return 0

    def _get_chat(self, obj):
        from apps.whatsapp_bridge.models import WhatsAppChat
        return WhatsAppChat.objects.filter(account=obj.account, wa_chat_id=obj.wa_group_id).first()

    def get_chat_db_id(self, obj):
        chat = self._get_chat(obj)
        return chat.pk if chat else None

    def get_ai_parsing(self, obj):
        chat = self._get_chat(obj)
        return chat.ai_parsing if chat else None


class GroupDetailSerializer(GroupSerializer):
    participants = serializers.SerializerMethodField()

    class Meta(GroupSerializer.Meta):
        fields = GroupSerializer.Meta.fields + ['participants']

    def get_participants(self, obj):
        qs = obj.participants.filter(is_active=True).select_related('contact').order_by('-role', 'wa_jid')
        return GroupParticipantSerializer(qs, many=True).data


class MessageSerializer(serializers.ModelSerializer):
    sender_name    = serializers.SerializerMethodField()
    classification = serializers.SerializerMethodField()

    class Meta:
        model = WhatsAppMessage
        fields = [
            'id', 'sender_number', 'sender_name', 'direction', 'message_type',
            'message_text', 'message_time', 'has_media',
            'media_mime_type', 'media_file_name', 'media_url',
            'classification',
        ]

    def get_sender_name(self, obj):
        if obj.contact:
            name = obj.contact.display_name or obj.contact.push_name
            if name:
                return name
            phone = obj.contact.phone_number
            if phone:
                return f'+{phone}'
        return f'+{obj.sender_number}' if obj.sender_number else ''

    def get_classification(self, obj):
        try:
            c = obj.classification
            return {'tags': c.tags, 'is_inquiry': c.is_inquiry, 'inquiry_type': c.inquiry_type}
        except Exception:
            return None
