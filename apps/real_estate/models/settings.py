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

    # How extraction judges whether an amount is a sale price or a year's rent when the
    # message does not say (see services/price_check.py).
    PRICE_CHECK_OFF = 'off'
    PRICE_CHECK_MODEL = 'model_knowledge'
    PRICE_CHECK_WEB = 'web_search'
    PRICE_CHECK_TABLE = 'reference_table'
    PRICE_CHECK_CHOICES = [
        (PRICE_CHECK_OFF, 'Off'),
        (PRICE_CHECK_MODEL, "AI's own market knowledge"),
        (PRICE_CHECK_WEB, 'Live web search (OpenRouter)'),
        (PRICE_CHECK_TABLE, 'Company price table'),
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
    price_check_mode = models.CharField(
        max_length=20, choices=PRICE_CHECK_CHOICES, default=PRICE_CHECK_MODEL,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'real_estate_settings'

    def __str__(self):
        return f'{self.company.name} Real Estate settings'


class MarketPriceReference(models.Model):
    """A typical sale price range the company keeps for an area (and optionally a property
    type and bedroom count), given to extraction when price_check_mode is reference_table."""

    company = models.ForeignKey(
        'tenancy.Company', on_delete=models.CASCADE, related_name='real_estate_market_prices',
    )
    location = models.CharField(max_length=200, help_text='Area, community or building as brokers write it.')
    property_type = models.ForeignKey(
        'real_estate.PropertyType', null=True, blank=True, on_delete=models.PROTECT,
        related_name='market_prices',
    )
    bedrooms = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    sale_price_min = models.DecimalField(max_digits=16, decimal_places=2)
    sale_price_max = models.DecimalField(max_digits=16, decimal_places=2)
    currency = models.CharField(max_length=3, default='AED')
    notes = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'real_estate_market_price'
        ordering = ['location', 'property_type__name', 'bedrooms']

    def __str__(self):
        return f'{self.location} {self.sale_price_min}-{self.sale_price_max} {self.currency}'
