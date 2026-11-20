from django.conf import settings
from django.db import models


class TradingMessageReview(models.Model):
    """Explicit human message-level label; never changes the live classification."""
    company = models.ForeignKey('tenancy.Company', on_delete=models.CASCADE)
    message = models.OneToOneField('whatsapp_bridge.WhatsAppMessage', on_delete=models.CASCADE, related_name='trading_review')
    source_text = models.TextField()
    ai_snapshot = models.JSONField(default=dict)
    label = models.JSONField()
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=['company', 'created_at'])]
