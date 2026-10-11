from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q


class Listing(models.Model):
    TYPE_CHOICES = [('sale', 'Sale'), ('lease', 'Lease')]
    STATUS_CHOICES = [(value, value.title()) for value in ('draft', 'active', 'paused', 'expired', 'closed')]
    FREQUENCY_CHOICES = [(value, value.replace('_', ' ').title()) for value in (
        'not_applicable', 'yearly', 'monthly', 'quarterly', 'weekly', 'daily',
    )]

    company = models.ForeignKey('tenancy.Company', on_delete=models.CASCADE, related_name='property_listings')
    property = models.ForeignKey('real_estate.Property', on_delete=models.PROTECT, related_name='listings')
    listing_type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    asking_price = models.DecimalField(max_digits=16, decimal_places=2, validators=[MinValueValidator(0)])
    currency = models.CharField(max_length=3, default='AED')
    payment_frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, default='not_applicable')
    deposit = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)])
    commission = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)])
    payment_terms = models.TextField(blank=True)
    available_from = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    assigned_agent = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='assigned_property_listings')
    source_contact = models.ForeignKey('tenancy.CompanyContact', null=True, blank=True, on_delete=models.SET_NULL, related_name='property_listings')
    source_message = models.ForeignKey('whatsapp_bridge.WhatsAppMessage', null=True, blank=True, on_delete=models.SET_NULL, related_name='property_listings')
    published_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    is_verified = models.BooleanField(default=False)
    is_archived = models.BooleanField(default=False)
    archived_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'real_estate_listing'
        ordering = ['-updated_at', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'property', 'listing_type'],
                condition=Q(status='active', is_archived=False),
                name='re_single_active_listing_per_type',
            ),
        ]
        indexes = [models.Index(fields=['company', 'listing_type', 'status', 'is_archived'])]

    def __str__(self):
        return f'{self.get_listing_type_display()}: {self.property}'

    def clean(self):
        super().clean()
        errors = {}
        for field in ('property', 'source_contact'):
            linked = getattr(self, field, None) if getattr(self, f'{field}_id', None) else None
            if linked and linked.company_id != self.company_id:
                errors[field] = f'The {field.replace("_", " ")} must belong to this company.'
        if self.source_message_id:
            communication = self.source_message.account.communication_account
            if not communication or communication.company_id != self.company_id:
                errors['source_message'] = 'The source message must belong to this company.'
        if self.status == 'active' and not self.is_verified:
            errors['status'] = 'An active listing must be verified.'
        if self.listing_type == 'sale' and self.payment_frequency != 'not_applicable':
            errors['payment_frequency'] = 'Sale listings do not use a payment frequency.'
        if self.listing_type == 'lease' and self.payment_frequency == 'not_applicable':
            errors['payment_frequency'] = 'Lease listings require a payment frequency.'
        if self.published_at and self.expires_at and self.expires_at < self.published_at:
            errors['expires_at'] = 'Expiry cannot be before publication.'
        if self.assigned_agent_id:
            from apps.tenancy.models import CompanyMembership
            if not CompanyMembership.objects.filter(company_id=self.company_id, user_id=self.assigned_agent_id, is_active=True).exists():
                errors['assigned_agent'] = 'The assigned agent must be an active company member.'
        if errors:
            raise ValidationError(errors)
