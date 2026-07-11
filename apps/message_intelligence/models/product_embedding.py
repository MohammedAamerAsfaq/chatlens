from django.db import models
from pgvector.django import VectorField


class ProductEmbedding(models.Model):
    product = models.OneToOneField(
        'trading.Product',
        on_delete=models.CASCADE,
        related_name='embedding',
    )
    embedding = VectorField(dimensions=512, null=True, blank=True)
    embedding_model = models.CharField(max_length=255)
    metadata = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'product_embedding'

    def __str__(self):
        return f"Embedding for product {self.product_id}"
