from django.db import models


class DroppedMessage(models.Model):
    account = models.ForeignKey(
        'whatsapp_bridge.WhatsAppAccount',
        on_delete=models.CASCADE,
        related_name='dropped_messages',
    )
    msg_id = models.CharField(max_length=255, blank=True, null=True)
    raw_jid = models.CharField(max_length=255, blank=True, null=True)
    from_me = models.BooleanField(null=True)
    has_message = models.BooleanField(default=False)
    reason = models.CharField(max_length=100)
    raw_key = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'whatsapp_dropped_message'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['account', 'created_at'])]

    def __str__(self):
        return f"{self.reason} | {self.raw_jid or 'no-jid'} | {self.created_at}"
