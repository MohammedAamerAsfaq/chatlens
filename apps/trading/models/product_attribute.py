from django.db import models


class ProductAttribute(models.Model):
    """
    A hot-addable key/value detail on a Product — e.g. "Color: Silver",
    "Warranty: 1 year" — for anything worth recording that doesn't warrant its
    own column on Product. One row per key so keys can be added, renamed, or
    removed per product without a schema change.
    """
    product = models.ForeignKey(
        'trading.Product',
        on_delete=models.CASCADE,
        related_name='attribute_set',
    )
    key        = models.CharField(max_length=100)
    value      = models.CharField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'trading_product_attribute'
        ordering = ['key']
        constraints = [
            models.UniqueConstraint(fields=['product', 'key'], name='unique_product_attribute_key'),
        ]

    def __str__(self):
        return f'{self.key}={self.value} (product {self.product_id})'
