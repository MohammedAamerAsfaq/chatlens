from django.conf import settings
from django.db import models


class StuckReceipt(models.Model):
    """
    One row per distinct message that WhatsApp keeps asking us to resend (a
    'retry receipt') but that our own send path can't actually fulfill — Baileys'
    relayMessage throws on it every time (see WorkerAlert 'error in sending
    message again' occurrences for the underlying crash). Rather than let every
    repeat of the same request hit assertSessions() (a real network round-trip
    to WhatsApp) and crash again, the worker records the first occurrence here
    and short-circuits every later repeat locally — the worker's getMessage()
    callback returns null for any key matching a row in this table, so Baileys
    takes its own documented "message not available" path instead of attempting
    (and failing) to relay it again. This table is the queryable, one-by-one
    review queue for those permanently-stuck messages; occurrence_count/
    last_seen_at show whether WhatsApp is still asking.
    """
    account = models.ForeignKey(
        'whatsapp_bridge.WhatsAppAccount',
        on_delete=models.CASCADE,
        related_name='stuck_receipts',
        null=True, blank=True,
    )
    remote_jid  = models.CharField(max_length=255)
    participant = models.CharField(max_length=255, blank=True)
    message_id  = models.CharField(max_length=255)
    from_me     = models.BooleanField(default=True)
    context     = models.JSONField(null=True, blank=True)

    occurrence_count = models.PositiveIntegerField(default=1)
    first_seen_at    = models.DateTimeField(auto_now_add=True)
    last_seen_at     = models.DateTimeField(auto_now=True)

    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='+',
    )

    class Meta:
        db_table = 'whatsapp_stuck_receipt'
        ordering = ['-last_seen_at']
        constraints = [
            models.UniqueConstraint(
                fields=['account', 'remote_jid', 'message_id'],
                name='unique_stuck_receipt_per_message',
            ),
        ]
        indexes = [
            models.Index(fields=['account', 'resolved_at']),
        ]

    def __str__(self):
        return f"{self.remote_jid}:{self.message_id} | seen {self.occurrence_count}x"
