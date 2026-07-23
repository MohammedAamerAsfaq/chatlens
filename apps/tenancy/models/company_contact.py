from django.db import models


class CompanyContact(models.Model):
    CATEGORY_SUPPLIER = 'supplier'
    CATEGORY_CUSTOMER = 'customer'
    CATEGORY_BOTH = 'both'
    CATEGORY_OTHER = 'other'

    CATEGORY_CHOICES = [
        (CATEGORY_SUPPLIER, 'Supplier'),
        (CATEGORY_CUSTOMER, 'Customer'),
        (CATEGORY_BOTH, 'Both'),
        (CATEGORY_OTHER, 'Other'),
    ]

    company = models.ForeignKey(
        'tenancy.Company',
        on_delete=models.CASCADE,
        related_name='contacts',
    )
    display_name = models.CharField(max_length=255, blank=True)
    legal_name = models.CharField(max_length=255, blank=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, blank=True)
    is_company = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tenant_company_contact'
        ordering = ['company__name', 'display_name', 'legal_name']

    def __str__(self):
        return self.display_name or self.legal_name or f'Contact #{self.pk}'

