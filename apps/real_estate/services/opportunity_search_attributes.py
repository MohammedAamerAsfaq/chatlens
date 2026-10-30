"""Normalize and score catalog-backed property attribute search constraints."""

from decimal import Decimal, InvalidOperation
from difflib import SequenceMatcher

from apps.real_estate.models import PropertyAttributeDefinition
from apps.real_estate.models.property_attribute import normalize_alias
from apps.real_estate.services.property_attribute_catalog import seed_attribute_catalog
from apps.real_estate.services.property_attributes import normalize_number


FUZZY_THRESHOLD = 0.74
DIRECT_FIELDS = {
    'furnishing': 'furnishing', 'tenure': 'tenure_type',
    'ownership_eligibility': 'ownership_eligibility',
}
RANGE_FIELDS = {'bathrooms': 'bathrooms', 'area': 'area'}
SEPARATE_CONSTRAINTS = {'bedrooms', 'price'}


def parse_attribute_constraints(company, query):
    definitions = _definitions(company)
    normalized_query = f' {normalize_alias(query)} '
    constraints = []
    for definition in definitions:
        if definition.code in SEPARATE_CONSTRAINTS:
            continue
        matches = []
        for option in definition.options.all():
            if not option.is_active:
                continue
            labels = {
                label for label in _option_labels(option)
                if not (definition.data_type == definition.TYPE_NUMBER and _is_number(label))
            }
            matches.extend((len(label), option) for label in labels if f' {label} ' in normalized_query)
        if matches:
            _length, option = max(matches, key=lambda item: item[0])
            constraints.append(_constraint(definition, option.code, option.numeric_value))
    return tuple(constraints), ()


def resolve_structured_attributes(company, values):
    if not isinstance(values, dict):
        return (), ()
    definitions = _definitions(company)
    constraints, corrections = [], []
    for supplied_key, supplied_value in list(values.items())[:20]:
        definition, score = _resolve_definition(definitions, supplied_key)
        if not definition or definition.code in SEPARATE_CONSTRAINTS:
            continue
        if score < 1:
            corrections.append(_correction('attribute', supplied_key, definition.label, score))
        value, numeric, value_correction = _resolve_value(definition, supplied_value)
        if value is None:
            continue
        if value_correction:
            corrections.append(value_correction)
        constraints.append(_constraint(definition, value, numeric))
    return tuple(constraints), tuple(corrections)


def score_attribute_constraints(items, constraints, reasons, adjustments):
    bonus = penalty = 0.0
    for constraint in constraints:
        values = _item_values(items, constraint)
        if not values:
            penalty = _penalize(penalty, adjustments, 0.03, f'{constraint["label"]} unavailable')
            continue
        matched, distance = _matches(values, constraint)
        if matched:
            bonus += 0.05
            reasons.append(constraint['label'].lower())
            continue
        amount = min(0.10, 0.04 + (distance or Decimal('0')) * Decimal('0.02'))
        penalty = _penalize(penalty, adjustments, float(amount), f'Nearest {constraint["label"].lower()}')
    return bonus, penalty


def _definitions(company):
    seed_attribute_catalog(company)
    return list(PropertyAttributeDefinition.objects.filter(
        company=company, is_active=True,
    ).prefetch_related('aliases', 'options__aliases'))


def _resolve_definition(definitions, value):
    supplied = normalize_alias(value)
    scored = []
    for definition in definitions:
        labels = {normalize_alias(definition.code), normalize_alias(definition.label)}
        labels.update(alias.normalized_alias for alias in definition.aliases.all() if alias.is_active and not alias.option_id)
        if supplied in labels:
            return definition, 1.0
        scored.append((max(SequenceMatcher(None, supplied, label).ratio() for label in labels), definition))
    score, definition = max(scored, default=(0, None), key=lambda item: item[0])
    return (definition, score) if score >= FUZZY_THRESHOLD else (None, 0)


def _resolve_value(definition, value):
    options = [option for option in definition.options.all() if option.is_active]
    if options:
        supplied = normalize_alias(value)
        exact = next((option for option in options if supplied in _option_labels(option)), None)
        if exact:
            return exact.code, exact.numeric_value, None
        scored = [(max(SequenceMatcher(None, supplied, label).ratio() for label in _option_labels(option)), option) for option in options]
        score, option = max(scored, default=(0, None), key=lambda item: item[0])
        if option and score >= FUZZY_THRESHOLD:
            return option.code, option.numeric_value, _correction(definition.code, value, option.label, score)
        return None, None, None
    if definition.data_type == definition.TYPE_NUMBER:
        try:
            number = normalize_number(value)
            return str(number), number, None
        except (InvalidOperation, ValueError):
            return None, None, None
    if definition.data_type == definition.TYPE_LIST:
        values = value if isinstance(value, list) else str(value).split(',')
        return [str(item).strip() for item in values if str(item).strip()], None, None
    return str(value).strip(), None, None


def _item_values(items, constraint):
    code = constraint['code']
    if code in DIRECT_FIELDS:
        return [getattr(item, DIRECT_FIELDS[code]) for item in items if getattr(item, DIRECT_FIELDS[code], None)]
    if code in RANGE_FIELDS:
        prefix = RANGE_FIELDS[code]
        return [(getattr(item, f'{prefix}_min'), getattr(item, f'{prefix}_max')) for item in items if getattr(item, f'{prefix}_min') is not None or getattr(item, f'{prefix}_max') is not None]
    return [item.attributes[code] for item in items if code in (item.attributes or {})]


def _matches(values, constraint):
    target_number = constraint['numeric_value']
    if target_number is not None:
        distances = [_numeric_distance(value, target_number) for value in values]
        distance = min((value for value in distances if value is not None), default=None)
        return distance == 0, distance
    target = normalize_alias(constraint['value'])
    normalized = {
        normalize_alias(item)
        for value in values
        for item in _comparable_values(value)
    }
    return target in normalized, None


def _comparable_values(value):
    if isinstance(value, bool):
        return ('yes' if value else 'no',)
    if isinstance(value, (list, tuple, set)):
        return value
    return (value,)


def _numeric_distance(value, target):
    values = value if isinstance(value, tuple) else (value, value)
    low = values[0] if values[0] is not None else values[1]
    high = values[1] if values[1] is not None else values[0]
    try:
        low, high = Decimal(str(low)), Decimal(str(high))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return Decimal('0') if low <= target <= high else min(abs(target - low), abs(target - high))


def _option_labels(option):
    labels = {normalize_alias(option.code), normalize_alias(option.label)}
    labels.update(alias.normalized_alias for alias in option.aliases.all() if alias.is_active)
    return labels


def _is_number(value):
    try:
        Decimal(value)
        return True
    except (InvalidOperation, TypeError, ValueError):
        return False


def _constraint(definition, value, numeric):
    return {'code': definition.code, 'label': definition.label, 'value': value, 'numeric_value': numeric}


def _correction(field, supplied, canonical, score):
    return {'field': field, 'supplied': supplied, 'canonical': canonical, 'confidence': round(score, 3)}


def _penalize(total, adjustments, amount, reason):
    adjustments.append({'reason': reason, 'penalty': amount})
    return total + amount
