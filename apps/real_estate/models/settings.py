from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class RealEstateSettings(models.Model):
    GATE_DISABLED = 'disabled'
    GATE_OBSERVATIONAL = 'observational'
    GATE_ENFORCED = 'enforced'
    GATE_MODE_CHOICES = [
        (GATE_DISABLED, 'Disabled'),
        (GATE_OBSERVATIONAL, 'Observational'),
        (GATE_ENFORCED, 'Enforced'),
    ]

    AREA_SQFT = 'sqft'
    AREA_SQM = 'sqm'
    AREA_UNIT_CHOICES = [(AREA_SQFT, 'Square feet'), (AREA_SQM, 'Square metres')]

    company = models.OneToOneField(
        'tenancy.Company',
        on_delete=models.CASCADE,
        related_name='real_estate_settings',
    )
    gate_mode = models.CharField(
        max_length=20,
        choices=GATE_MODE_CHOICES,
        default=GATE_OBSERVATIONAL,
    )
    default_currency = models.CharField(max_length=3, default='AED')
    default_area_unit = models.CharField(
        max_length=10,
        choices=AREA_UNIT_CHOICES,
        default=AREA_SQFT,
    )
    default_country = models.CharField(max_length=100, default='United Arab Emirates')
    minimum_match_score = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        default=0.7000,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'real_estate_settings'

    def __str__(self):
        return f'{self.company.name} Real Estate settings'
