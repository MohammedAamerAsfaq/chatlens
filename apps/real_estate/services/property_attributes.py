import logging
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)


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
    definitions = {
        item.code: item for item in property_type.field_definitions.filter(is_active=True)
    }
    normalized = {}
    errors = {}
    for code, value in attributes.items():
        definition = definitions.get(code)
        if not definition:
            if strict:
                errors[code] = 'This field is not configured for the selected property type.'
            continue
        try:
            normalized[code] = _coerce(definition, value)
        except ValueError as exc:
            if strict:
                errors[code] = str(exc)
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
        try:
            return str(Decimal(str(value).replace(',', '').strip()))
        except (InvalidOperation, ValueError) as exc:
            raise ValueError('Enter a valid number.') from exc
    if definition.data_type == definition.TYPE_BOOLEAN:
        if isinstance(value, bool):
            return value
        text = str(value).strip().lower()
        if text in {'true', '1', 'yes'}:
            return True
        if text in {'false', '0', 'no'}:
            return False
        raise ValueError('Select yes or no.')
    if definition.data_type == definition.TYPE_SELECT:
        text = str(value).strip()
        if text not in definition.options:
            raise ValueError('Select a configured option.')
        return text
    if definition.data_type == definition.TYPE_LIST:
        values = value if isinstance(value, list) else str(value).split(',')
        return [str(item).strip() for item in values if str(item).strip()]
    raise ValueError('Unsupported property field type.')
