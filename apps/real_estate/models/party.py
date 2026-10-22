from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models


class Party(models.Model):
    KIND_CHOICES = [('person', 'Person'), ('organization', 'Organization')]

    company = models.ForeignKey('tenancy.Company', on_delete=models.CASCADE, related_name='real_estate_parties')
    party_kind = models.CharField(max_length=20, choices=KIND_CHOICES, default='person')
    first_name = models.CharField(max_length=100, blank=True)
    middle_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    organization_name = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=50, blank=True)
    alternate_phone = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    address_line_1 = models.CharField(max_length=255, blank=True)
    address_line_2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state_region = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=30, blank=True)
    country = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'real_estate_party'
        ordering = ['organization_name', 'first_name', 'last_name', 'id']
        indexes = [
            models.Index(fields=['company', 'is_active'], name='re_party_active_idx'),
            models.Index(fields=['company', 'phone'], name='re_party_phone_idx'),
        ]

    @property
    def display_name(self):
        person_name = ' '.join(filter(None, [self.first_name, self.middle_name, self.last_name]))
        return self.organization_name or person_name or f'Party #{self.pk}'

    def __str__(self):
        return self.display_name

    def clean(self):
        super().clean()
        if not self.organization_name and not any((self.first_name, self.middle_name, self.last_name)):
            raise ValidationError({'first_name': 'Enter a person name or an organization name.'})


class PropertyPartyAssociation(models.Model):
    ROLE_CHOICES = [
        ('current_owner', 'Current owner'),
        ('previous_owner', 'Previous owner'),
        ('landlord', 'Landlord'),
        ('tenant', 'Tenant'),
        ('authorized_representative', 'Authorized representative'),
        ('developer', 'Developer'),
        ('broker', 'Broker'),
        ('other', 'Other'),
    ]

    company = models.ForeignKey('tenancy.Company', on_delete=models.CASCADE, related_name='property_party_associations')
    property = models.ForeignKey('real_estate.Property', on_delete=models.CASCADE, related_name='party_associations')
    party = models.ForeignKey(Party, on_delete=models.PROTECT, related_name='property_associations')
    relationship_type = models.CharField(max_length=40, choices=ROLE_CHOICES, default='current_owner')
    ownership_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    started_on = models.DateField(null=True, blank=True)
    ended_on = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'real_estate_property_party'
        ordering = ['relationship_type', 'party_id']
        constraints = [models.UniqueConstraint(
            fields=['property', 'party', 'relationship_type'],
            name='re_property_party_role_uniq',
        )]
        indexes = [models.Index(
            fields=['company', 'property', 'is_active'], name='re_property_party_active_idx',
        )]

    def clean(self):
        super().clean()
        if self.property_id and self.property.company_id != self.company_id:
            raise ValidationError({'property': 'The property must belong to this company.'})
        if self.party_id and self.party.company_id != self.company_id:
            raise ValidationError({'party': 'The party must belong to this company.'})
        if self.started_on and self.ended_on and self.ended_on < self.started_on:
            raise ValidationError({'ended_on': 'The end date cannot precede the start date.'})

    def __str__(self):
        return f'{self.party} - {self.get_relationship_type_display()} - {self.property}'
