from django.db import models
from django.db.models import Q


class ResolutionStatus(models.TextChoices):
    PENDING  = 'pending',  'Pending'
    RESOLVED = 'resolved', 'Resolved'
    FAILED   = 'failed',   'Failed'


class WhatsAppUnresolvedMessage(models.Model):
    """
    Durable preservation for a WhatsApp message that carried genuine user content
    but arrived with a chat identity (LID) ChatLens could not resolve to a phone
    JID at ingestion time. Identity resolution and message preservation are
    separate concerns — this table exists so a resolution failure never means
    the message itself is gone, only that it's parked pending resolution.

    This is deliberately NOT a substitute for `whatsapp_dropped_message`, which
    remains the record for genuinely non-user-message events (protocol frames,
    status broadcasts, pure key-distribution envelopes, malformed events). A row
    here always has real message content in `raw_payload`/`message_text`, and is
    expected to eventually become a normal `WhatsAppMessage` once its LID maps to
    a phone JID (see `IngestionService.recover_unresolved_for_lid`).

    Scope (see `docs/Contact Message Loss — LID Resolution Fix Proposal.md`):
    only individual chats where the chat-level `remoteJid` itself is a LID.
    Group messages from an unresolvable LID *participant* still use the
    existing `unresolvable_lid` drop path unchanged — that message's chat
    identity (the group) is already known; only groups.
    """

    account = models.ForeignKey(
        'whatsapp_bridge.WhatsAppAccount',
        on_delete=models.CASCADE,
        related_name='unresolved_messages',
        null=True, blank=True,
    )

    provider_message_id = models.CharField(max_length=255, null=True, blank=True)
    raw_jid             = models.CharField(max_length=255)
    participant_jid      = models.CharField(max_length=255, blank=True)
    lid_jid              = models.CharField(max_length=255, blank=True, db_index=True)
    from_me              = models.BooleanField(default=False)
    direction             = models.CharField(max_length=10, blank=True)  # 'inbound' / 'outbound', blank if undeterminable

    message_type   = models.CharField(max_length=20, default='unknown')
    message_text   = models.TextField(blank=True)
    has_media      = models.BooleanField(default=False)
    message_time   = models.DateTimeField(null=True, blank=True)
    push_name      = models.CharField(max_length=255, blank=True)

    # True when this arrived via history sync / a reconnect-redelivered 'prepend'
    # batch rather than a live 'notify'/'append' event — preserved so recovery
    # routes through the same live-vs-history post-processing split ingestion
    # already uses (no live AI classification of resurfaced historical messages).
    is_history = models.BooleanField(default=False)

    reason = models.CharField(max_length=50, default='unresolvable_lid')

    raw_key     = models.JSONField(null=True, blank=True)
    # Full recoverable ingest-ready payload (same shape IngestionService.ingest_message
    # expects, minus chat_id) — required so reprocessing never needs WhatsApp to resend.
    raw_payload = models.JSONField(null=True, blank=True)

    resolution_status  = models.CharField(
        max_length=10, choices=ResolutionStatus.choices, default=ResolutionStatus.PENDING,
        db_index=True,
    )
    resolved_contact = models.ForeignKey(
        'whatsapp_bridge.WhatsAppContact',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='+',
    )
    resolved_message = models.ForeignKey(
        'whatsapp_bridge.WhatsAppMessage',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='+',
    )
    resolution_error = models.TextField(blank=True, default='')

    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'whatsapp_unresolved_message'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['account', 'provider_message_id'],
                condition=Q(provider_message_id__isnull=False),
                name='unique_unresolved_message_per_account_provider_id',
            ),
        ]
        indexes = [
            models.Index(fields=['account', 'resolution_status']),
            models.Index(fields=['account', 'lid_jid', 'resolution_status']),
        ]

    def __str__(self):
        return f"{self.raw_jid} | {self.resolution_status} | {self.created_at}"
