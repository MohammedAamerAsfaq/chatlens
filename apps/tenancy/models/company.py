from django.db import models


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
    is_active = models.BooleanField(default=True)
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
