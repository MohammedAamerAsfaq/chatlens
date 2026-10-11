from datetime import date
from decimal import Decimal, InvalidOperation

from django.db import transaction

from apps.real_estate.models import (
    ActivityType,
    Property,
    PropertyCandidate,
    PropertyRequirement,
    RealEstateSettings,
)


@transaction.atomic
def project_extraction(opportunity, parsed):
    if not opportunity.activity_type:
        return None
    settings, _ = RealEstateSettings.objects.get_or_create(company=opportunity.company)
    payload = parsed.get('property') or {}
    if opportunity.activity_type in ActivityType.requirement_values():
        PropertyCandidate.objects.filter(opportunity=opportunity).delete()
        return _project_requirement(opportunity, payload, parsed, settings)
    PropertyRequirement.objects.filter(opportunity=opportunity).delete()
    return _project_candidate(opportunity, payload, parsed, settings)


def _project_requirement(opportunity, payload, parsed, settings):
    budget = _mapping(payload.get('budget'))
    area = _mapping(payload.get('area'))
    defaults = {
        'company': opportunity.company,
        'acceptable_locations': _list(payload.get('locations') or payload.get('location')),
        'acceptable_property_types': _property_types(payload),
        'bedrooms_min': _decimal(payload.get('bedrooms_min') or payload.get('bedrooms')),
        'bedrooms_max': _decimal(payload.get('bedrooms_max') or payload.get('bedrooms')),
        'bathrooms_min': _decimal(payload.get('bathrooms_min') or payload.get('bathrooms')),
        'bathrooms_max': _decimal(payload.get('bathrooms_max') or payload.get('bathrooms')),
        'area_min': _decimal(payload.get('area_min') or area.get('min')),
        'area_max': _decimal(payload.get('area_max') or area.get('max')),
        'area_unit': _choice(payload.get('area_unit') or area.get('unit'), {'sqft', 'sqm'}, settings.default_area_unit),
        'budget_min': _decimal(payload.get('budget_min') or budget.get('min')),
        'budget_max': _decimal(payload.get('budget_max') or budget.get('max')),
        'currency': str(payload.get('currency') or budget.get('currency') or settings.default_currency).upper()[:3],
        'furnishing': _furnishing(payload.get('furnishing')),
        'timeframe': str(payload.get('timeframe') or '')[:255],
        'required_amenities': _list(payload.get('required_amenities')),
        'preferred_amenities': _list(payload.get('preferred_amenities') or payload.get('amenities')),
        'free_form_constraints': str(payload.get('constraints') or ''),
        'extraction_confidence': _decimal(parsed.get('confidence')),
        'raw_extraction': payload,
    }
    requirement, _ = PropertyRequirement.objects.update_or_create(opportunity=opportunity, defaults=defaults)
    requirement.full_clean()
    requirement.save()
    return requirement


def _project_candidate(opportunity, payload, parsed, settings):
    price = _mapping(payload.get('price'))
    defaults = {
        'company': opportunity.company,
        'title': str(payload.get('title') or parsed.get('summary') or '')[:255],
        'property_type': _property_type(payload.get('property_type')),
        'location_raw': str(payload.get('location') or _first(payload.get('locations')) or '')[:500],
        'bedrooms': _decimal(payload.get('bedrooms')),
        'bathrooms': _decimal(payload.get('bathrooms')),
        'area': _decimal(payload.get('area') if not isinstance(payload.get('area'), dict) else payload['area'].get('value')),
        'area_unit': _choice(payload.get('area_unit'), {'sqft', 'sqm'}, settings.default_area_unit),
        'asking_price': _decimal(payload.get('asking_price') or price.get('value') or price.get('amount')),
        'currency': str(payload.get('currency') or price.get('currency') or settings.default_currency).upper()[:3],
        'furnishing': _furnishing(payload.get('furnishing')),
        'available_from': _date(payload.get('available_from')),
        'description': str(payload.get('description') or opportunity.original_message or ''),
        'raw_extraction': payload,
    }
    candidate, created = PropertyCandidate.objects.update_or_create(opportunity=opportunity, defaults=defaults)
    if not created and candidate.review_status != 'pending':
        candidate.review_status = 'pending'
        candidate.promoted_property = None
        candidate.promoted_listing = None
        candidate.reviewed_by = None
        candidate.reviewed_at = None
    candidate.full_clean()
    candidate.save()
    return candidate


def _mapping(value):
    return value if isinstance(value, dict) else {}


def _list(value):
    if value in (None, ''):
        return []
    return [str(item).strip() for item in (value if isinstance(value, list) else [value]) if str(item).strip()]


def _first(value):
    values = _list(value)
    return values[0] if values else ''


def _decimal(value):
    if value in (None, '') or isinstance(value, (dict, list)):
        return None
    try:
        return Decimal(str(value).replace(',', '').strip())
    except (InvalidOperation, ValueError):
        return None


def _date(value):
    try:
        return date.fromisoformat(str(value)) if value else None
    except ValueError:
        return None


def _choice(value, allowed, default):
    normalized = str(value or '').lower().replace(' ', '_')
    return normalized if normalized in allowed else default


def _furnishing(value):
    return _choice(value, {item[0] for item in Property.FURNISHING_CHOICES}, 'unknown')


def _property_type(value):
    return _choice(value, {item[0] for item in Property.TYPE_CHOICES}, 'other')


def _property_types(payload):
    values = _list(payload.get('property_types') or payload.get('property_type'))
    return [_property_type(value) for value in values]
