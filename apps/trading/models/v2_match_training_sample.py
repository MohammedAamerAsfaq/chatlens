from django.db import models


class V2MatchTrainingSample(models.Model):
    """One human-labeled verdict on a V2 pass-2 candidate line — built to calibrate
    pass2_candidate_max_distance / exact_auto_match_max_distance (see
    trading_settings_service.get_v2_matching_settings) against real ground truth
    instead of the guessed defaults they shipped with.

    Candidates are re-run fresh against current product/alias embeddings at review
    time rather than reusing the stale distance stored on the original
    AiParseV2Log — alias coverage changes over time, and calibration should reflect
    today's retrieval quality, not whatever it was when the message first arrived.
    """
    company = models.ForeignKey(
        'tenancy.Company',
        on_delete=models.CASCADE,
        related_name='v2_match_training_samples',
    )
    message = models.ForeignKey(
        'whatsapp_bridge.WhatsAppMessage',
        on_delete=models.CASCADE,
        related_name='v2_match_training_samples',
    )
    line_index = models.PositiveIntegerField()
    query_text = models.TextField(blank=True)
    # Fresh candidate snapshot at review time: [{product_id, name, brand, distance}, ...]
    candidates = models.JSONField(default=list)

    # What the original live classification decided for this line, for comparison.
    ai_product_id = models.PositiveIntegerField(null=True, blank=True)
    ai_match_type = models.CharField(max_length=20, blank=True)

    # Human ground truth. Null correct_product means "none of the candidates were right".
    correct_product = models.ForeignKey(
        'trading.Product',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
    )
    best_distance = models.FloatField(null=True, blank=True)
    correct_distance = models.FloatField(null=True, blank=True)

    reviewed_by = models.ForeignKey(
        'auth.User',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'trading_v2_match_training_sample'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['message', 'line_index'], name='unique_v2_training_sample_line'),
        ]

    def __str__(self):
        return f'V2MatchTrainingSample(message={self.message_id}, line={self.line_index})'
