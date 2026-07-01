from django.db import models


class MessageTag(models.TextChoices):
    WTB               = 'wtb',               'Want To Buy'
    WTS               = 'wts',               'Want To Sell'
    PRICE_INQUIRY     = 'price_inquiry',     'Price Inquiry'
    STOCK_INQUIRY     = 'stock_inquiry',     'Stock Availability'
    NEGOTIATION       = 'negotiation',       'Negotiation'
    DEAL_CONFIRMATION = 'deal_confirmation', 'Deal Confirmation'
    GREETING          = 'greeting',          'Greeting'
    JOKE              = 'joke',              'Joke / Casual'
    SPAM              = 'spam',              'Spam'
    OTHER             = 'other',             'Other'


class MessageClassification(models.Model):
    INQUIRY_TYPE_CHOICES = [
        ('buy',  'Buy'),
        ('sell', 'Sell'),
        ('both', 'Both'),
    ]

    message = models.OneToOneField(
        'whatsapp_bridge.WhatsAppMessage',
        on_delete=models.CASCADE,
        related_name='classification',
    )
    # List of MessageTag values, e.g. ["wtb", "price_inquiry"]
    tags = models.JSONField(default=list)

    # [{product_id, canonical_name, quantity, price, currency}]
    products = models.JSONField(default=list)

    is_inquiry   = models.BooleanField(default=False)
    inquiry_type = models.CharField(
        max_length=10, choices=INQUIRY_TYPE_CHOICES, blank=True,
    )
    ai_summary   = models.TextField(blank=True)
    dedup_key    = models.CharField(max_length=512, blank=True, default='')
    raw_response = models.JSONField(null=True, blank=True)
    classified_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'trading_message_classification'

    def __str__(self):
        return f'Classification({self.message_id}) tags={self.tags}'
