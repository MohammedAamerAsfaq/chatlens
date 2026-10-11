from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from .contracts import ActivityType
from .property import Property


class PropertyCandidate(models.Model):
    REVIEW_CHOICES = [(value, value.title()) for value in ('pending', 'promoted', 'merged', 'rejected')]
    company = models.ForeignKey('tenancy.Company', on_delete=models.CASCADE, related_name='property_candidates')
    opportunity = models.OneToOneField('real_estate.RealEstateOpportunity', on_delete=models.CASCADE, related_name='property_candidate')
    title = models.CharField(max_length=255, blank=True)
    property_type = models.CharField(max_length=30, choices=Property.TYPE_CHOICES, blank=True)
    location_raw = models.CharField(max_length=500, blank=True)
    bedrooms = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True, validators=[MinValueValidator(0)])
    bathrooms = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True, validators=[MinValueValidator(0)])
    area = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)])
    area_unit = models.CharField(max_length=10, choices=Property.AREA_UNIT_CHOICES, default='sqft')
    asking_price = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)])
    currency = models.CharField(max_length=3, default='AED')
    furnishing = models.CharField(max_length=30, choices=Property.FURNISHING_CHOICES, default='unknown')
    available_from = models.DateField(null=True, blank=True)
    description = models.TextField(blank=True)
    raw_extraction = models.JSONField(default=dict, blank=True)
    review_status = models.CharField(max_length=20, choices=REVIEW_CHOICES, default='pending')
    promoted_property = models.ForeignKey('real_estate.Property', null=True, blank=True, on_delete=models.SET_NULL, related_name='source_candidates')
    promoted_listing = models.ForeignKey('real_estate.Listing', null=True, blank=True, on_delete=models.SET_NULL, related_name='source_candidates')
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='reviewed_property_candidates')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'real_estate_property_candidate'
        ordering = ['-updated_at', '-id']

    def clean(self):
        super().clean()
        errors = {}
        if self.opportunity_id and self.opportunity.company_id != self.company_id:
            errors['opportunity'] = 'The opportunity must belong to this company.'
        if self.opportunity_id and self.opportunity.activity_type not in ActivityType.offer_values():
            errors['opportunity'] = 'Only selling or leasing offer opportunities can create candidates.'
        for field in ('promoted_property', 'promoted_listing'):
            linked = getattr(self, field, None) if getattr(self, f'{field}_id', None) else None
            if linked and linked.company_id != self.company_id:
                errors[field] = 'The promoted record must belong to this company.'
        if self.review_status in {'promoted', 'merged'} and not self.promoted_listing_id:
            errors['promoted_listing'] = 'A reviewed candidate must reference its resulting listing.'
        if errors:
            raise ValidationError(errors)
