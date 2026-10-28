"""Parse structured constraints from a Real Estate search phrase."""

import re
from dataclasses import dataclass
from decimal import Decimal

from apps.real_estate.models import PropertyType


TOKEN_RE = re.compile(r'[a-z0-9]+')
BEDROOM_RE = re.compile(r'\b(\d+(?:\.\d+)?)\s*(?:bed(?:room)?s?|br|bhk)\b', re.I)
STUDIO_RE = re.compile(r'\bstudio\b', re.I)
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
    bedrooms: Decimal | None
    amount: Decimal | None
    property_type_ids: frozenset


def parse_constraints(query, company):
    normalized = normalize(query)
    bedroom_match = BEDROOM_RE.search(query)
    bedrooms = Decimal(bedroom_match.group(1)) if bedroom_match else None
    if bedrooms is None and STUDIO_RE.search(query):
        bedrooms = Decimal('0')
    amount_match = AMOUNT_RE.search(query)
    type_ids = set()
    for property_type in PropertyType.objects.filter(company=company, is_active=True):
        labels = [
            property_type.name, property_type.code.replace('_', ' '),
            *(property_type.aliases or []),
        ]
        if any(_phrase_present(normalized, label) for label in labels):
            type_ids.add(property_type.pk)
    return SearchConstraints(
        normalized=normalized,
        tokens=frozenset(tokens(normalized)),
        bedrooms=bedrooms,
        amount=_amount(amount_match) if amount_match else None,
        property_type_ids=frozenset(type_ids),
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
