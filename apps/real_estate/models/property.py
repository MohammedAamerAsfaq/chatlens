from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q

from .contracts import AreaUnit


class Property(models.Model):
    STATUS_CHOICES = [(value, value.replace('_', ' ').title()) for value in (
        'draft', 'available', 'reserved', 'sold', 'leased', 'inactive',
    )]
    FURNISHING_CHOICES = [(value, value.replace('_', ' ').title()) for value in (
        'unknown', 'unfurnished', 'semi_furnished', 'furnished',
    )]
    COMPLETION_CHOICES = [(value, value.replace('_', ' ').title()) for value in (
        'unknown', 'ready', 'off_plan', 'under_construction',
    )]
    AREA_UNIT_CHOICES = AreaUnit.choices

    company = models.ForeignKey('tenancy.Company', on_delete=models.CASCADE, related_name='properties')
    reference_code = models.CharField(max_length=80, blank=True)
    title = models.CharField(max_length=255)
    property_type = models.ForeignKey(
        'real_estate.PropertyType', on_delete=models.PROTECT, related_name='properties',
    )
    description = models.TextField(blank=True)
    bedrooms = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True, validators=[MinValueValidator(0)])
    bathrooms = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True, validators=[MinValueValidator(0)])
    built_up_area = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)])
    plot_area = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)])
    area_unit = models.CharField(max_length=10, choices=AREA_UNIT_CHOICES, default='sqft')
    furnishing = models.CharField(max_length=30, choices=FURNISHING_CHOICES, default='unknown')
    completion_status = models.CharField(max_length=30, choices=COMPLETION_CHOICES, default='unknown')
    developer = models.CharField(max_length=255, blank=True)
    project_name = models.CharField(max_length=255, blank=True)
    completion_year = models.PositiveSmallIntegerField(null=True, blank=True)
    availability_status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='draft')
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='assigned_properties')
    source = models.CharField(max_length=50, blank=True)
    external_source_id = models.CharField(max_length=255, blank=True)
    is_archived = models.BooleanField(default=False)
    archived_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'real_estate_property'
        ordering = ['-updated_at', '-id']
        constraints = [
            models.UniqueConstraint(fields=['company', 'reference_code'], condition=~Q(reference_code=''), name='re_property_company_reference_uniq'),
            models.UniqueConstraint(fields=['company', 'source', 'external_source_id'], condition=~Q(external_source_id=''), name='re_property_external_source_uniq'),
        ]
        indexes = [models.Index(
            fields=['company', 'property_type', 'availability_status'],
            name='re_property_type_status_idx',
        )]

    def __str__(self):
        return self.title

    def clean(self):
        super().clean()
        if self.property_type_id and self.property_type.company_id != self.company_id:
            raise ValidationError({'property_type': 'The property type must belong to this company.'})
        if not self.assigned_to_id:
            return
        from apps.tenancy.models import CompanyMembership
        if not CompanyMembership.objects.filter(company_id=self.company_id, user_id=self.assigned_to_id, is_active=True).exists():
            raise ValidationError({'assigned_to': 'The assigned user must be an active company member.'})
