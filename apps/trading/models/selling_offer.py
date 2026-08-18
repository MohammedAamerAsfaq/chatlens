from django.db import models


class SellingOfferStatus(models.TextChoices):
    OPEN = 'open', 'Open'
    CLOSED = 'closed', 'Closed'


class SellingOfferCustomerSource(models.TextChoices):
    AUTO = 'auto', 'Auto'
    MANUAL = 'manual', 'Manual'


class SellingOffer(models.Model):
    company = models.ForeignKey(
        'tenancy.Company',
        on_delete=models.CASCADE,
        related_name='selling_offers',
    )
    name = models.CharField(max_length=255)
    status = models.CharField(
        max_length=20,
        choices=SellingOfferStatus.choices,
        default=SellingOfferStatus.OPEN,
        db_index=True,
    )
    header_template = models.TextField(default='Hello, available stock offer:')
    product_line_template = models.TextField(default='- {product_name} - Qty {qty} - {price}')
    footer_template = models.TextField(default='Reply with required quantity. Subject to availability.')
    created_by = models.ForeignKey(
        'auth.User',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='selling_offers_created',
    )
    closed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'trading_selling_offer'
        ordering = ['-created_at', '-id']
        indexes = [
            models.Index(fields=['company', 'status', 'created_at'], name='selloffer_company_status_idx'),
        ]

    def __str__(self):
        return self.name


class SellingOfferProduct(models.Model):
    offer = models.ForeignKey(
        SellingOffer,
        on_delete=models.CASCADE,
        related_name='products',
    )
    product = models.ForeignKey(
        'trading.Product',
        on_delete=models.CASCADE,
        related_name='selling_offer_rows',
    )
    quantity = models.IntegerField(null=True, blank=True)
    price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=10, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'trading_selling_offer_product'
        ordering = ['id']
        constraints = [
            models.UniqueConstraint(fields=['offer', 'product'], name='unique_selling_offer_product'),
        ]

    def __str__(self):
        return f'{self.offer_id}: {self.product}'


class SellingOfferCustomer(models.Model):
    offer = models.ForeignKey(
        SellingOffer,
        on_delete=models.CASCADE,
        related_name='customers',
    )
    contact = models.ForeignKey(
        'whatsapp_bridge.WhatsAppContact',
        on_delete=models.CASCADE,
        related_name='selling_offer_rows',
    )
    source = models.CharField(
        max_length=20,
        choices=SellingOfferCustomerSource.choices,
        default=SellingOfferCustomerSource.MANUAL,
    )
    source_product = models.ForeignKey(
        'trading.Product',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
    )
    source_inquiry_product = models.ForeignKey(
        'trading.InquiryProduct',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
    )
    sent_count = models.PositiveIntegerField(default=0)
    last_sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'trading_selling_offer_customer'
        ordering = ['id']
        constraints = [
            models.UniqueConstraint(fields=['offer', 'contact'], name='unique_selling_offer_customer'),
        ]

    def __str__(self):
        return f'{self.offer_id}: {self.contact}'
