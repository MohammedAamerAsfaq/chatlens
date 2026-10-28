"""Remove repeated property extractions before opportunity items are persisted."""

import re


TOKEN_RE = re.compile(r'[a-z0-9]+')


def deduplicate_item_values(values_list):
    unique = []
    positions = {}
    for values in values_list:
        key = _fingerprint(values)
        if key not in positions:
            positions[key] = len(unique)
            unique.append(values)
            continue
        _merge(unique[positions[key]], values)
    return unique


def _fingerprint(values):
    return (
        values.get('item_kind'),
        values.get('property_type_id') or getattr(values.get('property_type'), 'pk', None),
        _normalize(values.get('title')),
        _normalize(values.get('location_raw')),
        tuple(sorted(_normalize(value) for value in values.get('locations', []))),
        str(values.get('bedrooms_min') or ''),
        str(values.get('bedrooms_max') or ''),
        str(values.get('amount_min') or ''),
        str(values.get('amount_max') or ''),
        values.get('currency'),
    )


def _merge(target, duplicate):
    target['locations'] = _unique([*target.get('locations', []), *duplicate.get('locations', [])])
    target['amenities'] = _unique([*target.get('amenities', []), *duplicate.get('amenities', [])])
    target['attributes'] = {**duplicate.get('attributes', {}), **target.get('attributes', {})}
    if len(duplicate.get('description', '')) > len(target.get('description', '')):
        target['description'] = duplicate['description']
    raw = dict(target.get('raw_extraction') or {})
    raw['duplicate_extraction_count'] = int(raw.get('duplicate_extraction_count', 1)) + 1
    target['raw_extraction'] = raw


def _normalize(value):
    return ' '.join(TOKEN_RE.findall(str(value or '').lower()))


def _unique(values):
    return list(dict.fromkeys(value for value in values if value))
