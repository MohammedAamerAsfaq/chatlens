from django.db import models


class RealEstateAgentCallLog(models.Model):
    PURPOSE_GATE = 'gate'
    PURPOSE_EXTRACTION = 'extraction'
    PURPOSE_MATCH_RERANK = 'match_rerank'
    PURPOSE_CHOICES = [
        (PURPOSE_GATE, 'Real Estate GatePass'),
        (PURPOSE_EXTRACTION, 'Real Estate Extraction'),
        (PURPOSE_MATCH_RERANK, 'Real Estate Match Reranking'),
    ]

    company = models.ForeignKey(
        'tenancy.Company', on_delete=models.CASCADE,
        related_name='real_estate_agent_call_logs',
    )
    purpose = models.CharField(max_length=30, choices=PURPOSE_CHOICES, db_index=True)
    provider = models.CharField(max_length=50, blank=True)
    model = models.CharField(max_length=150, blank=True)
    messages = models.JSONField(default=list)
    response = models.TextField(blank=True)
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    duration_ms = models.PositiveIntegerField(default=0)
    success = models.BooleanField(default=True)
    error = models.TextField(blank=True)
    wa_message_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'real_estate_agent_call_log'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['company', 'purpose', 'created_at'])]

