from django.db import models


class BuyingInquiryStatus(models.TextChoices):
    OPEN = 'open', 'Open'
    CLOSED = 'closed', 'Closed'


class SupplierQuoteStatus(models.TextChoices):
    NOT_ASKED = 'not_asked', 'Not Asked'
    ASKED = 'asked', 'Asked - Waiting'
    QUOTED = 'quoted', 'Quoted'
    DECLINED = 'declined', 'Declined / No Stock'


class BuyingInquiry(models.Model):
    """A manually-created 'I need to buy X' request, shopped around to a list of
    supplier contacts (see SupplierQuote) rather than detected from an inbound message
    like the AI-classified Inquiry model.
    """
    account = models.ForeignKey(
        'whatsapp_bridge.WhatsAppAccount',
        on_delete=models.CASCADE,
        related_name='buying_inquiries',
    )
    product_name = models.CharField(max_length=255)
    quantity = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=BuyingInquiryStatus.choices, default=BuyingInquiryStatus.OPEN)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'trading_buying_inquiry'
        ordering = ['-created_at']
        verbose_name_plural = 'buying inquiries'

    def __str__(self):
        return f'{self.product_name} ({self.quantity})'.strip()


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
