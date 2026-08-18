from django.db import models


class BuyingInquiryStatus(models.TextChoices):
    OPEN = 'open', 'Open'
    CLOSED = 'closed', 'Closed'


class SupplierQuoteStatus(models.TextChoices):
    NOT_ASKED = 'not_asked', 'Not Asked'
    ASKED = 'asked', 'Asked - Waiting'
    QUOTED = 'quoted', 'Quoted'
    DECLINED = 'declined', 'Declined / No Stock'


class BuyingInquirySupplierSource(models.TextChoices):
    AUTO = 'auto', 'Auto'
    MANUAL = 'manual', 'Manual'


class BuyingInquiry(models.Model):
    """A manually-created 'I need to buy X' request, shopped around to a list of
    supplier contacts (see SupplierQuote) rather than detected from an inbound message
    like the AI-classified Inquiry model.
    """
    account = models.ForeignKey(
        'whatsapp_bridge.WhatsAppAccount',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='buying_inquiries',
    )
    company = models.ForeignKey(
        'tenancy.Company',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='buying_inquiries',
    )
    name = models.CharField(max_length=255, blank=True)
    product_name = models.CharField(max_length=255, blank=True)
    quantity = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=BuyingInquiryStatus.choices,
        default=BuyingInquiryStatus.OPEN,
        db_index=True,
    )
    header_template = models.TextField(default='Hello, looking to buy:')
    product_line_template = models.TextField(default='- {product_name} - Qty {qty} - Target {price}')
    footer_template = models.TextField(default='Please reply with availability and best price.')
    created_by = models.ForeignKey(
        'auth.User',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='buying_inquiries_created',
    )
    closed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'trading_buying_inquiry'
        ordering = ['-created_at', '-id']
        verbose_name_plural = 'buying inquiries'
        indexes = [
            models.Index(fields=['company', 'status', 'created_at'], name='buyinq_company_status_idx'),
        ]

    def __str__(self):
        return self.name or f'{self.product_name} ({self.quantity})'.strip()


class BuyingInquiryProduct(models.Model):
    inquiry = models.ForeignKey(
        BuyingInquiry,
        on_delete=models.CASCADE,
        related_name='products',
    )
    product = models.ForeignKey(
        'trading.Product',
        on_delete=models.CASCADE,
        related_name='buying_inquiry_rows',
    )
    quantity = models.IntegerField(null=True, blank=True)
    target_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=10, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'trading_buying_inquiry_product'
        ordering = ['id']
        constraints = [
            models.UniqueConstraint(fields=['inquiry', 'product'], name='unique_buying_inquiry_product'),
        ]

    def __str__(self):
        return f'{self.inquiry_id}: {self.product}'


class BuyingInquirySupplier(models.Model):
    inquiry = models.ForeignKey(
        BuyingInquiry,
        on_delete=models.CASCADE,
        related_name='suppliers',
    )
    contact = models.ForeignKey(
        'whatsapp_bridge.WhatsAppContact',
        on_delete=models.CASCADE,
        related_name='buying_inquiry_rows',
    )
    source = models.CharField(
        max_length=20,
        choices=BuyingInquirySupplierSource.choices,
        default=BuyingInquirySupplierSource.MANUAL,
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
        db_table = 'trading_buying_inquiry_supplier'
        ordering = ['id']
        constraints = [
            models.UniqueConstraint(fields=['inquiry', 'contact'], name='unique_buying_inquiry_supplier'),
        ]

    def __str__(self):
        return f'{self.inquiry_id}: {self.contact}'


class SupplierQuote(models.Model):
    """One supplier's status/response for a given BuyingInquiry."""
    buying_inquiry = models.ForeignKey(
        BuyingInquiry,
        on_delete=models.CASCADE,
        related_name='supplier_quotes',
    )
    supplier = models.ForeignKey(
        'whatsapp_bridge.WhatsAppContact',
        on_delete=models.CASCADE,
        related_name='quote_requests',
    )
    status = models.CharField(max_length=10, choices=SupplierQuoteStatus.choices, default=SupplierQuoteStatus.NOT_ASKED)
    asked_at = models.DateTimeField(null=True, blank=True)
    quoted_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    quoted_currency = models.CharField(max_length=10, blank=True, default='USD')
    quote_note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'trading_supplier_quote'
        unique_together = [('buying_inquiry', 'supplier')]
        ordering = ['id']

    def __str__(self):
        return f'supplier={self.supplier_id} inquiry={self.buying_inquiry_id} status={self.status}'
