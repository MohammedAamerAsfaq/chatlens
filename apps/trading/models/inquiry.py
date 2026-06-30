from django.db import models


class InquiryStatus(models.TextChoices):
    OPEN      = 'open',      'Open'
    CLOSED    = 'closed',    'Closed'
    DEAL_DONE = 'deal_done', 'Deal Done'


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

    # "{buy|sell}:{product-slug}:{qty-bucket}:{contact-id}"
    # Used for cross-group deduplication within the same account + contact + time window.
    dedup_key   = models.CharField(max_length=512, db_index=True)
    source_type = models.CharField(max_length=20, choices=SOURCE_TYPE_CHOICES)

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
