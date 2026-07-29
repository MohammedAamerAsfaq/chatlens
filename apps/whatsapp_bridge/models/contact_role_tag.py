from django.db import models


class ContactRoleTag(models.Model):
    ROLE_SUPPLIER = 'supplier'
    ROLE_CUSTOMER = 'customer'

    ROLE_CHOICES = [
        (ROLE_SUPPLIER, 'Supplier'),
        (ROLE_CUSTOMER, 'Customer'),
    ]

    SOURCE_MIGRATION = 'migration'
    SOURCE_MANUAL = 'manual'
    SOURCE_AI_SUGGESTION = 'ai_suggestion'

    SOURCE_CHOICES = [
        (SOURCE_MIGRATION, 'Migration'),
        (SOURCE_MANUAL, 'Manual'),
        (SOURCE_AI_SUGGESTION, 'AI Suggestion'),
    ]

    company = models.ForeignKey(
        'tenancy.Company',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='contact_role_tags',
    )
    contact = models.ForeignKey(
        'whatsapp_bridge.WhatsAppContact',
        on_delete=models.CASCADE,
        related_name='role_tags',
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    source = models.CharField(max_length=30, choices=SOURCE_CHOICES, default=SOURCE_MANUAL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'whatsapp_contact_role_tag'
        constraints = [
            models.UniqueConstraint(fields=['contact', 'role'], name='whatsapp_contact_role_tag_contact_role_uniq'),
        ]
        indexes = [
            models.Index(fields=['company', 'role'], name='wa_role_company_role_idx'),
        ]

    def __str__(self):
        return f'{self.contact_id}:{self.role}'
