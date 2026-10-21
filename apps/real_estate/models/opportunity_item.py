from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from .contracts import AreaUnit, OwnershipEligibility, TenureType
from .property import Property


class OpportunityItem(models.Model):
    KIND_DEMAND = 'demand'
    KIND_SUPPLY = 'supply'
    KIND_CHOICES = [(KIND_DEMAND, 'Demand'), (KIND_SUPPLY, 'Supply')]
    AMOUNT_BUDGET = 'budget'
    AMOUNT_ASKING = 'asking'
    AMOUNT_CHOICES = [(AMOUNT_BUDGET, 'Budget'), (AMOUNT_ASKING, 'Asking price')]
    MATCH_UNMATCHED = 'unmatched'
    MATCH_SUGGESTED = 'suggested'
    MATCH_LINKED = 'linked'
    MATCH_REJECTED = 'rejected'
    MATCH_CHOICES = [
        (MATCH_UNMATCHED, 'Unmatched'),
        (MATCH_SUGGESTED, 'Suggested'),
        (MATCH_LINKED, 'Linked'),
        (MATCH_REJECTED, 'Rejected'),
    ]
    LINK_NONE = 'none'
    LINK_AUTOMATIC = 'automatic'
    LINK_MANUAL = 'manual'
    LINK_CHOICES = [
        (LINK_NONE, 'None'), (LINK_AUTOMATIC, 'Automatic'), (LINK_MANUAL, 'Manual'),
    ]

    company = models.ForeignKey(
        'tenancy.Company', on_delete=models.CASCADE, related_name='real_estate_opportunity_items',
    )
    opportunity = models.ForeignKey(
        'real_estate.RealEstateOpportunity', on_delete=models.CASCADE, related_name='items',
    )
    sequence = models.PositiveSmallIntegerField(default=1)
    item_kind = models.CharField(max_length=10, choices=KIND_CHOICES)
    title = models.CharField(max_length=255, blank=True)
    property_type = models.ForeignKey(
        'real_estate.PropertyType', null=True, blank=True, on_delete=models.PROTECT,
        related_name='opportunity_items',
    )
    property_type_label = models.CharField(max_length=100, blank=True)
    locations = models.JSONField(default=list, blank=True)
    location_raw = models.CharField(max_length=500, blank=True)
    bedrooms_min = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    bedrooms_max = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    bathrooms_min = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    bathrooms_max = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    area_min = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    area_max = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    area_unit = models.CharField(max_length=10, choices=AreaUnit.choices, default=AreaUnit.SQUARE_FEET)
    amount_min = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    amount_max = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    amount_role = models.CharField(max_length=10, choices=AMOUNT_CHOICES)
    currency = models.CharField(max_length=3, default='AED')
    furnishing = models.CharField(max_length=30, choices=Property.FURNISHING_CHOICES, default='unknown')
    ownership_eligibility = models.CharField(
        max_length=20, choices=OwnershipEligibility.choices, default=OwnershipEligibility.ALL,
    )
    tenure_type = models.CharField(max_length=20, choices=TenureType.choices, blank=True, default='')
    timeframe = models.CharField(max_length=255, blank=True)
    amenities = models.JSONField(default=list, blank=True)
    attributes = models.JSONField(default=dict, blank=True)
    description = models.TextField(blank=True)
    raw_extraction = models.JSONField(default=dict, blank=True)
    extraction_confidence = models.DecimalField(
        max_digits=5, decimal_places=4, null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
    )
    property = models.ForeignKey(
        'real_estate.Property', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='opportunity_items',
    )
    match_status = models.CharField(max_length=20, choices=MATCH_CHOICES, default=MATCH_UNMATCHED)
    match_confidence = models.DecimalField(
        max_digits=5, decimal_places=4, null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
    )
    link_method = models.CharField(max_length=12, choices=LINK_CHOICES, default=LINK_NONE)
    linked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='linked_real_estate_opportunity_items',
    )
    linked_at = models.DateTimeField(null=True, blank=True)
    legacy_requirement = models.OneToOneField(
        'real_estate.PropertyRequirement', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='opportunity_item',
    )
    legacy_candidate = models.OneToOneField(
        'real_estate.PropertyCandidate', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='opportunity_item',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'real_estate_opportunity_item'
        ordering = ['sequence', 'id']
        constraints = [models.UniqueConstraint(
            fields=['opportunity', 'sequence'], name='re_opportunity_item_sequence_uniq',
        )]
        indexes = [
            models.Index(fields=['company', 'match_status'], name='re_item_match_status_idx'),
            models.Index(fields=['company', 'property'], name='re_item_property_idx'),
        ]

    def clean(self):
        super().clean()
        errors = {}
        for field in ('opportunity', 'property_type', 'property'):
            value = getattr(self, field, None) if getattr(self, f'{field}_id', None) else None
            if value and value.company_id != self.company_id:
                errors[field] = 'The linked record must belong to this company.'
        if self.match_status in {self.MATCH_SUGGESTED, self.MATCH_LINKED} and not self.property_id:
            errors['property'] = 'Suggested and linked items require a property.'
        if not isinstance(self.locations, list):
            errors['locations'] = 'Locations must be a list.'
        if not isinstance(self.amenities, list):
            errors['amenities'] = 'Amenities must be a list.'
        if not isinstance(self.attributes, dict):
            errors['attributes'] = 'Attributes must be an object.'
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f'Opportunity #{self.opportunity_id} item {self.sequence}'
