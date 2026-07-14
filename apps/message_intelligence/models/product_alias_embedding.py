from django.db import models
from pgvector.django import VectorField


class ProductAliasEmbedding(models.Model):
    """Same shape/purpose as ProductEmbedding, but one row per ProductAlias instead of
    per Product — this is what makes retrieval multi-vector: a query is compared
    against a product's own name AND every one of its aliases independently, and
    whichever single vector is closest wins, instead of averaging every phrasing
    into one blended embedding."""
    alias = models.OneToOneField(
        'trading.ProductAlias',
        on_delete=models.CASCADE,
        related_name='embedding',
    )
    embedding = VectorField(dimensions=512, null=True, blank=True)
    embedding_model = models.CharField(max_length=255)
    metadata = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'product_alias_embedding'

    def __str__(self):
        return f"Embedding for alias {self.alias_id}"
