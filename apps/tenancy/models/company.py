from django.db import models
from django.utils import timezone


class Company(models.Model):
    TYPE_CONTROL = 'control'
    TYPE_CUSTOMER = 'customer'
    TYPE_INTERNAL = 'internal'

    INDUSTRY_GENERAL = 'general'
    INDUSTRY_TRADING = 'trading'
    INDUSTRY_REAL_ESTATE = 'real_estate'

    COMPANY_TYPE_CHOICES = [
        (TYPE_CONTROL, 'Control'),
        (TYPE_CUSTOMER, 'Customer Company'),
        (TYPE_INTERNAL, 'Internal'),
    ]

    INDUSTRY_TYPE_CHOICES = [
        (INDUSTRY_GENERAL, 'General'),
        (INDUSTRY_TRADING, 'Trading'),
        (INDUSTRY_REAL_ESTATE, 'Real Estate'),
    ]
    CLASSIFICATION_V1 = 'v1'
    CLASSIFICATION_V2 = 'v2'
    CLASSIFICATION_VERSION_CHOICES = [
        (CLASSIFICATION_V1, 'Classification V1'),
        (CLASSIFICATION_V2, 'Classification V2'),
    ]

    name = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    company_type = models.CharField(
        max_length=20,
        choices=COMPANY_TYPE_CHOICES,
        default=TYPE_CUSTOMER,
    )
    industry_type = models.CharField(
        max_length=30,
        choices=INDUSTRY_TYPE_CHOICES,
        default=INDUSTRY_GENERAL,
    )
    default_classification_version = models.CharField(
        max_length=10,
        choices=CLASSIFICATION_VERSION_CHOICES,
        default=CLASSIFICATION_V1,
    )
    ai_parsing_enabled = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    enforce_validity_period = models.BooleanField(
        default=False,
        help_text='Block company access outside the configured validity period.',
    )
    valid_from = models.DateField(null=True, blank=True)
    valid_until = models.DateField(null=True, blank=True)
    parent_company = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='managed_companies',
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tenant_company'
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def validity_status(self):
        today = timezone.localdate()
        if self.valid_from and today < self.valid_from:
            return 'not_started'
        if self.valid_until and today > self.valid_until:
            return 'expired'
        return 'valid'

    @property
    def access_is_valid(self):
        return self.is_active and (
            not self.enforce_validity_period or self.validity_status == 'valid'
        )
