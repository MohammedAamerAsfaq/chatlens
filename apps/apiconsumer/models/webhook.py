import secrets

from django.db import models


def _generate_webhook_secret():
    return secrets.token_urlsafe(32)


class WebhookSubscription(models.Model):
    EVENT_MESSAGE_INBOUND_RECEIVED = 'message.inbound.received'
    EVENT_OUTBOUND_STATUS_CHANGED = 'outbound_message.status_changed'
    EVENT_CHOICES = [
        (EVENT_MESSAGE_INBOUND_RECEIVED, 'Inbound message received'),
        (EVENT_OUTBOUND_STATUS_CHANGED, 'Outbound message status changed'),
    ]

    company = models.ForeignKey('tenancy.Company', on_delete=models.CASCADE, related_name='webhook_subscriptions')
    created_by_api_key = models.ForeignKey(
        'apiconsumer.ApiKey', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='webhook_subscriptions_created',
    )
    target_url = models.URLField(max_length=1000)
    secret = models.CharField(max_length=64, default=_generate_webhook_secret)
    event_types = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'apiconsumer_webhook_subscription'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['company', 'is_active'])]

    def __str__(self):
        return f'{self.company}: {self.target_url}'


class WebhookDeliveryAttempt(models.Model):
    subscription = models.ForeignKey(
        WebhookSubscription, on_delete=models.CASCADE, related_name='delivery_attempts',
    )
    event_type = models.CharField(max_length=80)
    payload = models.JSONField(default=dict)
    attempt_number = models.PositiveIntegerField(default=1)
    response_status = models.PositiveSmallIntegerField(null=True, blank=True)
    response_body_snippet = models.CharField(max_length=500, blank=True)
    succeeded = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'apiconsumer_webhook_delivery_attempt'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['subscription', 'created_at'])]
