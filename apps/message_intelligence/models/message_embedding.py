from django.db import models
from pgvector.django import VectorField


class MessageEmbedding(models.Model):
    message = models.OneToOneField(
        'whatsapp_bridge.WhatsAppMessage',
        on_delete=models.CASCADE,
        related_name='embedding',
    )
    embedding = VectorField(dimensions=512, null=True, blank=True)
    embedding_model = models.CharField(max_length=255)
    metadata = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'message_embedding'

    def __str__(self):
        return f"Embedding for message {self.message_id}"
