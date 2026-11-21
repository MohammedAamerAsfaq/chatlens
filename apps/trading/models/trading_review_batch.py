from django.conf import settings
from django.db import models


class TradingReviewBatch(models.Model):
    company = models.ForeignKey('tenancy.Company', on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)


class TradingReviewBatchItem(models.Model):
    batch = models.ForeignKey(TradingReviewBatch, on_delete=models.CASCADE, related_name='items')
    message = models.ForeignKey('whatsapp_bridge.WhatsAppMessage', on_delete=models.CASCADE)
    position = models.PositiveIntegerField()
    group_id = models.CharField(max_length=64)
    sampling_pool = models.CharField(max_length=20)
    duplicate_message_ids = models.JSONField(default=list)

    class Meta:
        ordering = ['position']
        constraints = [models.UniqueConstraint(fields=['batch', 'message'], name='trading_review_batch_message_uniq'),
                       models.UniqueConstraint(fields=['batch', 'position'], name='trading_review_batch_position_uniq')]


class TradingReviewRevision(models.Model):
    review = models.ForeignKey('trading.TradingMessageReview', on_delete=models.CASCADE, related_name='revisions')
    previous_label = models.JSONField()
    previous_reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='+')
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)
