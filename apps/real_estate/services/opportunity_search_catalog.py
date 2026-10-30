"""Resolve search phrases through company and geography master data."""

from difflib import SequenceMatcher

from apps.integrations.models import AdministrativeArea, City, Country, Locality
from apps.real_estate.models import (
    PropertyAttributeAlias, PropertyAttributeDefinition, PropertyType,
)
from apps.real_estate.services.property_attribute_catalog import seed_attribute_catalog


FUZZY_THRESHOLD = 0.74


def resolve_property_types(company, values):
    records = list(PropertyType.objects.filter(company=company, is_active=True))
    labels = {record.pk: _type_labels(record) for record in records}
    matched, corrections = set(), []
    for value in _values(values):
        exact = next((record for record in records if _exact(value, labels[record.pk])), None)
        if exact:
            matched.add(exact.pk)
            continue
        nearest, score = _nearest(value, records, labels)
        if nearest and score >= FUZZY_THRESHOLD:
            matched.add(nearest.pk)
            corrections.append(_correction('property_type', value, nearest.name, score))
    related = _related_type_ids(records, matched)
    return frozenset(matched), frozenset(related - matched), tuple(corrections)


def find_property_types(company, query):
    records = list(PropertyType.objects.filter(company=company, is_active=True))
    values = [record.name for record in records if _contains(query, _type_labels(record))]
    return resolve_property_types(company, values)


def resolve_bedrooms(company, query):
    seed_attribute_catalog(company)
    definition = PropertyAttributeDefinition.objects.filter(
        company=company, code='bedrooms', is_active=True,
    ).first()
    if not definition:
        return None
    options = list(definition.options.filter(is_active=True).prefetch_related('aliases'))
    for option in options:
        labels = [option.label, option.code, *[alias.alias for alias in option.aliases.all()]]
        if _contains(query, labels):
            return option.numeric_value
    return None


def resolve_locations(values, *, query=''):
    records = _geography_records()
    matched, corrections = [], []
    requested = _values(values)
    if not requested and query:
        requested = [label for record in records for label in _geo_labels(record) if _phrase(query, label)]
    for value in requested:
        exact = next((record for record in records if _exact(value, _geo_labels(record))), None)
        if exact:
            matched.append(_location(exact))
            continue
        nearest, score = _nearest(value, records, {id(record): _geo_labels(record) for record in records})
        if nearest and score >= FUZZY_THRESHOLD:
            matched.append(_location(nearest))
            corrections.append(_correction('location', value, nearest.name, score))
    unique = {item['key']: item for item in matched}
    return tuple(unique.values()), tuple(corrections)


def attribute_alias_map(company):
    seed_attribute_catalog(company)
    aliases = PropertyAttributeAlias.objects.filter(
        company=company, is_active=True, definition__is_active=True,
    ).select_related('definition', 'option')
    return {
        alias.normalized_alias: {
            'attribute': alias.definition.code,
            'value': alias.option.code if alias.option_id else None,
        }
        for alias in aliases
    }


def _geography_records():
    return [
        *Country.objects.filter(is_active=True),
        *AdministrativeArea.objects.filter(is_active=True),
        *City.objects.filter(is_active=True),
        *Locality.objects.filter(is_active=True),
    ]


def _type_labels(record):
    return [record.name, record.code.replace('_', ' '), *(record.aliases or [])]


def _geo_labels(record):
    return [record.name, record.normalized_name, *(record.alternate_names or [])]


def _location(record):
    labels = {_normalize(label) for label in _geo_labels(record) if _normalize(label)}
    return {
        'key': f'{record._meta.model_name}:{record.pk}',
        'name': record.name,
        'terms': tuple(sorted(labels, key=len, reverse=True)),
    }


def _related_type_ids(records, matched):
    parent_by_id = {record.pk: record.parent_id for record in records}
    related = set(matched)
    for record in records:
        current = record.parent_id
        while current:
            if current in matched:
                related.add(record.pk)
                break
            current = parent_by_id.get(current)
    for pk in matched:
        current = parent_by_id.get(pk)
        while current:
            related.add(current)
            current = parent_by_id.get(current)
    return related


def _nearest(value, records, labels):
    normalized = _normalize(value)
    scored = [
        (max((SequenceMatcher(None, normalized, _normalize(label)).ratio() for label in labels[_key(record)]), default=0), record)
        for record in records
    ]
    score, record = max(scored, default=(0, None), key=lambda item: item[0])
    return record, score


def _key(record):
    return record.pk if record.__class__ is PropertyType else id(record)


def _correction(kind, supplied, canonical, score):
    return {'field': kind, 'supplied': supplied, 'canonical': canonical, 'confidence': round(score, 3)}


def _values(values):
    return [str(value).strip() for value in values or [] if str(value).strip()]


def _contains(query, labels):
    return any(_phrase(query, label) for label in labels)


def _exact(value, labels):
    normalized = _normalize(value)
    return any(normalized == _normalize(label) for label in labels)


def _phrase(query, value):
    query, value = _normalize(query), _normalize(value)
    return bool(value and f' {value} ' in f' {query} ')


def _normalize(value):
    return ' '.join(''.join(character if character.isalnum() else ' ' for character in str(value or '').casefold()).split())
