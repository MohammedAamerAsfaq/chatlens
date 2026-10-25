from decimal import Decimal, InvalidOperation

from django.db import transaction

from apps.real_estate.models import (
    ActivityType, AreaUnit, OpportunityItem, OwnershipEligibility, Property,
    TenureType,
)
from apps.real_estate.services.property_attributes import normalize_attributes
from apps.real_estate.services.property_types import resolve_property_type


@transaction.atomic
def sync_extracted_items(
    opportunity, parsed, settings, *, legacy_requirement=None, legacy_candidate=None,
):
    payloads = parsed.get('properties') or []
    if not payloads and parsed.get('property'):
        payloads = [parsed['property']]
    kind = (
        OpportunityItem.KIND_DEMAND
        if opportunity.activity_type in ActivityType.requirement_values()
        else OpportunityItem.KIND_SUPPLY
    )
    items = []
    for sequence, payload in enumerate(payloads, 1):
        values = _item_values(opportunity, payload, parsed, settings, kind)
        if sequence == 1:
            values['legacy_requirement'] = legacy_requirement
            values['legacy_candidate'] = legacy_candidate
        item = _upsert(opportunity, sequence, values)
        if item.match_status == OpportunityItem.MATCH_UNMATCHED:
            _link_exact_reference(item)
        items.append(item)
    OpportunityItem.objects.filter(
        opportunity=opportunity, sequence__gt=len(payloads),
        match_status__in=[OpportunityItem.MATCH_UNMATCHED, OpportunityItem.MATCH_REJECTED],
    ).delete()
    return items


def _item_values(opportunity, payload, parsed, settings, kind):
    payload = payload if isinstance(payload, dict) else {}
    type_labels = _strings(payload.get('property_types') or payload.get('property_type'))
    # Use the first label whenever at least one was extracted (previously required
    # exactly one, so 0 or 2+ labels both silently dropped to no lookup at all - the
    # common real case is 0 labels, e.g. a listing whose extraction never named a
    # property type, which is exactly when SUPPLY items most need the fallback below).
    property_type = resolve_property_type(
        opportunity.company, type_labels[0] if type_labels else None,
        fallback=kind == OpportunityItem.KIND_SUPPLY,
    )
    locations = _strings(payload.get('locations') or payload.get('location'))
    area = _mapping(payload.get('area'))
    money = _mapping(payload.get('budget') if kind == OpportunityItem.KIND_DEMAND else payload.get('price'))
    single_area = payload.get('area') if not isinstance(payload.get('area'), dict) else area.get('value')
    if kind == OpportunityItem.KIND_DEMAND:
        amount = payload.get('budget_min') or money.get('min')
        amount_max = payload.get('budget_max') or money.get('max')
    else:
        amount = payload.get('asking_price') or money.get('amount') or money.get('value')
        amount_max = money.get('max') or amount
    attributes = payload.get('attributes') if isinstance(payload.get('attributes'), dict) else {}
    if property_type:
        attributes = normalize_attributes(property_type, attributes, strict=False)
    return {
        'company': opportunity.company,
        'item_kind': kind,
        'title': str(payload.get('title') or parsed.get('summary') or '')[:255],
        'property_type': property_type,
        'property_type_label': ', '.join(type_labels)[:100],
        'locations': locations,
        'location_raw': str(payload.get('location') or (locations[0] if locations else ''))[:500],
        'bedrooms_min': _number(payload.get('bedrooms_min') or payload.get('bedrooms')),
        'bedrooms_max': _number(payload.get('bedrooms_max') or payload.get('bedrooms')),
        'bathrooms_min': _number(payload.get('bathrooms_min') or payload.get('bathrooms')),
        'bathrooms_max': _number(payload.get('bathrooms_max') or payload.get('bathrooms')),
        'area_min': _number(payload.get('area_min') or area.get('min') or single_area),
        'area_max': _number(payload.get('area_max') or area.get('max') or single_area),
        'area_unit': _choice(
            payload.get('area_unit') or area.get('unit'), AreaUnit.values, settings.default_area_unit,
        ),
        'amount_min': _number(amount),
        'amount_max': _number(amount_max),
        'amount_role': (
            OpportunityItem.AMOUNT_BUDGET
            if kind == OpportunityItem.KIND_DEMAND else OpportunityItem.AMOUNT_ASKING
        ),
        'currency': str(payload.get('currency') or money.get('currency') or settings.default_currency).upper()[:3],
        'furnishing': _choice(payload.get('furnishing'), dict(Property.FURNISHING_CHOICES), 'unknown'),
        'ownership_eligibility': _choice(
            payload.get('ownership_eligibility'), OwnershipEligibility.values, OwnershipEligibility.ALL,
        ),
        'tenure_type': _choice(payload.get('tenure_type'), TenureType.values, ''),
        'timeframe': str(payload.get('timeframe') or '')[:255],
        'amenities': _unique(_strings(payload.get('required_amenities')) + _strings(
            payload.get('preferred_amenities') or payload.get('amenities'),
        )),
        'attributes': attributes,
        'description': str(
            payload.get('description') or payload.get('free_form_constraints')
            or payload.get('constraints') or ''
        ),
        'raw_extraction': payload,
        'extraction_confidence': _number(parsed.get('confidence')),
        'legacy_requirement': None,
        'legacy_candidate': None,
    }


def _upsert(opportunity, sequence, values):
    item = OpportunityItem.objects.select_for_update().filter(
        opportunity=opportunity, sequence=sequence,
    ).first() or OpportunityItem(opportunity=opportunity, sequence=sequence)
    for field, value in values.items():
        setattr(item, field, value)
    item.full_clean()
    item.save()
    return item


def _link_exact_reference(item):
    reference = str(item.raw_extraction.get('reference_code') or '').strip()
    if not reference:
        return
    match = Property.objects.filter(
        company=item.company, reference_code__iexact=reference, is_archived=False,
    ).first()
    if not match:
        return
    item.property = match
    item.match_status = OpportunityItem.MATCH_LINKED
    item.match_confidence = 1
    item.link_method = OpportunityItem.LINK_AUTOMATIC
    item.save(update_fields=['property', 'match_status', 'match_confidence', 'link_method', 'updated_at'])


def _mapping(value):
    return value if isinstance(value, dict) else {}


def _strings(value):
    if value in (None, ''):
        return []
    values = value if isinstance(value, list) else [value]
    return [str(item).strip() for item in values if str(item).strip()]


def _number(value):
    if value in (None, '') or isinstance(value, (dict, list)):
        return None
    try:
        return Decimal(str(value).replace(',', '').strip())
    except (InvalidOperation, ValueError):
        return None


def _choice(value, allowed, default):
    normalized = str(value or '').strip().lower().replace(' ', '_')
    return normalized if normalized in allowed else default


def _unique(values):
    return list(dict.fromkeys(value for value in values if value))
