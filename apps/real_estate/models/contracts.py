from django.db import models


class ActivityType(models.TextChoices):
    BUYING = 'buying', 'Buying'
    SELLING = 'selling', 'Selling'
    LEASING_INQUIRY = 'leasing_inquiry', 'Leasing Inquiry'
    LEASING_OFFER = 'leasing_offer', 'Leasing Offer'

    @classmethod
    def requirement_values(cls):
        return {cls.BUYING, cls.LEASING_INQUIRY}

    @classmethod
    def offer_values(cls):
        return {cls.SELLING, cls.LEASING_OFFER}


class ClassificationStatus(models.TextChoices):
    CLASSIFIED = 'classified', 'Classified'
    NEEDS_REVIEW = 'needs_review', 'Needs Review'
    NOT_REAL_ESTATE = 'not_real_estate', 'Not Real Estate'


class ClassificationDecision(models.TextChoices):
    BUYING = ActivityType.BUYING, 'Buying'
    SELLING = ActivityType.SELLING, 'Selling'
    LEASING_INQUIRY = ActivityType.LEASING_INQUIRY, 'Leasing Inquiry'
    LEASING_OFFER = ActivityType.LEASING_OFFER, 'Leasing Offer'
    NOT_REAL_ESTATE = ClassificationStatus.NOT_REAL_ESTATE, 'Not Real Estate'
    NEEDS_REVIEW = ClassificationStatus.NEEDS_REVIEW, 'Needs Review'


class AreaUnit(models.TextChoices):
    SQUARE_FEET = 'sqft', 'Square feet'
    SQUARE_METRES = 'sqm', 'Square metres'
    SQUARE_YARDS = 'sqyd', 'Square yards'
    ACRES = 'acre', 'Acres'
    HECTARES = 'hectare', 'Hectares'


class MarketScope(models.TextChoices):
    LOCAL = 'local', 'Local'
    REGIONAL = 'regional', 'Regional'
    INTERNATIONAL = 'international', 'International'


class OwnershipEligibility(models.TextChoices):
    LOCALS_ONLY = 'locals_only', 'Locals Only'
    GCC_ONLY = 'gcc_only', 'GCC Only'
    ALL = 'all', 'All'


class TenureType(models.TextChoices):
    FREEHOLD = 'freehold', 'Freehold'
    LONG_LEASE = 'long_lease', 'Long Lease'
    LEASE_99_YEAR = 'lease_99_year', '99 Year Lease'


class InventorySourceType(models.TextChoices):
    OWN = 'own', 'Own Inventory'
    AUTHORIZED = 'authorized', 'Authorized Inventory'
    FLOATING = 'floating', 'Floating Inventory'
