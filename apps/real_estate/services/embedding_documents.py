"""Build deterministic, readable text for Real Estate embeddings."""

from django.core.exceptions import ObjectDoesNotExist


DOCUMENT_VERSION = 1


def _text(value):
    if value in (None, '', [], {}):
        return ''
    if isinstance(value, (list, tuple, set)):
        return ', '.join(str(item).strip() for item in value if str(item).strip())
    if isinstance(value, dict):
        return ', '.join(f'{key}: {value[key]}' for key in sorted(value) if value[key] not in (None, ''))
    return str(value).strip()


def _line(label, value):
    value = _text(value)
    return f'{label}: {value}' if value else ''


def _range(label, low, high, suffix=''):
    if low is None and high is None:
        return ''
    value = f'{low or "any"} to {high or "any"}'
    return _line(label, f'{value} {suffix}'.strip())


def _join(lines):
    return '\n'.join(line for line in lines if line)


def _property_location(record):
    try:
        address = record.address
    except ObjectDoesNotExist:
        return ''
    if address.normalized_location:
        return address.normalized_location
    parts = (
        address.project_building, address.community, address.city,
        address.state_region, address.country,
    )
    return ', '.join(dict.fromkeys(part.strip() for part in parts if part and part.strip()))


def property_document(record):
    captions = [item.caption for item in record.media.all() if item.caption]
    return _join([
        _line('Property', record.title),
        _line('Type', record.property_type.name),
        _line('Description', record.description),
        _line('Location', _property_location(record)),
        _line('Bedrooms', record.bedrooms),
        _line('Bathrooms', record.bathrooms),
        _line('Built-up area', f'{record.built_up_area} {record.area_unit}' if record.built_up_area else ''),
        _line('Plot area', f'{record.plot_area} {record.area_unit}' if record.plot_area else ''),
        _line('Furnishing', record.get_furnishing_display()),
        _line('Completion', record.get_completion_status_display()),
        _line('Developer', record.developer),
        _line('Project', record.project_name),
        _line('Completion year', record.completion_year),
        _line('Media context', captions),
    ])


def listing_document(record):
    return _join([
        property_document(record.property),
        _line('Listing type', record.get_listing_type_display()),
        _line('Asking price', f'{record.currency} {record.asking_price}'),
        _line('Payment frequency', record.get_payment_frequency_display()),
        _line('Deposit', f'{record.currency} {record.deposit}' if record.deposit is not None else ''),
        _line('Commission', f'{record.currency} {record.commission}' if record.commission is not None else ''),
        _line('Payment terms', record.payment_terms),
        _line('Available from', record.available_from),
    ])


def requirement_document(record):
    opportunity = record.opportunity
    return _join([
        _line('Activity', opportunity.get_activity_type_display()),
        _line('Summary', opportunity.summary),
        _line('Original inquiry', opportunity.original_message),
        _line('Acceptable locations', record.acceptable_locations),
        _line('Property types', record.acceptable_property_types),
        _range('Bedrooms', record.bedrooms_min, record.bedrooms_max),
        _range('Bathrooms', record.bathrooms_min, record.bathrooms_max),
        _range('Area', record.area_min, record.area_max, record.area_unit),
        _range('Budget', record.budget_min, record.budget_max, record.currency),
        _line('Furnishing', record.get_furnishing_display()),
        _line('Timeframe', record.timeframe),
        _line('Required amenities', record.required_amenities),
        _line('Preferred amenities', record.preferred_amenities),
        _line('Other constraints', record.free_form_constraints),
    ])


def candidate_document(record):
    opportunity = record.opportunity
    return _join([
        _line('Activity', opportunity.get_activity_type_display()),
        _line('Summary', opportunity.summary),
        _line('Original offer', opportunity.original_message),
        _line('Property', record.title),
        _line('Type', record.property_type.name if record.property_type else ''),
        _line('Location', record.location_raw),
        _line('Bedrooms', record.bedrooms),
        _line('Bathrooms', record.bathrooms),
        _line('Area', f'{record.area} {record.area_unit}' if record.area else ''),
        _line('Asking price', f'{record.currency} {record.asking_price}' if record.asking_price is not None else ''),
        _line('Furnishing', record.get_furnishing_display()),
        _line('Available from', record.available_from),
        _line('Description', record.description),
    ])
