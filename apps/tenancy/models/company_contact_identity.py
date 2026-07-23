from django.db import models


class CompanyContactIdentity(models.Model):
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
    identity_type = models.CharField(max_length=30, choices=IDENTITY_TYPE_CHOICES)
    value = models.CharField(max_length=255)
    is_primary = models.BooleanField(default=False)

    class Meta:
        db_table = 'tenant_company_contact_identity'
        ordering = ['contact__company__name', 'contact__display_name', '-is_primary', 'value']
        constraints = [
            models.UniqueConstraint(
                fields=['contact', 'identity_type', 'value'],
                name='unique_company_contact_identity',
            ),
        ]

    def __str__(self):
        return f'{self.identity_type}: {self.value}'

