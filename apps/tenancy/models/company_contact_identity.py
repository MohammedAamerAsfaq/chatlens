from django.db import models

from apps.tenancy.services.identity_normalization import normalize_identity


class CompanyContactIdentity(models.Model):
    SOURCE_MANUAL = 'manual'
    SOURCE_WHATSAPP = 'whatsapp'
    SOURCE_INTEGRATION = 'integration'
    SOURCE_IMPORT = 'import'
    SOURCE_TYPE_CHOICES = [
        (SOURCE_MANUAL, 'Manual'),
        (SOURCE_WHATSAPP, 'WhatsApp'),
        (SOURCE_INTEGRATION, 'Integration'),
        (SOURCE_IMPORT, 'Import'),
    ]
    TYPE_PHONE = 'phone'
    TYPE_EMAIL = 'email'
    TYPE_WHATSAPP_JID = 'whatsapp_jid'
    TYPE_TELEGRAM_HANDLE = 'telegram_handle'
    TYPE_DISCORD_HANDLE = 'discord_handle'
    TYPE_OTHER = 'other'

    IDENTITY_TYPE_CHOICES = [
        (TYPE_PHONE, 'Phone'),
        (TYPE_EMAIL, 'Email'),
        (TYPE_WHATSAPP_JID, 'WhatsApp JID'),
        (TYPE_TELEGRAM_HANDLE, 'Telegram Handle'),
        (TYPE_DISCORD_HANDLE, 'Discord Handle'),
        (TYPE_OTHER, 'Other'),
    ]

    contact = models.ForeignKey(
        'tenancy.CompanyContact',
        on_delete=models.CASCADE,
        related_name='identities',
    )
    company = models.ForeignKey(
        'tenancy.Company',
        on_delete=models.CASCADE,
        related_name='contact_identities',
    )
    identity_type = models.CharField(max_length=30, choices=IDENTITY_TYPE_CHOICES)
    value = models.CharField(max_length=255)
    normalized_value = models.CharField(max_length=255, db_index=True)
    label = models.CharField(max_length=100, blank=True)
    is_primary = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    source_type = models.CharField(
        max_length=20,
        choices=SOURCE_TYPE_CHOICES,
        default=SOURCE_MANUAL,
    )
    source_reference = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tenant_company_contact_identity'
        ordering = ['contact__company__name', 'contact__display_name', '-is_primary', 'value']
        constraints = [
            models.UniqueConstraint(
                fields=['contact', 'identity_type', 'value'],
                name='unique_company_contact_identity',
            ),
        ]
        indexes = [
            models.Index(
                fields=['company', 'identity_type', 'normalized_value'],
                name='tenant_identity_lookup_idx',
            ),
        ]

    def save(self, *args, **kwargs):
        if not self.contact_id:
            raise ValueError('A contact identity must belong to a contact.')
        contact_company_id = self.contact.company_id
        if self.company_id and self.company_id != contact_company_id:
            raise ValueError('Contact identity company must match its contact company.')
        self.company_id = contact_company_id
        self.normalized_value = normalize_identity(self.identity_type, self.value)
        if not self.normalized_value:
            raise ValueError('Contact identity value cannot normalize to an empty value.')
        if kwargs.get('update_fields'):
            kwargs['update_fields'] = set(kwargs['update_fields']) | {
                'company', 'normalized_value', 'updated_at',
            }
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.identity_type}: {self.value}'
