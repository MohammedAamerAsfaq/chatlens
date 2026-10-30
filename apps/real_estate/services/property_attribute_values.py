"""Resolve extracted values through company-owned property attribute masters."""

from decimal import Decimal, InvalidOperation

from apps.real_estate.models import PropertyAttributeDefinition
from apps.real_estate.models.property_attribute import normalize_alias
from apps.real_estate.services.property_attribute_catalog import (
    option_numeric_value, seed_attribute_catalog,
)
from apps.real_estate.services.property_attributes import normalize_number


def resolve_option(company, definition_code, value):
    """Return the canonical option matched by code, label, or an active alias."""
    if value in (None, ''):
        return None
    definition = _definition(company, definition_code)
    if not definition:
        return None
    supplied = normalize_alias(value)
    for option in definition.options.filter(is_active=True).prefetch_related('aliases'):
        labels = [option.code, option.label]
        labels.extend(alias.alias for alias in option.aliases.all() if alias.is_active)
        if supplied in {normalize_alias(label) for label in labels}:
            return option
    return None


def canonical_option_code(company, definition_code, value, *, default=''):
    option = resolve_option(company, definition_code, value)
    return option.code if option else default


def canonical_numeric_value(company, definition_code, value):
    option = resolve_option(company, definition_code, value)
    numeric = option_numeric_value(option)
    if numeric is not None:
        return _compact_decimal(numeric)
    if value in (None, '') or isinstance(value, (dict, list)):
        return None
    try:
        return _compact_decimal(normalize_number(value))
    except (InvalidOperation, ValueError):
        return None


def _compact_decimal(value):
    """Drop storage scale so values fit narrower downstream decimal fields."""
    return Decimal(value).normalize()


def _definition(company, code):
    seed_attribute_catalog(company)
    return PropertyAttributeDefinition.objects.filter(
        company=company, code=code, is_active=True,
    ).first()
