import csv
import io
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.real_estate.models import Listing, Property, PropertyAddress
from apps.real_estate.services.property_types import resolve_property_type


PROPERTY_FIELDS = (
    'reference_code', 'title', 'property_type', 'description', 'bedrooms', 'bathrooms',
    'built_up_area', 'plot_area', 'area_unit', 'furnishing', 'completion_status',
    'developer', 'project_name', 'completion_year', 'availability_status',
)
ADDRESS_FIELDS = (
    'country', 'state_region', 'city', 'community', 'project_building', 'street',
    'unit_number', 'postal_code',
)
LISTING_FIELDS = (
    'listing_type', 'asking_price', 'currency', 'payment_frequency', 'available_from',
    'status', 'is_verified',
)
CSV_FIELDS = PROPERTY_FIELDS + ADDRESS_FIELDS + LISTING_FIELDS
DECIMAL_FIELDS = {'bedrooms', 'bathrooms', 'built_up_area', 'plot_area', 'asking_price'}


def parse_csv_upload(upload):
    if not upload:
        raise ValidationError({'file': 'Select a CSV file.'})
    if upload.size > 2 * 1024 * 1024:
        raise ValidationError({'file': 'CSV files are limited to 2 MB.'})
    try:
        content = upload.read().decode('utf-8-sig')
    except UnicodeDecodeError as exc:
        raise ValidationError({'file': 'The CSV must use UTF-8 encoding.'}) from exc
    reader = csv.DictReader(io.StringIO(content))
    if not reader.fieldnames:
        raise ValidationError({'file': 'The CSV header row is missing.'})
    unknown = set(reader.fieldnames) - set(CSV_FIELDS)
    if unknown:
        raise ValidationError({'file': f'Unknown columns: {", ".join(sorted(unknown))}.'})
    return [normalize_row(row, index + 2) for index, row in enumerate(reader)]


def normalize_row(row, row_number=None):
    clean = {field: _clean_value(field, row.get(field)) for field in CSV_FIELDS}
    clean['row_number'] = row_number or row.get('row_number')
    clean['area_unit'] = clean['area_unit'] or 'sqft'
    clean['furnishing'] = clean['furnishing'] or 'unknown'
    clean['completion_status'] = clean['completion_status'] or 'unknown'
    clean['availability_status'] = clean['availability_status'] or 'draft'
    clean['currency'] = clean['currency'] or 'AED'
    clean['status'] = clean['status'] or 'draft'
    clean['is_verified'] = _boolean(clean['is_verified'])
    return clean


def preview_rows(company, rows):
    previews = []
    seen = {}
    for source in rows:
        preview = preview_row(company, source)
        signature = _row_signature(preview)
        if signature and signature in seen and not preview['duplicate_property_id']:
            preview['errors']['duplicate'] = f'Duplicates row {seen[signature]} in this upload.'
            preview['valid'] = False
        elif signature:
            seen[signature] = preview['row_number']
        previews.append(preview)
    return previews


def preview_row(company, source):
    row = normalize_row(source)
    errors = {}
    duplicate = _find_duplicate(company, row)
    if not duplicate:
        property_values = _values(row, PROPERTY_FIELDS)
        property_values['property_type'] = resolve_property_type(company, row.get('property_type'))
        if not property_values['property_type']:
            errors['property_type'] = 'Select an active property type configured for this company.'
        property_record = Property(company=company, **property_values)
        if not errors:
            _collect_errors(property_record, errors)
        if _has_values(row, ADDRESS_FIELDS):
            _collect_errors(
                PropertyAddress(company=company, property=property_record, **_values(row, ADDRESS_FIELDS)),
                errors, exclude=['property'],
            )
        if row.get('listing_type') or row.get('asking_price') is not None:
            _collect_errors(
                Listing(company=company, property=property_record, **_values(row, LISTING_FIELDS)),
                errors, exclude=['property'],
            )
    return {
        **row,
        'errors': errors,
        'valid': not errors,
        'duplicate_property_id': duplicate.pk if duplicate else None,
        'duplicate_title': duplicate.title if duplicate else '',
    }


@transaction.atomic
def import_rows(company, rows):
    previews = preview_rows(company, rows)
    invalid = [row for row in previews if not row['valid']]
    if invalid:
        raise ValidationError({'rows': invalid})
    created = []
    skipped = []
    for row in previews:
        if row['duplicate_property_id']:
            skipped.append(row['row_number'])
            continue
        values = _values(row, PROPERTY_FIELDS)
        values['property_type'] = resolve_property_type(company, row.get('property_type'))
        property_record = Property.objects.create(company=company, **values)
        if _has_values(row, ADDRESS_FIELDS):
            PropertyAddress.objects.create(company=company, property=property_record, **_values(row, ADDRESS_FIELDS))
        if row.get('listing_type') or row.get('asking_price') is not None:
            Listing.objects.create(company=company, property=property_record, **_values(row, LISTING_FIELDS))
        created.append(property_record.pk)
    return {'created_count': len(created), 'created_ids': created, 'skipped_rows': skipped}


def _find_duplicate(company, row):
    qs = Property.objects.filter(company=company, is_archived=False)
    if row.get('reference_code'):
        match = qs.filter(reference_code__iexact=row['reference_code']).first()
        if match:
            return match
    if row.get('title'):
        return qs.filter(
            title__iexact=row['title'], project_name__iexact=row.get('project_name') or '',
        ).first()
    return None


def _row_signature(row):
    reference_code = (row.get('reference_code') or '').strip().casefold()
    if reference_code:
        return ('reference_code', reference_code)
    title = (row.get('title') or '').strip().casefold()
    if not title:
        return None
    project = (row.get('project_name') or '').strip().casefold()
    return ('title_project', title, project)


def _clean_value(field, value):
    value = value.strip() if isinstance(value, str) else value
    if value in ('', None):
        return None if field in DECIMAL_FIELDS or field == 'completion_year' else ''
    if field in DECIMAL_FIELDS:
        try:
            return Decimal(str(value).replace(',', ''))
        except InvalidOperation:
            return value
    if field == 'completion_year':
        try:
            return int(value)
        except (TypeError, ValueError):
            return value
    return value


def _boolean(value):
    return str(value).strip().lower() in {'1', 'true', 'yes', 'y'}


def _values(row, fields):
    return {field: row.get(field) for field in fields if row.get(field) not in ('', None)}


def _has_values(row, fields):
    return any(row.get(field) not in ('', None) for field in fields)


def _collect_errors(instance, errors, exclude=None):
    try:
        instance.full_clean(exclude=exclude)
    except ValidationError as exc:
        for field, messages in exc.message_dict.items():
            errors[field] = ' '.join(messages)
