from django.db import models


class CompanyContact(models.Model):
    TYPE_PERSON = 'person'
    TYPE_ORGANIZATION = 'organization'
    CONTACT_TYPE_CHOICES = [
        (TYPE_PERSON, 'Person'),
        (TYPE_ORGANIZATION, 'Organization'),
    ]
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
    contact_type = models.CharField(
        max_length=20,
        choices=CONTACT_TYPE_CHOICES,
        default=TYPE_PERSON,
    )
    first_name = models.CharField(max_length=150, blank=True)
    middle_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    display_name = models.CharField(max_length=255, blank=True)
    legal_name = models.CharField(max_length=255, blank=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, blank=True)
    is_company = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        'auth.User',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='company_contacts_created',
    )
    updated_by = models.ForeignKey(
        'auth.User',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='company_contacts_updated',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tenant_company_contact'
        ordering = ['company__name', 'display_name', 'legal_name']

    def __str__(self):
        return self.display_name or self.legal_name or f'Contact #{self.pk}'

    def save(self, *args, **kwargs):
        if self._state.adding and self.is_company:
            self.contact_type = self.TYPE_ORGANIZATION
        self.is_company = self.contact_type == self.TYPE_ORGANIZATION
        if kwargs.get('update_fields') and 'contact_type' in kwargs['update_fields']:
            kwargs['update_fields'] = set(kwargs['update_fields']) | {'is_company'}
        super().save(*args, **kwargs)
