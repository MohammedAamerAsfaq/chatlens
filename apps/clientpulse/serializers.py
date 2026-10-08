from rest_framework import serializers

from apps.clientpulse.models import ClientProfile, ClientReminder, ContactConsent
from apps.tenancy.models import CompanyContact, CompanyContactIdentity


class IdentityInputSerializer(serializers.Serializer):
    identity_type = serializers.ChoiceField(choices=CompanyContactIdentity.IDENTITY_TYPE_CHOICES)
    value = serializers.CharField(max_length=255)
    label = serializers.CharField(max_length=100, required=False, allow_blank=True)
    is_primary = serializers.BooleanField(required=False, default=False)


class ClientProfileInputSerializer(serializers.Serializer):
    contact_type = serializers.ChoiceField(choices=CompanyContact.CONTACT_TYPE_CHOICES, required=False)
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    middle_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    display_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    legal_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    category = serializers.ChoiceField(choices=CompanyContact.CATEGORY_CHOICES, required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    owner_id = serializers.IntegerField(required=False, allow_null=True)
    lifecycle_stage = serializers.ChoiceField(choices=ClientProfile.STAGES, required=False)
    status = serializers.ChoiceField(choices=ClientProfile.STATUSES, required=False)
    priority = serializers.ChoiceField(choices=ClientProfile.PRIORITIES, required=False)
    source = serializers.ChoiceField(choices=ClientProfile.SOURCES, required=False)
    preferred_channel = serializers.ChoiceField(choices=ClientProfile.CHANNELS, required=False, allow_blank=True)
    preferred_language = serializers.CharField(max_length=20, required=False, allow_blank=True)
    timezone = serializers.CharField(max_length=64, required=False)
    company_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    job_title = serializers.CharField(max_length=150, required=False, allow_blank=True)
    website = serializers.URLField(max_length=500, required=False, allow_blank=True)
    address_line1 = serializers.CharField(max_length=255, required=False, allow_blank=True)
    address_line2 = serializers.CharField(max_length=255, required=False, allow_blank=True)
    city = serializers.CharField(max_length=100, required=False, allow_blank=True)
    state_region = serializers.CharField(max_length=100, required=False, allow_blank=True)
    postal_code = serializers.CharField(max_length=30, required=False, allow_blank=True)
    country = serializers.CharField(max_length=100, required=False, allow_blank=True)
    last_contacted_at = serializers.DateTimeField(required=False, allow_null=True)
    last_inbound_at = serializers.DateTimeField(required=False, allow_null=True)
    next_follow_up_at = serializers.DateTimeField(required=False, allow_null=True)
    do_not_contact = serializers.BooleanField(required=False)
    do_not_contact_reason = serializers.CharField(required=False, allow_blank=True)
    identities = IdentityInputSerializer(many=True, required=False)
    tag_ids = serializers.ListField(child=serializers.IntegerField(), required=False)

    def validate(self, attrs):
        if not self.partial and not any(attrs.get(key) for key in ('display_name', 'legal_name', 'first_name')):
            raise serializers.ValidationError('A display, legal, or first name is required.')
        if attrs.get('do_not_contact') and not attrs.get('do_not_contact_reason'):
            raise serializers.ValidationError({'do_not_contact_reason': 'A reason is required.'})
        return attrs


class ClientNoteInputSerializer(serializers.Serializer):
    body = serializers.CharField()
    is_pinned = serializers.BooleanField(required=False, default=False)


class ConsentInputSerializer(serializers.Serializer):
    channel = serializers.CharField(max_length=30)
    purpose = serializers.ChoiceField(choices=ContactConsent.PURPOSES)
    status = serializers.ChoiceField(choices=ContactConsent.STATUSES)
    source = serializers.CharField(max_length=100, required=False, allow_blank=True)
    evidence = serializers.JSONField(required=False)


class ClientPulseSettingsInputSerializer(serializers.Serializer):
    consent_mode = serializers.ChoiceField(choices=('observational', 'enforced'), required=False)
    reminders_enabled = serializers.BooleanField(required=False)
    reminder_popup_enabled = serializers.BooleanField(required=False)
    reminder_sound_enabled = serializers.BooleanField(required=False)
    reminder_sound = serializers.ChoiceField(
        choices=('chime', 'bell', 'soft'), required=False,
    )
    reminder_sound_volume = serializers.IntegerField(min_value=0, max_value=100, required=False)
    reminder_desktop_notifications_enabled = serializers.BooleanField(required=False)
    reminder_poll_interval_seconds = serializers.IntegerField(
        min_value=10, max_value=300, required=False,
    )
    default_timezone = serializers.CharField(max_length=64, required=False)
    default_language = serializers.CharField(max_length=20, required=False, allow_blank=True)


class ClientReminderInputSerializer(serializers.Serializer):
    profile_id = serializers.IntegerField(required=False)
    linked_from_id = serializers.IntegerField(required=False, allow_null=True)
    assigned_to_id = serializers.IntegerField(required=False, allow_null=True)
    title = serializers.CharField(max_length=255, required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    due_at = serializers.DateTimeField(required=False)
    timezone = serializers.CharField(max_length=64, required=False)
    priority = serializers.ChoiceField(choices=ClientReminder.PRIORITIES, required=False)
    recurrence_type = serializers.ChoiceField(choices=ClientReminder.RECURRENCES, required=False)
    recurrence_rule = serializers.JSONField(required=False)

    def validate(self, attrs):
        if not self.partial:
            missing = [key for key in ('profile_id', 'title', 'due_at') if not attrs.get(key)]
            if missing:
                raise serializers.ValidationError({key: 'This field is required.' for key in missing})
        if attrs.get('recurrence_type') == 'custom':
            try:
                days = int(attrs.get('recurrence_rule', {}).get('interval_days', 0))
            except (TypeError, ValueError):
                days = 0
            if days <= 0:
                raise serializers.ValidationError({'recurrence_rule': 'Positive interval_days is required.'})
        return attrs


class SnoozeInputSerializer(serializers.Serializer):
    snoozed_until = serializers.DateTimeField()


class ManualFollowUpSerializer(serializers.Serializer):
    whatsapp_contact_id = serializers.IntegerField()
    text = serializers.CharField(required=False, allow_blank=True, max_length=10000)
    asset_id = serializers.IntegerField(required=False, allow_null=True)
    confirm_new_chat = serializers.BooleanField(required=False, default=False)
    idempotency_key = serializers.CharField(max_length=255)

    def validate(self, attrs):
        text = attrs.get('text', '').strip()
        attrs['text'] = text
        if not text and not attrs.get('asset_id'):
            raise serializers.ValidationError({'text': 'Enter text or select an image.'})
        if attrs.get('asset_id') and len(text) > 1024:
            raise serializers.ValidationError({'text': 'Image captions cannot exceed 1024 characters.'})
        return attrs
