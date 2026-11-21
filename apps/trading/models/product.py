import re

from django.db import models


def normalize_brand(brand):
    """Brands start with a capital letter; the rest is kept as typed (OnePlus, iPhone-style casing)."""
    brand = (brand or '').strip()
    return brand[:1].upper() + brand[1:]


def name_without_brand(name, brand):
    """The brand has its own field, so a name does not repeat it: 'Samsung A15 LCD' with brand
    Samsung is stored as 'A15 LCD'. A name that is only the brand is left alone."""
    name = (name or '').strip()
    brand = (brand or '').strip()
    if not brand:
        return name
    match = re.match(rf'{re.escape(brand)}\s+(?=\S)', name, re.IGNORECASE)
    return name[match.end():] if match else name


class Product(models.Model):
    company   = models.ForeignKey(
        'tenancy.Company',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='products',
    )
    name      = models.CharField(max_length=255)
    brand     = models.CharField(max_length=100, blank=True)
    category  = models.CharField(max_length=100, blank=True)
    sku       = models.CharField(max_length=100, blank=True)
    is_active  = models.BooleanField(default=True)
    tracking   = models.BooleanField(default=True)
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

    def save(self, *args, **kwargs):
        self.brand = normalize_brand(self.brand)
        self.name = name_without_brand(self.name, self.brand)
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.brand} {self.name}'.strip()
