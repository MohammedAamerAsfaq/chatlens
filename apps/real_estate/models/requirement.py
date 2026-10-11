from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from .contracts import ActivityType
from .property import Property


class PropertyRequirement(models.Model):
    REVIEW_CHOICES = [(value, value.title()) for value in ('pending', 'approved', 'rejected')]
    company = models.ForeignKey('tenancy.Company', on_delete=models.CASCADE, related_name='property_requirements')
    opportunity = models.OneToOneField('real_estate.RealEstateOpportunity', on_delete=models.CASCADE, related_name='requirement')
    acceptable_locations = models.JSONField(default=list, blank=True)
    acceptable_property_types = models.JSONField(default=list, blank=True)
    bedrooms_min = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True, validators=[MinValueValidator(0)])
    bedrooms_max = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True, validators=[MinValueValidator(0)])
    bathrooms_min = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True, validators=[MinValueValidator(0)])
    bathrooms_max = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True, validators=[MinValueValidator(0)])
    area_min = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)])
    area_max = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)])
    area_unit = models.CharField(max_length=10, choices=Property.AREA_UNIT_CHOICES, default='sqft')
    budget_min = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)])
    budget_max = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)])
    currency = models.CharField(max_length=3, default='AED')
    furnishing = models.CharField(max_length=30, choices=Property.FURNISHING_CHOICES, default='unknown')
    timeframe = models.CharField(max_length=255, blank=True)
    required_amenities = models.JSONField(default=list, blank=True)
    preferred_amenities = models.JSONField(default=list, blank=True)
    free_form_constraints = models.TextField(blank=True)
    extraction_confidence = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(1)])
    review_status = models.CharField(max_length=20, choices=REVIEW_CHOICES, default='pending')
    raw_extraction = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'real_estate_property_requirement'
        ordering = ['-updated_at', '-id']

    def clean(self):
        super().clean()
        errors = {}
        if self.opportunity_id and self.opportunity.company_id != self.company_id:
            errors['opportunity'] = 'The opportunity must belong to this company.'
        if self.opportunity_id and self.opportunity.activity_type not in ActivityType.requirement_values():
            errors['opportunity'] = 'Only buying or leasing inquiry opportunities can have requirements.'
        for low, high in (('bedrooms_min', 'bedrooms_max'), ('bathrooms_min', 'bathrooms_max'), ('area_min', 'area_max'), ('budget_min', 'budget_max')):
            if getattr(self, low) is not None and getattr(self, high) is not None and getattr(self, low) > getattr(self, high):
                errors[high] = f'{high.replace("_", " ").title()} cannot be below the minimum.'
        for field in ('acceptable_locations', 'acceptable_property_types', 'required_amenities', 'preferred_amenities'):
            if not isinstance(getattr(self, field), list):
                errors[field] = 'This value must be a list.'
        if errors:
            raise ValidationError(errors)
