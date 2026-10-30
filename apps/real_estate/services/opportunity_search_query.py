"""Parse structured constraints from a Real Estate search phrase."""

import re
from dataclasses import dataclass
from decimal import Decimal

from apps.real_estate.services.opportunity_search_catalog import (
    find_property_types, resolve_bedrooms, resolve_locations, resolve_property_types,
)
from apps.real_estate.services.opportunity_search_attributes import (
    parse_attribute_constraints, resolve_structured_attributes,
)


TOKEN_RE = re.compile(r'[a-z0-9]+')
BEDROOM_RE = re.compile(r'\b(\d+(?:\.\d+)?)\s*(?:bed(?:room)?s?|br|bhk)\b', re.I)
AMOUNT_RE = re.compile(
    r'(?:(?:aed|dhs?)\s*)?(\d[\d,]*(?:\.\d+)?)\s*(million|thousand|m|k)\b'
    r'|(?:aed|dhs?)\s*(\d[\d,]{3,})\b', re.I,
)
STOP_WORDS = {
    'a', 'an', 'and', 'for', 'in', 'is', 'of', 'on', 'or', 'the', 'to',
    'want', 'wanted', 'with', 'property', 'looking', 'available',
}


@dataclass(frozen=True)
class SearchConstraints:
    normalized: str
    tokens: frozenset
    bedrooms_min: Decimal | None
    bedrooms_max: Decimal | None
    amount_min: Decimal | None
    amount_max: Decimal | None
    property_type_ids: frozenset
    related_property_type_ids: frozenset
    locations: tuple
    attributes: tuple
    corrections: tuple

    @property
    def bedrooms(self):
        return self.bedrooms_min if self.bedrooms_min == self.bedrooms_max else None

    @property
    def amount(self):
        return self.amount_min if self.amount_min == self.amount_max else None


def parse_constraints(query, company):
    normalized = normalize(query)
    bedroom_match = BEDROOM_RE.search(query)
    bedrooms = Decimal(bedroom_match.group(1)) if bedroom_match else resolve_bedrooms(company, query)
    amount_match = AMOUNT_RE.search(query)
    type_ids, related_ids, type_corrections = find_property_types(company, query)
    locations, location_corrections = resolve_locations((), query=query)
    attributes, attribute_corrections = parse_attribute_constraints(company, query)
    amount = _amount(amount_match) if amount_match else None
    return SearchConstraints(
        normalized=normalized,
        tokens=frozenset(tokens(normalized)),
        bedrooms_min=bedrooms,
        bedrooms_max=bedrooms,
        amount_min=amount,
        amount_max=amount,
        property_type_ids=type_ids,
        related_property_type_ids=related_ids,
        locations=locations,
        attributes=attributes,
        corrections=(*type_corrections, *location_corrections, *attribute_corrections),
    )


def build_constraints(
    *, query, company, property_types=(), bedrooms_min=None, bedrooms_max=None,
    amount_min=None, amount_max=None, locations=(), attributes=None,
):
    """Build validated constraints from an already structured search phrase."""
    normalized = normalize(query)
    type_ids, related_ids, type_corrections = resolve_property_types(company, property_types)
    resolved_locations, location_corrections = resolve_locations(locations)
    resolved_attributes, attribute_corrections = resolve_structured_attributes(company, attributes)
    return SearchConstraints(
        normalized=normalized,
        tokens=frozenset(tokens(normalized)),
        bedrooms_min=bedrooms_min,
        bedrooms_max=bedrooms_max,
        amount_min=amount_min,
        amount_max=amount_max,
        property_type_ids=type_ids,
        related_property_type_ids=related_ids,
        locations=resolved_locations,
        attributes=resolved_attributes,
        corrections=(*type_corrections, *location_corrections, *attribute_corrections),
    )


def tokens(value):
    return [token for token in TOKEN_RE.findall(value.lower()) if token not in STOP_WORDS]


def normalize(value):
    return ' '.join(TOKEN_RE.findall(str(value or '').lower()))


def _phrase_present(query, phrase):
    normalized = normalize(phrase)
    return bool(normalized and re.search(rf'\b{re.escape(normalized)}\b', query))


def _amount(match):
    raw, suffix = (
        (match.group(1), match.group(2))
        if match.group(1) else (match.group(3), '')
    )
    multiplier = {
        'k': 1000, 'thousand': 1000, 'm': 1000000, 'million': 1000000,
    }.get((suffix or '').lower(), 1)
    return Decimal(raw.replace(',', '')) * multiplier
