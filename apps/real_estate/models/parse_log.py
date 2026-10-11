from django.db import models


class RealEstateParseLog(models.Model):
    STATUS_SKIPPED = 'skipped'
    STATUS_GATE_PENDING = 'gate_pending'
    STATUS_GATE_RUNNING = 'gate_running'
    STATUS_EXTRACT_PENDING = 'extract_pending'
    STATUS_EXTRACT_RUNNING = 'extract_running'
    STATUS_COMPLETE = 'complete'
    STATUS_ERROR = 'error'
    STATUS_CHOICES = [
        (STATUS_SKIPPED, 'Skipped'),
        (STATUS_GATE_PENDING, 'Gate Pending'),
        (STATUS_GATE_RUNNING, 'Gate Running'),
        (STATUS_EXTRACT_PENDING, 'Extraction Pending'),
        (STATUS_EXTRACT_RUNNING, 'Extraction Running'),
        (STATUS_COMPLETE, 'Complete'),
        (STATUS_ERROR, 'Error'),
    ]

    company = models.ForeignKey(
        'tenancy.Company', on_delete=models.CASCADE,
        related_name='real_estate_parse_logs',
    )
    message = models.OneToOneField(
        'whatsapp_bridge.WhatsAppMessage', on_delete=models.CASCADE,
        related_name='real_estate_parse_log',
    )
    account = models.ForeignKey(
        'whatsapp_bridge.WhatsAppAccount', on_delete=models.PROTECT,
        related_name='real_estate_parse_logs',
    )
    chat = models.ForeignKey(
        'whatsapp_bridge.WhatsAppChat', on_delete=models.PROTECT,
        related_name='real_estate_parse_logs',
    )
    opportunity = models.OneToOneField(
        'real_estate.RealEstateOpportunity', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='parse_log',
    )
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, db_index=True)
    skip_reason = models.CharField(max_length=50, blank=True)
    gate_mode = models.CharField(max_length=20, blank=True)
    gate_decision = models.CharField(max_length=30, blank=True)
    gate_request = models.JSONField(default=dict, blank=True)
    gate_response = models.TextField(blank=True)
    gate_duration_ms = models.PositiveIntegerField(null=True, blank=True)
    extraction_request = models.JSONField(default=dict, blank=True)
    extraction_response = models.TextField(blank=True)
    extraction_result = models.JSONField(default=dict, blank=True)
    extraction_duration_ms = models.PositiveIntegerField(null=True, blank=True)
    total_duration_ms = models.PositiveIntegerField(null=True, blank=True)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'real_estate_parse_log'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'status', 'created_at']),
            models.Index(fields=['company', 'gate_decision', 'created_at']),
        ]

