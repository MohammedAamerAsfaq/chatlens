from django.db import models
from django.db.models import Q


class ConnectionProvider(models.Model):
    CHANNEL_WHATSAPP = 'whatsapp'
    CHANNEL_TELEGRAM = 'telegram'
    CHANNEL_SIGNAL = 'signal'
    CHANNEL_DISCORD = 'discord'
    CHANNEL_GMAIL = 'gmail'
    CHANNEL_EXCHANGE = 'exchange'
    CHANNEL_IMAP = 'imap'
    CHANNEL_OTHER = 'other'

    CHANNEL_CHOICES = [
        (CHANNEL_WHATSAPP, 'WhatsApp'),
        (CHANNEL_TELEGRAM, 'Telegram'),
        (CHANNEL_SIGNAL, 'Signal'),
        (CHANNEL_DISCORD, 'Discord'),
        (CHANNEL_GMAIL, 'Gmail'),
        (CHANNEL_EXCHANGE, 'Exchange'),
        (CHANNEL_IMAP, 'IMAP'),
        (CHANNEL_OTHER, 'Other'),
    ]

    key = models.SlugField(max_length=100, unique=True)
    name = models.CharField(max_length=255)
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES)
    provider_type = models.CharField(max_length=50, blank=True)
    is_active = models.BooleanField(default=True)
    is_default_for_channel = models.BooleanField(default=False)
    capabilities = models.JSONField(default=list, blank=True)
    config_schema = models.JSONField(default=dict, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tenant_connection_provider'
        ordering = ['channel', 'name']
        constraints = [
            models.UniqueConstraint(
                fields=['channel'],
                condition=Q(is_default_for_channel=True),
                name='unique_default_provider_per_channel',
            ),
        ]

    def __str__(self):
        return f'{self.name} ({self.channel})'

