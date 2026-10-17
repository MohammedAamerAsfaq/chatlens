from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class PropertyAddress(models.Model):
    company = models.ForeignKey('tenancy.Company', on_delete=models.CASCADE, related_name='property_addresses')
    property = models.OneToOneField('real_estate.Property', on_delete=models.CASCADE, related_name='address')
    country_master = models.ForeignKey(
        'integrations.Country', null=True, blank=True, on_delete=models.PROTECT,
        related_name='property_addresses',
    )
    administrative_area_master = models.ForeignKey(
        'integrations.AdministrativeArea', null=True, blank=True, on_delete=models.PROTECT,
        related_name='property_addresses',
    )
    city_master = models.ForeignKey(
        'integrations.City', null=True, blank=True, on_delete=models.PROTECT,
        related_name='property_addresses',
    )
    locality_master = models.ForeignKey(
        'integrations.Locality', null=True, blank=True, on_delete=models.PROTECT,
        related_name='property_addresses',
    )
    development_master = models.ForeignKey(
        'real_estate.PropertyDevelopment', null=True, blank=True, on_delete=models.PROTECT,
        related_name='property_addresses',
    )
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
        self._validate_geography_hierarchy()

    def _validate_geography_hierarchy(self):
        errors = {}
        if self.administrative_area_master_id and self.country_master_id:
            if self.administrative_area_master.country_id != self.country_master_id:
                errors['administrative_area_master'] = 'The administrative area is outside the country.'
        if self.city_master_id and self.administrative_area_master_id:
            if self.city_master.administrative_area_id != self.administrative_area_master_id:
                errors['city_master'] = 'The city is outside the administrative area.'
        if self.city_master_id and self.country_master_id:
            if self.city_master.country_id != self.country_master_id:
                errors['city_master'] = 'The city is outside the country.'
        if self.locality_master_id:
            if self.country_master_id and self.locality_master.country_id != self.country_master_id:
                errors['locality_master'] = 'The locality is outside the country.'
            if self.city_master_id and self.locality_master.city_id != self.city_master_id:
                errors['locality_master'] = 'The locality is not mapped to the selected city.'
            if self.administrative_area_master_id and self.locality_master.administrative_area_id != self.administrative_area_master_id:
                errors['locality_master'] = 'The locality is outside the administrative area.'
        if self.development_master_id:
            if self.development_master.company_id != self.company_id:
                errors['development_master'] = 'The project or building must belong to this company.'
            if self.locality_master_id and self.development_master.locality_id != self.locality_master_id:
                errors['development_master'] = 'The project or building is outside the locality.'
        if errors:
            raise ValidationError(errors)
