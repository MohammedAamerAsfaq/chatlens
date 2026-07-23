from django.db import models


class InquiryStatus(models.TextChoices):
    OPEN            = 'open',            'Open'
    REQUESTED_PRICE = 'requested_price',  'Requested Price'
    QUOTED_WAITING  = 'quoted_waiting',   'Quoted - Waiting'
    NO_RESPONSE    = 'no_response',    'No Response'
    PRICE_HIGH     = 'price_high',     'Price High'
    NO_STOCK       = 'no_stock',       'No Stock'
    CURRENTLY_IN_STOCK = 'currently_in_stock', 'Currently In Stock'
    NOT_DEALING    = 'not_dealing',    'Product Not Dealing with ATM'
    IRRELEVANT     = 'irrelevant',     'Irrelevant'
    CLOSED         = 'closed',         'Closed'
    DEAL_DONE      = 'deal_done',      'Deal Done'
    TRACKING       = 'tracking',       'Tracking'
    INCORRECT_MATCH = 'incorrect_match', 'Incorrect Match'


class Inquiry(models.Model):
    INQUIRY_TYPE_CHOICES = [
        ('buy',  'Buy'),
        ('sell', 'Sell'),
    ]
    SOURCE_TYPE_CHOICES = [
        ('direct',    'Direct'),
        ('group',     'Group'),
        ('community', 'Community'),
    ]

    company = models.ForeignKey(
        'tenancy.Company',
        null=True, blank=True,
        on_delete=models.CASCADE,
        related_name='inquiries',
    )
    account = models.ForeignKey(
        'whatsapp_bridge.WhatsAppAccount',
        on_delete=models.CASCADE,
        related_name='inquiries',
    )
    contact = models.ForeignKey(
        'whatsapp_bridge.WhatsAppContact',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='inquiries',
    )
    inquiry_type = models.CharField(max_length=10, choices=INQUIRY_TYPE_CHOICES, db_index=True)
    status       = models.CharField(
        max_length=20, choices=InquiryStatus.choices,
        default=InquiryStatus.OPEN, db_index=True,
    )
    # Snapshot of matched products at creation time
    # [{product_id, canonical_name, quantity, price, currency}]
    products = models.JSONField(default=list)

    summary = models.TextField()
    remarks = models.TextField(blank=True)

    # Snapshot of MessageClassification.suggested_contact_category at creation/update time —
    # 'supplier'/'customer'/'both', blank if the AI found no reason to suggest a category change.
    suggested_contact_category = models.CharField(max_length=20, blank=True)

    # "{buy|sell}:{product-slug}:{qty-bucket}:{contact-id}"
    # Used for cross-group deduplication within the same account + contact + time window.
    dedup_key   = models.CharField(max_length=512, db_index=True)
    source_type = models.CharField(max_length=20, choices=SOURCE_TYPE_CHOICES)

    # Manual human rating of how well the AI classified/matched THIS inquiry (1 = worst,
    # 5 = exact) — defaults to 5 so a reviewer only has to touch the ones that are
    # actually wrong, not attend every single inquiry to confirm the good ones.
    classification_rating = models.PositiveSmallIntegerField(
        default=5,
        choices=[(i, str(i)) for i in range(1, 6)],
    )

    first_seen_at = models.DateTimeField(db_index=True)
    closed_at     = models.DateTimeField(null=True, blank=True)
    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'trading_inquiry'
        ordering = ['-first_seen_at']

    def __str__(self):
        return f'Inquiry({self.pk}) {self.inquiry_type} {self.status}'


class InquiryMessage(models.Model):
    inquiry = models.ForeignKey(
        Inquiry,
        on_delete=models.CASCADE,
        related_name='inquiry_messages',
    )
    message = models.ForeignKey(
        'whatsapp_bridge.WhatsAppMessage',
        on_delete=models.CASCADE,
        related_name='inquiry_links',
    )
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'trading_inquiry_message'
        unique_together = [('inquiry', 'message')]
