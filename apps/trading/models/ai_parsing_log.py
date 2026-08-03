from django.db import models


class AiParsingLog(models.Model):
    STATUS_CHOICES = [
        ('sent',    'Sent for AI Parsing'),
        ('skipped', 'Skipped'),
    ]
    SKIP_REASON_CHOICES = [
        ('no_text',             'No text content'),
        ('outbound',            'Outbound message'),
        ('too_old',             'Older than 24h (history sync)'),
        ('chat_disabled',       'AI parsing off for this chat'),
        ('account_disabled',    'AI parsing off for this account'),
        ('duplicate_broadcast', 'Duplicate of a recent group broadcast'),
    ]

    message = models.OneToOneField(
        'whatsapp_bridge.WhatsAppMessage',
        on_delete=models.CASCADE,
        related_name='ai_parsing_log',
    )
    account = models.ForeignKey(
        'whatsapp_bridge.WhatsAppAccount',
        on_delete=models.CASCADE,
        related_name='ai_parsing_logs',
    )
    chat = models.ForeignKey(
        'whatsapp_bridge.WhatsAppChat',
        on_delete=models.CASCADE,
        related_name='ai_parsing_logs',
        null=True, blank=True,
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    skip_reason = models.CharField(max_length=30, choices=SKIP_REASON_CHOICES, blank=True)
    message_preview = models.CharField(max_length=200, blank=True)
    classification_version = models.CharField(max_length=10, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'trading_ai_parsing_log'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['account', 'created_at']),
            models.Index(fields=['status', 'created_at']),
        ]

    def __str__(self):
        return f'{self.status}({self.skip_reason or "-"}) msg={self.message_id}'
