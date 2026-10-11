from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class PropertyAddress(models.Model):
    company = models.ForeignKey('tenancy.Company', on_delete=models.CASCADE, related_name='property_addresses')
    property = models.OneToOneField('real_estate.Property', on_delete=models.CASCADE, related_name='address')
    country = models.CharField(max_length=100, blank=True)
    state_region = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)
    community = models.CharField(max_length=150, blank=True)
    project_building = models.CharField(max_length=200, blank=True)
    street = models.CharField(max_length=255, blank=True)
    unit_number = models.CharField(max_length=80, blank=True)
    postal_code = models.CharField(max_length=30, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, validators=[MinValueValidator(-90), MaxValueValidator(90)])
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, validators=[MinValueValidator(-180), MaxValueValidator(180)])
    normalized_location = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'real_estate_property_address'

    def clean(self):
        super().clean()
        if self.property_id and self.property.company_id != self.company_id:
            raise ValidationError({'property': 'The property must belong to this company.'})
