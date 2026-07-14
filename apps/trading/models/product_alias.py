from django.db import models


class ProductAlias(models.Model):
    """
    One alternate name/spelling/code for a Product — a customer's own phrasing
    ("17PM 256", "SKU-4421") that maps back to a single catalog entry. Split out
    from a plain JSON list on Product so each alias can carry its own embedding
    (see ProductAliasEmbedding) — a query gets compared against every alias's own
    vector individually, not one blended-together vector for the whole product,
    which is what actually helps when the same product gets typed differently in
    every inquiry.
    """
    product = models.ForeignKey(
        'trading.Product',
        on_delete=models.CASCADE,
        related_name='alias_set',
    )
    alias      = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'trading_product_alias'
        ordering = ['alias']
        constraints = [
            models.UniqueConstraint(fields=['product', 'alias'], name='unique_product_alias'),
        ]

    def __str__(self):
        return f'{self.alias} → product {self.product_id}'
