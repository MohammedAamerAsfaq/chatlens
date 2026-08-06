from django.db import models
from django.db.models import Q
from pgvector.django import VectorField


class NonInventoryProductStatus(models.TextChoices):
    TRACKING = 'tracking', 'Tracking'
    PROMOTED = 'promoted_to_inventory', 'Promoted to Inventory'
    DISMISSED = 'dismissed', 'Dismissed'
    MERGED = 'merged', 'Merged'


class NonInventoryProductMatchSource(models.TextChoices):
    DETERMINISTIC = 'deterministic', 'Deterministic'
    EMBEDDING = 'embedding', 'Embedding'
    AI = 'ai', 'AI'
    MANUAL = 'manual', 'Manual'


class NonInventoryProductEmbeddingStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    EMBEDDED = 'embedded', 'Embedded'
    ERROR = 'error', 'Error'
    SKIPPED = 'skipped', 'Skipped'


class NonInventoryProduct(models.Model):
    company = models.ForeignKey(
        'tenancy.Company',
        on_delete=models.CASCADE,
        related_name='non_inventory_products',
    )
    canonical_name = models.CharField(max_length=500)
    normalized_name = models.CharField(max_length=500, db_index=True, blank=True)
    # Deterministic identity key built from brand + normalized product identity attributes.
    normalized_key = models.CharField(max_length=700, db_index=True, blank=True)
    brand = models.CharField(max_length=100, blank=True)
    attributes = models.JSONField(default=dict, blank=True)

    status = models.CharField(
        max_length=30,
        choices=NonInventoryProductStatus.choices,
        default=NonInventoryProductStatus.TRACKING,
        db_index=True,
    )
    promoted_product = models.ForeignKey(
        'trading.Product',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='non_inventory_sources',
    )
    merged_into = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='merged_products',
    )

    mention_count = models.PositiveIntegerField(default=0)
    buy_mention_count = models.PositiveIntegerField(default=0)
    sell_mention_count = models.PositiveIntegerField(default=0)

    embedding = VectorField(dimensions=512, null=True, blank=True)
    embedding_model = models.CharField(max_length=255, blank=True)
    embedding_metadata = models.JSONField(null=True, blank=True)
    embedding_status = models.CharField(
        max_length=20,
        choices=NonInventoryProductEmbeddingStatus.choices,
        default=NonInventoryProductEmbeddingStatus.PENDING,
        db_index=True,
    )
    embedding_error = models.TextField(blank=True)

    first_seen_at = models.DateTimeField(db_index=True)
    last_seen_at = models.DateTimeField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'trading_non_inventory_product'
        ordering = ['-last_seen_at', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'normalized_key'],
                condition=~Q(normalized_key=''),
                name='uniq_noninv_company_norm_key',
            ),
        ]
        indexes = [
            models.Index(fields=['company', 'status', 'last_seen_at'], name='noninv_company_status_seen_idx'),
            models.Index(fields=['company', 'brand', 'normalized_name'], name='noninv_company_brand_name_idx'),
            models.Index(fields=['promoted_product'], name='noninv_promoted_product_idx'),
            models.Index(fields=['merged_into'], name='noninv_merged_into_idx'),
        ]

    def __str__(self):
        return self.canonical_name or f'NonInventoryProduct #{self.pk}'


class NonInventoryProductMention(models.Model):
    company = models.ForeignKey(
        'tenancy.Company',
        on_delete=models.CASCADE,
        related_name='non_inventory_product_mentions',
    )
    non_inventory_product = models.ForeignKey(
        'trading.NonInventoryProduct',
        on_delete=models.CASCADE,
        related_name='mentions',
    )
    inquiry = models.ForeignKey(
        'trading.Inquiry',
        on_delete=models.CASCADE,
        related_name='non_inventory_mentions',
    )
    inquiry_product = models.ForeignKey(
        'trading.InquiryProduct',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='non_inventory_mentions',
    )
    source_message = models.ForeignKey(
        'whatsapp_bridge.WhatsAppMessage',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='non_inventory_product_mentions',
    )
    account = models.ForeignKey(
        'whatsapp_bridge.WhatsAppAccount',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='non_inventory_product_mentions',
    )
    contact = models.ForeignKey(
        'whatsapp_bridge.WhatsAppContact',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='non_inventory_product_mentions',
    )
    company_contact = models.ForeignKey(
        'tenancy.CompanyContact',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='non_inventory_product_mentions',
    )

    inquiry_type = models.CharField(max_length=10, db_index=True)
    source_product_index = models.PositiveIntegerField(null=True, blank=True)
    raw_text = models.TextField(blank=True)
    canonical_name_from_ai = models.CharField(max_length=500)
    normalized_name_from_ai = models.CharField(max_length=500, db_index=True, blank=True)
    brand_from_ai = models.CharField(max_length=100, blank=True)
    attributes_from_ai = models.JSONField(default=dict, blank=True)
    quantity = models.IntegerField(null=True, blank=True)
    price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=10, blank=True)

    match_source = models.CharField(
        max_length=30,
        choices=NonInventoryProductMatchSource.choices,
        blank=True,
        db_index=True,
    )
    match_confidence = models.FloatField(null=True, blank=True)
    match_reason = models.TextField(blank=True)

    message_time = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'trading_non_inventory_product_mention'
        ordering = ['-message_time', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'inquiry_product'],
                condition=Q(inquiry_product__isnull=False),
                name='uniq_noninv_mention_inq_product',
            ),
        ]
        indexes = [
            models.Index(fields=['company', 'inquiry_type', 'message_time'], name='noninvm_cmp_type_time_idx'),
            models.Index(fields=['non_inventory_product', 'inquiry_type', 'message_time'], name='noninvm_prod_type_time_idx'),
            models.Index(fields=['company', 'match_source'], name='noninvmen_company_source_idx'),
        ]

    def __str__(self):
        return self.canonical_name_from_ai or f'NonInventoryProductMention #{self.pk}'
