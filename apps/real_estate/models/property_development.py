from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class PropertyDevelopment(models.Model):
    TYPE_PROJECT = 'project'
    TYPE_BUILDING = 'building'
    TYPE_CHOICES = [(TYPE_PROJECT, 'Project'), (TYPE_BUILDING, 'Building')]

    company = models.ForeignKey(
        'tenancy.Company', on_delete=models.CASCADE, related_name='property_developments',
    )
    parent = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.PROTECT, related_name='buildings',
    )
    locality = models.ForeignKey(
        'integrations.Locality', null=True, blank=True, on_delete=models.PROTECT,
        related_name='property_developments',
    )
    development_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    name = models.CharField(max_length=200)
    normalized_name = models.CharField(max_length=200, db_index=True)
    developer_name = models.CharField(max_length=200, blank=True)
    alternate_names = models.JSONField(default=list, blank=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    source = models.CharField(max_length=50, blank=True)
    external_source_id = models.CharField(max_length=255, blank=True)
    is_verified = models.BooleanField(default=False, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'real_estate_property_development'
        ordering = ['development_type', 'name']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'locality', 'development_type', 'normalized_name'],
                condition=Q(is_active=True, locality__isnull=False),
                name='re_active_development_name_uniq',
            ),
            models.UniqueConstraint(
                fields=['company', 'development_type', 'normalized_name'],
                condition=Q(is_active=True, locality__isnull=True),
                name='re_active_development_no_locality_uniq',
            ),
        ]
        indexes = [models.Index(
            fields=['company', 'locality', 'development_type', 'is_active'],
            name='re_development_lookup_idx',
        )]

    def clean(self):
        super().clean()
        if self.parent_id:
            if self.parent.company_id != self.company_id:
                raise ValidationError({'parent': 'The parent must belong to this company.'})
            if self.development_type != self.TYPE_BUILDING:
                raise ValidationError({'parent': 'Only a building can have a parent project.'})
            if self.parent.development_type != self.TYPE_PROJECT:
                raise ValidationError({'parent': 'A building parent must be a project.'})
            if self.locality_id and self.parent.locality_id != self.locality_id:
                raise ValidationError({'locality': 'Building and parent project locality must match.'})

    def __str__(self):
        return self.name
