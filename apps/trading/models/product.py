from django.db import models


class Product(models.Model):
    name      = models.CharField(max_length=255)
    brand     = models.CharField(max_length=100, blank=True)
    category  = models.CharField(max_length=100, blank=True)
    sku       = models.CharField(max_length=100, blank=True)
    aliases    = models.JSONField(default=list)
    is_active  = models.BooleanField(default=True)
    # Inventory
    qty        = models.IntegerField(default=0)
    cost_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    sale_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    currency   = models.CharField(max_length=10, blank=True, default='USD')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'trading_product'
        ordering = ['brand', 'name']

    def __str__(self):
        return f'{self.brand} {self.name}'.strip()
