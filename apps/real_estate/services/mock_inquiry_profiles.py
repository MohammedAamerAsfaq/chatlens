import re
from dataclasses import dataclass

from django.db.models import Count, Q

from apps.real_estate.models import ActivityType, RealEstateMockSourceRecord


@dataclass(frozen=True)
class DatasetProfile:
    file_name: str
    activity_type: str
    description: str
    columns: dict


PROFILES = {
    profile.file_name: profile for profile in (
        DatasetProfile(
            'Binghatti Leads-1.xlsx', ActivityType.BUYING,
            'Buyer leads with phone, project, bedroom preference, and budget.',
            {'name': 0, 'phones': (2, 3), 'budget': 4, 'bedrooms': 5, 'project': 6},
        ),
        DatasetProfile(
            'Leads JVC-1.xlsx', ActivityType.BUYING,
            'Buyer leads with phone, preferred JVC location, and apartment type.',
            {'name': 0, 'phones': (2,), 'location': 3, 'property_type': 4},
        ),
        DatasetProfile(
            'Dubai silicon oasis 2026.xlsx', ActivityType.SELLING,
            'Owner records with project, unit, type, size, value, and mobile numbers.',
            {
                'name': 20, 'phones': (23, 24, 25, 22, 21), 'location': 0,
                'project': 1, 'unit': 7, 'property_type': 8, 'bedrooms': 10,
                'size': 15, 'price': 14,
            },
        ),
        DatasetProfile(
            'Business Bay F2026.xlsx', ActivityType.SELLING,
            'Owner records with Business Bay community, unit, size, and mobile.',
            {'location': 0, 'project': 1, 'size': 2, 'unit': 3, 'name': 5, 'phones': (6,)},
        ),
    )
}


def clean_value(values, index):
    if index is None or index >= len(values):
        return ''
    value = str(values[index] or '').strip()
    return '' if value.lower() in {'null', 'none', 'nan', '--', '-'} else value


def normalize_phone(value):
    digits = re.sub(r'\D', '', str(value or ''))
    if digits.startswith('00971'):
        digits = digits[2:]
    if digits.startswith('9710'):
        digits = f'971{digits[4:]}'
    elif digits.startswith('05') and len(digits) == 10:
        digits = f'971{digits[1:]}'
    elif digits.startswith('5') and len(digits) == 9:
        digits = f'971{digits}'
    return digits if 8 <= len(digits) <= 15 else ''


def parse_source_record(record, profile):
    values = record.display_values or []
    columns = profile.columns
    phone = ''
    for index in columns['phones']:
        phone = normalize_phone(clean_value(values, index))
        if phone:
            break
    name = clean_value(values, columns.get('name')) or 'Property Client'
    fields = {
        key: clean_value(values, index)
        for key, index in columns.items() if key not in {'name', 'phones'}
    }
    context = [fields.get(key) for key in ('project', 'location', 'property_type')]
    if not phone or not any(context):
        return None
    return {'name': name, 'phone': phone, **fields}


def build_mock_message(profile, data):
    place = data.get('project') or data.get('location') or 'Dubai'
    property_type = data.get('property_type') or data.get('bedrooms') or 'property'
    if profile.activity_type == ActivityType.BUYING:
        details = [f'I am looking to buy a {property_type} in {place}.']
        if data.get('bedrooms') and data['bedrooms'] != property_type:
            details.append(f'Preference: {data["bedrooms"]}.')
        if data.get('budget'):
            details.append(f'Budget is around AED {data["budget"]}.')
        details.append('Please share suitable available options.')
        return ' '.join(details)
    details = [f'I am offering my {property_type} in {place} for sale.']
    if data.get('unit'):
        details.append(f'Unit {data["unit"]}.')
    if data.get('bedrooms'):
        details.append(f'{data["bedrooms"]} bedroom.')
    if data.get('size'):
        details.append(f'Approximate size {data["size"]} square metres.')
    if data.get('price'):
        details.append(f'Expected price AED {data["price"]}.')
    details.append('Please contact me if you have an interested buyer.')
    return ' '.join(details)


def dataset_profiles(company):
    grouped = RealEstateMockSourceRecord.objects.filter(company=company).values(
        'source_file_name',
    ).annotate(
        total=Count('id'),
        pending=Count('id', filter=Q(row_kind='data', processing_status='pending')),
        processed=Count('id', filter=Q(processing_status='processed')),
    ).order_by('source_file_name')
    output = []
    for counts in grouped:
        file_name = counts['source_file_name']
        profile = PROFILES.get(file_name)
        output.append({
            'source_file_name': file_name, 'total_records': counts['total'],
            'eligible_pending': counts['pending'] if profile else 0,
            'processed': counts['processed'],
            'suitable': bool(profile),
            'activity_type': profile.activity_type if profile else '',
            'description': profile.description if profile else 'Not profiled for first-phase mocking.',
        })
    return output
