from rest_framework import serializers
from apps.whatsapp_bridge.models import (
    WhatsAppAccount, WhatsAppChat, WhatsAppMessage, WhatsAppContact, SyncLog, DroppedMessage,
    WhatsAppGroup, WhatsAppGroupParticipant, WorkerAlert, StuckReceipt, WhatsAppUnresolvedMessage,
    BaileysEvent, SessionStatus, OutboundAsset, OutboundMessage,
)


class WhatsAppAccountSerializer(serializers.ModelSerializer):
    total_unread = serializers.SerializerMethodField()
    effective_classification_version = serializers.SerializerMethodField()
    worker_liveness_status = serializers.SerializerMethodField()
    effective_session_status = serializers.SerializerMethodField()

    def get_total_unread(self, obj):
        return obj.chats.filter(unread_count__gt=0).count()

    class Meta:
        model = WhatsAppAccount
        fields = [
            'id', 'display_name', 'phone_number', 'session_status',
            'worker_session_id', 'last_connected_at', 'last_disconnected_at',
            'last_worker_heartbeat_at', 'worker_liveness_status', 'effective_session_status',
            'is_active', 'created_at', 'total_unread',
            'sync_history', 'history_days', 'idle_disconnect_minutes',
            'auto_download_media', 'ai_parsing_enabled',
            'outbound_sending_enabled', 'direct_sending_enabled', 'group_sending_enabled',
            'image_sending_enabled',
            'recipient_interval_ms', 'account_interval_ms',
            'allow_concurrent_sends', 'max_concurrent_sends', 'unknown_new_chat_policy',
            'classification_version_override', 'effective_classification_version',
            'connection_unhealthy', 'connection_unhealthy_reason', 'connection_unhealthy_since',
        ]
        read_only_fields = [
            'id', 'session_status', 'worker_session_id',
            'last_connected_at', 'last_disconnected_at', 'last_worker_heartbeat_at',
            'worker_liveness_status', 'effective_session_status', 'created_at',
            'effective_classification_version',
            'connection_unhealthy', 'connection_unhealthy_reason', 'connection_unhealthy_since',
        ]

    def get_effective_classification_version(self, obj):
        from apps.trading.services.classification_service import effective_classification_version
        return effective_classification_version(obj)

    def get_worker_liveness_status(self, obj):
        return _worker_liveness_status(obj)

    def get_effective_session_status(self, obj):
        if obj.session_status == SessionStatus.CONNECTED and _worker_liveness_status(obj) != 'online':
            return 'stale'
        return obj.session_status


class WhatsAppAccountSettingsSerializer(serializers.ModelSerializer):
    recipient_interval_ms = serializers.IntegerField(min_value=1000, max_value=300000)
    account_interval_ms = serializers.IntegerField(min_value=1000, max_value=300000)
    max_concurrent_sends = serializers.IntegerField(min_value=1, max_value=20)

    class Meta:
        model = WhatsAppAccount
        fields = [
            'sync_history', 'history_days', 'idle_disconnect_minutes', 'display_name',
            'ai_parsing_enabled', 'auto_download_media', 'classification_version_override',
            'outbound_sending_enabled', 'direct_sending_enabled', 'group_sending_enabled',
            'image_sending_enabled',
            'recipient_interval_ms', 'account_interval_ms',
            'allow_concurrent_sends', 'max_concurrent_sends', 'unknown_new_chat_policy',
        ]


class OutboundMessageSerializer(serializers.ModelSerializer):
    account_name = serializers.SerializerMethodField()
    requested_by_name = serializers.CharField(source='requested_by.username', default=None, read_only=True)
    events = serializers.SerializerMethodField()

    class Meta:
        model = OutboundMessage
        fields = [
            'id', 'company', 'whatsapp_account', 'account_name', 'destination_jid',
            'destination_type', 'content_type', 'content_payload', 'asset', 'status', 'status_reason',
            'idempotency_key', 'provider_message_id', 'correlation_id', 'new_chat_state',
            'new_chat_confidence', 'new_chat_reason', 'permission_snapshot', 'settings_snapshot',
            'provider_response', 'attempt_count', 'requested_by_name', 'requested_at',
            'eligible_at', 'dispatch_started_at', 'provider_accepted_at', 'delivered_at',
            'read_at', 'finished_at', 'last_error_code', 'last_error', 'events',
        ]
        read_only_fields = fields

    def get_account_name(self, obj):
        return obj.whatsapp_account.display_name or obj.whatsapp_account.phone_number

    def get_events(self, obj):
        if not self.context.get('include_events'):
            return []
        return [
            {
                'id': event.pk, 'event_type': event.event_type, 'actor': event.actor,
                'attempt_number': event.attempt_number, 'detail': event.detail,
                'metadata': event.metadata, 'created_at': event.created_at,
            }
            for event in obj.events.all()
        ]


class OutboundAssetSerializer(serializers.ModelSerializer):
    class Meta:
        model = OutboundAsset
        fields = [
            'id', 'original_filename', 'mime_type', 'size_bytes', 'sha256', 'created_at',
        ]
        read_only_fields = fields


def _worker_liveness_status(obj):
    from django.utils.timezone import now

    if not obj.last_worker_heartbeat_at:
        return 'unknown'
    age_seconds = (now() - obj.last_worker_heartbeat_at).total_seconds()
    return 'online' if age_seconds <= 90 else 'stale'


class ContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = WhatsAppContact
        fields = [
            'id', 'phone_number', 'display_name', 'push_name', 'wa_contact_id',
            'is_business', 'is_existing_chat',
        ]


class ContactDetailSerializer(serializers.ModelSerializer):
    account_id    = serializers.IntegerField(source='account.pk', read_only=True)
    account_name  = serializers.SerializerMethodField()
    message_count = serializers.IntegerField(read_only=True, default=0)
    chat_id       = serializers.SerializerMethodField()
    chat_db_id    = serializers.SerializerMethodField()
    contact_type  = serializers.SerializerMethodField()
    ai_parsing    = serializers.SerializerMethodField()
    role_tags     = serializers.SerializerMethodField()
    role_category = serializers.SerializerMethodField()

    class Meta:
        model = WhatsAppContact
        fields = [
            'id', 'account_id', 'wa_contact_id', 'lid_jid', 'username', 'phone_number',
            'display_name', 'push_name', 'is_business', 'category', 'role_tags', 'role_category',
            'is_existing_chat',
            'account_name',
            'contact_type', 'message_count', 'chat_id', 'chat_db_id', 'ai_parsing',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'account_id', 'wa_contact_id', 'lid_jid', 'username', 'phone_number',
            'push_name', 'is_business', 'role_tags', 'role_category', 'account_name', 'contact_type',
            'message_count', 'chat_id', 'chat_db_id', 'ai_parsing',
            'created_at', 'updated_at',
        ]

    def _first_chat(self, obj):
        return next(iter(obj.chats.all()), None)

    def get_account_name(self, obj):
        account = obj.account
        return account.display_name or account.phone_number or f'Account {account.pk}'

    def get_contact_type(self, obj):
        jid = obj.wa_contact_id
        if jid.endswith('@s.whatsapp.net'):
            return 'phone'
        if jid.endswith('@lid'):
            return 'lid'  # should be zero after migration; kept for observability
        if jid.endswith('@g.us'):
            return 'group'
        return 'unknown'

    def get_role_tags(self, obj):
        return sorted(tag.role for tag in obj.role_tags.all())

    def get_role_category(self, obj):
        roles = set(self.get_role_tags(obj))
        if {'supplier', 'customer'}.issubset(roles):
            return 'both'
        if 'supplier' in roles:
            return 'supplier'
        if 'customer' in roles:
            return 'customer'
        return ''

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
    is_announcement = serializers.SerializerMethodField()
    last_message_preview = serializers.SerializerMethodField()
    last_message_direction = serializers.SerializerMethodField()
    message_count = serializers.SerializerMethodField()

    class Meta:
        model = WhatsAppChat
        fields = [
            'id', 'wa_chat_id', 'chat_type', 'name', 'contact',
            'display_name', 'is_announcement', 'last_message_at', 'last_message_preview',
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

    def get_is_announcement(self, obj):
        group = getattr(obj, 'group', None)
        return bool(group and (group.announce or group.is_community_announcement))

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


class BaileysEventSerializer(serializers.ModelSerializer):
    account_name = serializers.SerializerMethodField()
    django_message_id = serializers.IntegerField(source='whatsapp_message_id', read_only=True)

    class Meta:
        model = BaileysEvent
        fields = [
            'id', 'account', 'account_name', 'session_id', 'event_type', 'event_stage',
            'status', 'provider_message_id', 'django_message_id', 'raw_jid', 'remote_jid',
            'participant_jid', 'participant_pn', 'sender_jid', 'sender_number',
            'push_name', 'direction', 'message_type', 'upsert_type', 'reason',
            'error_message', 'raw_key', 'raw_payload', 'metadata', 'created_at',
        ]
        read_only_fields = fields

    def get_account_name(self, obj):
        if not obj.account:
            return ''
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
            'raw_key', 'raw_payload',
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
            'owner_jid', 'is_community', 'is_community_announcement',
            'announce', 'restrict', 'account_participant_role',
            'account_is_participant', 'can_send', 'send_block_reason',
            'metadata_refreshed_at', 'participant_count',
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
