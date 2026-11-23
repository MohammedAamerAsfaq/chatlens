"""Find the other side of an opportunity: sellers for a buyer, buyers for a seller,
landlords for a tenant's leasing inquiry and tenants for a leasing offer.

The search is the same hybrid search as Opportunity Search (vector similarity plus the
structured property type, bedroom, price, location and attribute scoring); only the
search phrase and constraints come from the opportunity's extracted property items
instead of a typed phrase.
"""

from apps.real_estate.models import ActivityType
from apps.real_estate.services.opportunity_search_input import OpportunitySearchPlan
from apps.real_estate.services.opportunity_search_query import build_constraints
from apps.real_estate.services.opportunity_search_scoring import amount_ranges
from apps.real_estate.services.property_types import FALLBACK_TYPE_CODE


SEARCH_MODE_COUNTERPART = 'counterpart'
COUNTERPART_ACTIVITY = {
    ActivityType.BUYING: ActivityType.SELLING,
    ActivityType.SELLING: ActivityType.BUYING,
    ActivityType.LEASING_INQUIRY: ActivityType.LEASING_OFFER,
    ActivityType.LEASING_OFFER: ActivityType.LEASING_INQUIRY,
}


def counterpart_activity(opportunity):
    try:
        return COUNTERPART_ACTIVITY[opportunity.activity_type]
    except KeyError:
        raise ValueError('This opportunity has no activity type to find a counterpart for.') from None


def counterpart_search_plan(opportunity):
    """The hybrid search plan built from the opportunity's own property details."""
    items = list(opportunity.items.select_related('property_type').order_by('sequence', 'pk'))
    # The fallback "Other" type means extraction found no type, so it is not a criterion.
    property_types = _unique(
        (item.property_type.name if item.property_type.code != FALLBACK_TYPE_CODE else None)
        if item.property_type_id else item.property_type_label
        for item in items
    )
    locations = _unique(
        value for item in items for value in [*(item.locations or []), item.location_raw]
    )
    bedrooms_min, bedrooms_max = _span(items, 'bedrooms')
    amount_min, amount_max = _amount_span(items)
    attributes = {}
    for item in items:
        for key, value in (item.attributes or {}).items():
            attributes.setdefault(key, value)
    criteria = {
        'property_types': property_types,
        'locations': locations,
        'bedrooms_min': bedrooms_min,
        'bedrooms_max': bedrooms_max,
        'amount_min': amount_min,
        'amount_max': amount_max,
        'currency': next((item.currency for item in items if item.currency), ''),
        'amenities': _unique(value for item in items for value in (item.amenities or [])),
        'keywords': _unique(item.title for item in items),
        'attributes': attributes,
    }
    query = _query_text(criteria) or (opportunity.summary or opportunity.original_message or '').strip()
    if not query:
        raise ValueError('This opportunity has no property details or message to match on.')
    constraints = build_constraints(
        query=query,
        company=opportunity.company,
        property_types=property_types,
        bedrooms_min=bedrooms_min,
        bedrooms_max=bedrooms_max,
        amount_min=amount_min,
        amount_max=amount_max,
        locations=locations,
        attributes=attributes,
    )
    interpretation = {
        **{key: _json(value) for key, value in criteria.items()},
        'canonical_query': query,
        'source_opportunity_id': opportunity.pk,
        'source_activity_type': opportunity.activity_type,
        'counterpart_activity_type': counterpart_activity(opportunity),
    }
    return OpportunitySearchPlan(SEARCH_MODE_COUNTERPART, query, constraints, interpretation)


def _span(items, prefix):
    lows = [value for item in items for value in (getattr(item, f'{prefix}_min'), getattr(item, f'{prefix}_max')) if value is not None]
    return (min(lows), max(lows)) if lows else (None, None)


def _amount_span(items):
    """Price range across the items, read the way search scoring reads them: a budget given
    only as a maximum ("up to 2M") starts at 0, one given only as a minimum has no ceiling."""
    ranges = [
        (low if low is not None else high, high if high is not None else low)
        for low, high in amount_ranges(items)
    ]
    if not ranges:
        return None, None
    return min(low for low, _high in ranges), max(high for _low, high in ranges)


def _query_text(criteria):
    parts = [*criteria['property_types'], *criteria['locations']]
    if criteria['bedrooms_min'] is not None:
        low, high = criteria['bedrooms_min'], criteria['bedrooms_max']
        parts.append(f'{_json(low)} bedrooms' if low == high else f'{_json(low)} to {_json(high)} bedrooms')
    if criteria['amount_max'] is not None:
        label = criteria['currency'] or 'price'
        low, high = _json(criteria['amount_min']), _json(criteria['amount_max'])
        if low == high:
            parts.append(f'{high} {label}')
        elif high is None:
            parts.append(f'from {low} {label}')
        elif not low:
            parts.append(f'up to {high} {label}')
        else:
            parts.append(f'{low} to {high} {label}')
    parts.extend(criteria['amenities'])
    parts.extend(criteria['keywords'])
    parts.extend(f'{key}: {value}' for key, value in criteria['attributes'].items())
    return '; '.join(_unique(parts))


def _unique(values):
    return list(dict.fromkeys(str(value).strip() for value in values if value is not None and str(value).strip()))


def _json(value):
    """A JSON-friendly number; an open-ended bound (Infinity) becomes None."""
    if hasattr(value, 'to_integral_value'):
        if not value.is_finite():
            return None
        return int(value) if value == value.to_integral_value() else float(value)
    return value
