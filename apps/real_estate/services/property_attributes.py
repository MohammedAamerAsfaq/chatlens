import logging
import re
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)
NUMBER_RE = re.compile(r'^\s*([+-]?\d[\d,]*(?:\.\d+)?)\s*(k|m|b|thousand|million|billion)?\s*$', re.I)


def normalize_attributes(property_type, attributes, *, strict):
    """strict=True is a human editing a Property through the UI - raise so the form
    can show them exactly what to fix. strict=False is the AI extraction pipeline
    (opportunity_item_projection.py, extraction_projection.py) - a single malformed
    or missing attribute (e.g. a non-numeric "floor" value like "Ground") must not
    abort the whole opportunity, since that call site's caller wraps opportunity
    creation and item/requirement sync in one transaction.atomic() block, so raising
    here rolls back and silently discards an otherwise-correctly-classified inquiry.
    Drop the offending attribute instead and keep the rest.
    """
    if not isinstance(attributes, dict):
        raise ValidationError({'attributes': 'Property attributes must be an object.'})
    fields = list(property_type.field_definitions.filter(is_active=True).select_related(
        'attribute_definition',
    ).prefetch_related('attribute_definition__aliases', 'attribute_definition__options__aliases'))
    definitions = {item.code: item for item in fields}
    aliases = _field_aliases(fields)
    normalized = {}
    errors = {}
    for code, value in attributes.items():
        canonical_code = aliases.get(_normalize(code), code)
        definition = definitions.get(canonical_code)
        if not definition:
            if strict:
                errors[code] = 'This field is not configured for the selected property type.'
            continue
        try:
            normalized[canonical_code] = _coerce(definition, value)
        except ValueError as exc:
            if strict:
                errors[canonical_code] = str(exc)
            else:
                logger.warning(
                    'Dropped unparseable AI-extracted attribute | property_type=%s code=%s value=%r error=%s',
                    property_type.code, code, value, exc,
                )
    for code, definition in definitions.items():
        if not definition.is_required or not _condition_matches(definition, normalized):
            continue
        if normalized.get(code) in (None, '', []):
            if strict:
                errors[code] = 'This field is required.'
            else:
                logger.warning(
                    'AI extraction missing required attribute | property_type=%s code=%s',
                    property_type.code, code,
                )
    if errors:
        raise ValidationError({
            'attributes': [f'{code}: {message}' for code, message in errors.items()],
        })
    return normalized


def _condition_matches(definition, values):
    if not definition.condition_field:
        return True
    return str(values.get(definition.condition_field, '')) == definition.condition_value


def _coerce(definition, value):
    if value in (None, ''):
        return None
    if definition.data_type == definition.TYPE_TEXT:
        return str(value).strip()
    if definition.data_type == definition.TYPE_NUMBER:
        return str(normalize_number(value))
    if definition.data_type == definition.TYPE_BOOLEAN:
        if isinstance(value, bool):
            return value
        option = _resolve_option(definition, value)
        if option and option.code in {'yes', 'no'}:
            return option.code == 'yes'
        text = str(value).strip().lower()
        if text in {'true', '1', 'yes'}:
            return True
        if text in {'false', '0', 'no'}:
            return False
        raise ValueError('Select yes or no.')
    if definition.data_type == definition.TYPE_SELECT:
        text = str(value).strip()
        option = _resolve_option(definition, text)
        if option:
            return option.code
        if text not in definition.options:
            raise ValueError('Select a configured option.')
        return text
    if definition.data_type == definition.TYPE_LIST:
        values = value if isinstance(value, list) else str(value).split(',')
        return [str(item).strip() for item in values if str(item).strip()]
    raise ValueError('Unsupported property field type.')


def normalize_number(value):
    match = NUMBER_RE.match(str(value or ''))
    if not match:
        raise ValueError('Enter a valid number.')
    try:
        number = Decimal(match.group(1).replace(',', ''))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError('Enter a valid number.') from exc
    multiplier = {
        'k': Decimal('1000'), 'thousand': Decimal('1000'),
        'm': Decimal('1000000'), 'million': Decimal('1000000'),
        'b': Decimal('1000000000'), 'billion': Decimal('1000000000'),
    }.get((match.group(2) or '').lower(), Decimal('1'))
    return number * multiplier


def _field_aliases(fields):
    # Exact configured field codes always win over catalog aliases. This avoids
    # an alias such as "parking spaces" redirecting a distinct field whose
    # actual code is ``parking_spaces``.
    values = {_normalize(field.code): field.code for field in fields}
    for field in fields:
        definition = field.attribute_definition
        if not definition:
            continue
        values.setdefault(_normalize(definition.code), field.code)
        for alias in definition.aliases.all():
            if alias.is_active and not alias.option_id:
                values.setdefault(alias.normalized_alias, field.code)
    return values


def _resolve_option(field, value):
    definition = field.attribute_definition
    if not definition:
        return None
    normalized = _normalize(value)
    for option in definition.options.all():
        if not option.is_active:
            continue
        labels = {_normalize(option.code), _normalize(option.label)}
        labels.update(alias.normalized_alias for alias in option.aliases.all() if alias.is_active)
        if normalized in labels:
            return option
    return None


def _normalize(value):
    return ' '.join(str(value or '').strip().casefold().replace('_', ' ').split())
