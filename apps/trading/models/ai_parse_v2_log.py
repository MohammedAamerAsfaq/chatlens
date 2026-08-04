from django.db import models


class AiParseV2Log(models.Model):
    STATUS_PASS1_STARTED = 'pass1_started'
    STATUS_PASS1_DONE = 'pass1_done'
    STATUS_PASS2_STARTED = 'pass2_started'
    STATUS_COMPLETE = 'complete'
    STATUS_ERROR = 'error'

    STATUS_CHOICES = [
        (STATUS_PASS1_STARTED, 'Pass 1 Started'),
        (STATUS_PASS1_DONE, 'Pass 1 Done'),
        (STATUS_PASS2_STARTED, 'Pass 2 Started'),
        (STATUS_COMPLETE, 'Complete'),
        (STATUS_ERROR, 'Error'),
    ]

    message = models.OneToOneField(
        'whatsapp_bridge.WhatsAppMessage',
        on_delete=models.CASCADE,
        related_name='ai_parse_v2_log',
    )
    account = models.ForeignKey(
        'whatsapp_bridge.WhatsAppAccount',
        on_delete=models.CASCADE,
        related_name='ai_parse_v2_logs',
    )
    chat = models.ForeignKey(
        'whatsapp_bridge.WhatsAppChat',
        on_delete=models.CASCADE,
        related_name='ai_parse_v2_logs',
        null=True,
        blank=True,
    )
    classification = models.ForeignKey(
        'trading.MessageClassification',
        on_delete=models.SET_NULL,
        related_name='ai_parse_v2_logs',
        null=True,
        blank=True,
    )
    inquiry_ids = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default=STATUS_PASS1_STARTED)
    pass1_request = models.JSONField(null=True, blank=True)
    pass1_response = models.TextField(blank=True)
    pass1_parsed = models.JSONField(null=True, blank=True)
    pass2_request = models.JSONField(null=True, blank=True)
    pass2_response = models.TextField(blank=True)
    pass2_parsed = models.JSONField(null=True, blank=True)
    pass1_ai_ms = models.PositiveIntegerField(null=True, blank=True)
    pass1_total_ms = models.PositiveIntegerField(null=True, blank=True)
    candidate_search_ms = models.PositiveIntegerField(null=True, blank=True)
    pass2_ai_ms = models.PositiveIntegerField(null=True, blank=True)
    pass2_total_ms = models.PositiveIntegerField(null=True, blank=True)
    total_ms = models.PositiveIntegerField(null=True, blank=True)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'trading_ai_parse_v2_log'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['account', 'created_at']),
            models.Index(fields=['status', 'created_at']),
        ]

    def __str__(self):
        return f'V2ParseLog(message={self.message_id}, status={self.status})'
