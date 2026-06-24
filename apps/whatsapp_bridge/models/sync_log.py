from django.db import models


class SyncLog(models.Model):
    account = models.ForeignKey(
        'whatsapp_bridge.WhatsAppAccount',
        on_delete=models.CASCADE,
        related_name='sync_logs',
    )
    event_type = models.CharField(max_length=100)
    status = models.CharField(max_length=50)
    message = models.TextField(blank=True)
    metadata = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'whatsapp_sync_log'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.event_type} | {self.status} | {self.created_at}"
