from django.db import models


class Product(models.Model):
    name      = models.CharField(max_length=255)
    brand     = models.CharField(max_length=100, blank=True)
    category  = models.CharField(max_length=100, blank=True)
    sku       = models.CharField(max_length=100, blank=True)
    aliases   = models.JSONField(default=list)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'trading_product'
        ordering = ['brand', 'name']

    def __str__(self):
        return f'{self.brand} {self.name}'.strip()
