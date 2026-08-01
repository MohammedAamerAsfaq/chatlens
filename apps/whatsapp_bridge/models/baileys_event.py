from django.db import models


class BaileysEventStatus(models.TextChoices):
    INFO = 'info', 'Info'
    SUCCESS = 'success', 'Success'
    FAILURE = 'failure', 'Failure'
    SKIPPED = 'skipped', 'Skipped'


class BaileysEventStage(models.TextChoices):
    RECEIVED = 'received', 'Received from Baileys'
    FILTERED = 'filtered', 'Filtered before Django'
    FORWARDING = 'forwarding', 'Forwarding to Django'
    FORWARDED = 'forwarded', 'Forwarded to Django'
    FAILED = 'failed', 'Failed'
    HISTORY = 'history', 'History sync'
    INTERNAL = 'internal', 'Baileys internal'


class BaileysEvent(models.Model):
    """
    Per-message Baileys audit trail. This is broader than DroppedMessage and
    WorkerAlert: it records successful receipt/forward events and failure/filter
    events against the same provider message id so message flow is traceable.
    """
    account = models.ForeignKey(
        'whatsapp_bridge.WhatsAppAccount',
        on_delete=models.CASCADE,
        related_name='baileys_events',
        null=True,
        blank=True,
    )
    whatsapp_message = models.ForeignKey(
        'whatsapp_bridge.WhatsAppMessage',
        on_delete=models.SET_NULL,
        related_name='baileys_events',
        null=True,
        blank=True,
    )
    session_id = models.CharField(max_length=64, blank=True)
    event_type = models.CharField(max_length=100)
    event_stage = models.CharField(max_length=30, choices=BaileysEventStage.choices)
    status = models.CharField(max_length=20, choices=BaileysEventStatus.choices)
    provider_message_id = models.CharField(max_length=255, blank=True, db_index=True)
    raw_jid = models.CharField(max_length=255, blank=True)
    remote_jid = models.CharField(max_length=255, blank=True)
    participant_jid = models.CharField(max_length=255, blank=True)
    participant_pn = models.CharField(max_length=255, blank=True)
    sender_jid = models.CharField(max_length=255, blank=True)
    sender_number = models.CharField(max_length=64, blank=True)
    push_name = models.CharField(max_length=255, blank=True)
    direction = models.CharField(max_length=20, blank=True)
    message_type = models.CharField(max_length=50, blank=True)
    upsert_type = models.CharField(max_length=30, blank=True)
    reason = models.CharField(max_length=120, blank=True)
    error_message = models.TextField(blank=True)
    raw_key = models.JSONField(null=True, blank=True)
    raw_payload = models.JSONField(null=True, blank=True)
    metadata = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'whatsapp_baileys_event'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['account', 'created_at']),
            models.Index(fields=['account', 'provider_message_id']),
            models.Index(fields=['event_stage', 'created_at']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['reason', 'created_at']),
        ]

    def __str__(self):
        return f"{self.event_stage}:{self.event_type} | {self.status} | {self.provider_message_id or 'no-msg-id'}"
