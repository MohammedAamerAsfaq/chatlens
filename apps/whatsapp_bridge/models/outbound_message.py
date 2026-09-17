import uuid

from django.conf import settings
from django.db import models


class OutboundMessage(models.Model):
    STATUS_QUEUED = 'queued'
    STATUS_DEFERRED = 'deferred'
    STATUS_BLOCKED = 'preflight_blocked'
    STATUS_SENDING = 'sending'
    STATUS_SENT = 'sent'
    STATUS_DELIVERED = 'delivered'
    STATUS_READ = 'read'
    STATUS_FAILED = 'failed'
    STATUS_CANCELLED = 'cancelled'
    STATUS_UNKNOWN = 'unknown'
    STATUS_CHOICES = [(value, value.replace('_', ' ').title()) for value in (
        STATUS_QUEUED, STATUS_DEFERRED, STATUS_BLOCKED, STATUS_SENDING, STATUS_SENT,
        STATUS_DELIVERED, STATUS_READ, STATUS_FAILED, STATUS_CANCELLED, STATUS_UNKNOWN,
    )]
    TERMINAL_STATUSES = (
        STATUS_BLOCKED, STATUS_SENT, STATUS_DELIVERED, STATUS_READ,
        STATUS_FAILED, STATUS_CANCELLED, STATUS_UNKNOWN,
    )

    company = models.ForeignKey('tenancy.Company', on_delete=models.CASCADE, related_name='outbound_messages')
    whatsapp_account = models.ForeignKey(
        'whatsapp_bridge.WhatsAppAccount', on_delete=models.CASCADE, related_name='outbound_messages',
    )
    destination_jid = models.CharField(max_length=255)
    canonical_recipient_key = models.CharField(max_length=255, db_index=True)
    destination_type = models.CharField(max_length=40, blank=True)
    content_type = models.CharField(max_length=20, default='text')
    content_payload = models.JSONField(default=dict)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default=STATUS_QUEUED, db_index=True)
    status_reason = models.CharField(max_length=100, blank=True)
    idempotency_key = models.CharField(max_length=255)
    provider_message_id = models.CharField(max_length=100, unique=True, default=uuid.uuid4)
    correlation_id = models.CharField(max_length=255, db_index=True)
    new_chat_state = models.CharField(max_length=30, default='unknown')
    new_chat_confidence = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)
    new_chat_reason = models.CharField(max_length=100, blank=True)
    permission_snapshot = models.JSONField(default=dict, blank=True)
    settings_snapshot = models.JSONField(default=dict, blank=True)
    provider_response = models.JSONField(default=dict, blank=True)
    attempt_count = models.PositiveIntegerField(default=0)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='outbound_messages_requested',
    )
    requested_at = models.DateTimeField(auto_now_add=True)
    eligible_at = models.DateTimeField(null=True, blank=True)
    dispatch_started_at = models.DateTimeField(null=True, blank=True)
    provider_accepted_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    last_error_code = models.CharField(max_length=100, blank=True)
    last_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'whatsapp_outbound_message'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'idempotency_key'], name='unique_company_outbound_idempotency',
            ),
        ]
        indexes = [
            models.Index(
                fields=['whatsapp_account', 'status', 'eligible_at'],
                name='whatsapp_ou_whatsap_6059aa_idx',
            ),
        ]


class OutboundMessageEvent(models.Model):
    message = models.ForeignKey(OutboundMessage, on_delete=models.CASCADE, related_name='events')
    event_type = models.CharField(max_length=50)
    actor = models.CharField(max_length=255, blank=True)
    attempt_number = models.PositiveIntegerField(default=0)
    detail = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'whatsapp_outbound_message_event'
        ordering = ['created_at', 'id']


class OutboundAccountState(models.Model):
    whatsapp_account = models.OneToOneField(
        'whatsapp_bridge.WhatsAppAccount', on_delete=models.CASCADE, related_name='outbound_state',
    )
    last_dispatch_started_at = models.DateTimeField(null=True, blank=True)
    in_flight_count = models.PositiveIntegerField(default=0)
    lease_version = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'whatsapp_outbound_account_state'


class OutboundRecipientState(models.Model):
    whatsapp_account = models.ForeignKey(
        'whatsapp_bridge.WhatsAppAccount', on_delete=models.CASCADE, related_name='outbound_recipient_states',
    )
    canonical_recipient_key = models.CharField(max_length=255)
    last_dispatch_started_at = models.DateTimeField(null=True, blank=True)
    in_flight_count = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'whatsapp_outbound_recipient_state'
        constraints = [
            models.UniqueConstraint(
                fields=['whatsapp_account', 'canonical_recipient_key'],
                name='unique_outbound_recipient_state',
            ),
        ]
