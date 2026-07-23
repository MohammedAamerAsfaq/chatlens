from django.core.exceptions import ValidationError
from django.db import models

from .connection_provider import ConnectionProvider


class CommunicationAccount(models.Model):
    channel = models.CharField(max_length=20, choices=ConnectionProvider.CHANNEL_CHOICES)
    company = models.ForeignKey(
        'tenancy.Company',
        on_delete=models.CASCADE,
        related_name='communication_accounts',
    )
    provider = models.ForeignKey(
        'tenancy.ConnectionProvider',
        on_delete=models.PROTECT,
        related_name='communication_accounts',
    )
    name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    external_account_id = models.CharField(max_length=255, blank=True)
    config = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tenant_communication_account'
        ordering = ['company__name', 'name']

    def clean(self):
        super().clean()
        if self.provider_id and self.channel != self.provider.channel:
            raise ValidationError({
                'provider': 'Provider channel must match communication account channel.',
            })

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.name} [{self.channel}]'

