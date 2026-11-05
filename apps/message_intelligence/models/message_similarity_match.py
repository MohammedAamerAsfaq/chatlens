from django.db import models


class MessageSimilarityMatch(models.Model):
    """Observational record: the closest earlier group message by embedding similarity.

    Never used to skip or merge anything — duplicate skipping is decided only by the
    deterministic content_fingerprint. Kept for analysis (repost patterns, template reuse).
    """
    message = models.OneToOneField(
        'whatsapp_bridge.WhatsAppMessage',
        on_delete=models.CASCADE,
        related_name='similarity_match',
    )
    similar_message = models.ForeignKey(
        'whatsapp_bridge.WhatsAppMessage',
        on_delete=models.CASCADE,
        related_name='similarity_matched_by',
    )
    distance = models.FloatField()
    same_chat = models.BooleanField()
    same_sender = models.BooleanField()
    exact_fingerprint = models.BooleanField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'message_similarity_match'

    def __str__(self):
        return f'Message {self.message_id} ~ {self.similar_message_id} ({self.distance:.4f})'
