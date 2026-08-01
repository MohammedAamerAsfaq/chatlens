from django.db import models
from pgvector.django import VectorField


class InquiryProductDecisionStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    MAPPED = 'mapped', 'Mapped'
    CREATED = 'created', 'Created'
    DISMISSED = 'dismissed', 'Dismissed'


class InquiryProductMatchStatus(models.TextChoices):
    EXACT = 'exact', 'Exact'
    NEAR = 'near', 'Near'
    UNMATCHED = 'unmatched', 'Unmatched'
    MANUAL_CONFIRMED = 'manual_confirmed', 'Manual Confirmed'
    REJECTED = 'rejected', 'Rejected'


class InquiryProductMatchSource(models.TextChoices):
    AI = 'ai', 'AI'
    ALIAS = 'alias', 'Alias'
    DETERMINISTIC = 'deterministic', 'Deterministic'
    EMBEDDING = 'embedding', 'Embedding'
    MANUAL = 'manual', 'Manual'
    BACKFILL = 'backfill', 'Backfill'


class InquiryProductEmbeddingStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    EMBEDDED = 'embedded', 'Embedded'
    ERROR = 'error', 'Error'
    SKIPPED = 'skipped', 'Skipped'


class InquiryProduct(models.Model):
    company = models.ForeignKey(
        'tenancy.Company',
        on_delete=models.CASCADE,
        related_name='inquiry_products',
    )
    inquiry = models.ForeignKey(
        'trading.Inquiry',
        on_delete=models.CASCADE,
        related_name='tracked_products',
    )
    source_message = models.ForeignKey(
        'whatsapp_bridge.WhatsAppMessage',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='inquiry_products',
    )
    account = models.ForeignKey(
        'whatsapp_bridge.WhatsAppAccount',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='inquiry_products',
    )
    contact = models.ForeignKey(
        'whatsapp_bridge.WhatsAppContact',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='inquiry_products',
    )
    company_contact = models.ForeignKey(
        'tenancy.CompanyContact',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='inquiry_products',
    )
    product = models.ForeignKey(
        'trading.Product',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='inquiry_mentions',
    )

    inquiry_type = models.CharField(max_length=10, db_index=True)
    source_product_index = models.PositiveIntegerField(null=True, blank=True)
    canonical_name = models.CharField(max_length=500)
    normalized_name = models.CharField(max_length=500, db_index=True, blank=True)
    original_text = models.TextField(blank=True)
    quantity = models.IntegerField(null=True, blank=True)
    price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=10, blank=True)

    decision_status = models.CharField(
        max_length=20,
        choices=InquiryProductDecisionStatus.choices,
        default=InquiryProductDecisionStatus.PENDING,
        db_index=True,
    )
    match_status = models.CharField(
        max_length=30,
        choices=InquiryProductMatchStatus.choices,
        default=InquiryProductMatchStatus.UNMATCHED,
        db_index=True,
    )
    match_type = models.CharField(max_length=20, blank=True)
    match_source = models.CharField(
        max_length=30,
        choices=InquiryProductMatchSource.choices,
        blank=True,
        db_index=True,
    )
    match_reason = models.TextField(blank=True)

    embedding = VectorField(dimensions=512, null=True, blank=True)
    embedding_model = models.CharField(max_length=255, blank=True)
    embedding_metadata = models.JSONField(null=True, blank=True)
    embedding_status = models.CharField(
        max_length=20,
        choices=InquiryProductEmbeddingStatus.choices,
        default=InquiryProductEmbeddingStatus.PENDING,
        db_index=True,
    )
    embedding_error = models.TextField(blank=True)

    first_seen_at = models.DateTimeField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'trading_inquiry_product'
        ordering = ['-first_seen_at', '-id']
        indexes = [
            models.Index(fields=['company', 'inquiry_type', 'first_seen_at'], name='inqprod_company_type_seen_idx'),
            models.Index(fields=['company', 'decision_status'], name='inqprod_company_decision_idx'),
            models.Index(fields=['company', 'match_status'], name='inqprod_company_match_idx'),
            models.Index(fields=['product', 'inquiry_type', 'first_seen_at'], name='inqprod_product_type_seen_idx'),
        ]

    def __str__(self):
        return self.canonical_name or f'InquiryProduct #{self.pk}'
