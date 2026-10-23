from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from .contracts import AreaUnit


class RealEstateSettings(models.Model):
    GATE_DISABLED = 'disabled'
    GATE_OBSERVATIONAL = 'observational'
    GATE_ENFORCED = 'enforced'
    GATE_MODE_CHOICES = [
        (GATE_DISABLED, 'Disabled'),
        (GATE_OBSERVATIONAL, 'Observational'),
        (GATE_ENFORCED, 'Enforced'),
    ]

    AREA_SQFT = AreaUnit.SQUARE_FEET
    AREA_SQM = AreaUnit.SQUARE_METRES
    AREA_UNIT_CHOICES = AreaUnit.choices

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
    # Ordered list of field ids from frontend/src/features/realEstate/cardFields.js to
    # show on Opportunity Board cards. Empty list means "use the card's built-in default
    # layout" — this is deliberately a plain list of opaque ids rather than a richer
    # structure so the frontend registry stays the single source of truth for what each
    # id means/renders as.
    card_field_config = models.JSONField(default=list, blank=True)
    # {"statuses": [...RealEstateOpportunity.STATUS_CHOICES ids], "max_inline": int} —
    # which status values get a quick-set button in the card footer, in what order, and
    # how many render inline before the rest collapse into a "More" dropdown.
    card_action_config = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'real_estate_settings'

    def __str__(self):
        return f'{self.company.name} Real Estate settings'
