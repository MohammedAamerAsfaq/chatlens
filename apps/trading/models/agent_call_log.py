from django.db import models


class AgentCallLog(models.Model):
    PURPOSE_CLASSIFICATION    = 'classification'
    PURPOSE_PRODUCT_EXTRACTION = 'product_extraction'

    PURPOSE_CHOICES = [
        (PURPOSE_CLASSIFICATION,     'Inquiry Classification'),
        (PURPOSE_PRODUCT_EXTRACTION, 'Product Extraction'),
    ]

    purpose      = models.CharField(max_length=50, choices=PURPOSE_CHOICES, db_index=True)
    provider     = models.CharField(max_length=50, blank=True)
    model        = models.CharField(max_length=100, blank=True)
    messages     = models.JSONField()          # full messages array sent to AI
    response     = models.TextField(blank=True)
    input_tokens  = models.IntegerField(default=0)
    output_tokens = models.IntegerField(default=0)
    duration_ms  = models.IntegerField(default=0)
    success      = models.BooleanField(default=True)
    error        = models.TextField(blank=True)
    # optional link to the WhatsApp message that triggered classification
    wa_message_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    created_at   = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'trading_agent_call_log'
        ordering = ['-created_at']
