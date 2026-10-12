from django.utils.text import slugify

from apps.real_estate.models import PropertyType


DEFAULT_PROPERTY_TYPES = (
    ('apartment', 'Apartment', 'residential'),
    ('villa', 'Villa', 'residential'),
    ('townhouse', 'Townhouse', 'residential'),
    ('penthouse', 'Penthouse', 'residential'),
    ('duplex', 'Duplex', 'residential'),
    ('studio', 'Studio', 'residential'),
    ('room', 'Room', 'residential'),
    ('office', 'Office', 'commercial'),
    ('retail', 'Retail', 'commercial'),
    ('warehouse', 'Warehouse', 'commercial'),
    ('building', 'Building', 'commercial'),
    ('land', 'Land', 'land'),
    ('other', 'Other', 'other'),
)


def seed_default_property_types(company):
    records = []
    for order, (code, name, category) in enumerate(DEFAULT_PROPERTY_TYPES, start=1):
        record, _ = PropertyType.objects.get_or_create(
            company=company,
            code=code,
            defaults={'name': name, 'category': category, 'sort_order': order * 10},
        )
        records.append(record)
    return records


def normalize_property_type_code(value):
    return slugify(str(value or '').strip()).replace('-', '_')[:50]


def resolve_property_type(company, value, *, active_only=True, fallback=False):
    if isinstance(value, PropertyType):
        return value if value.company_id == company.pk else None
    text = str(value or '').strip()
    if not text:
        return None
    queryset = PropertyType.objects.filter(company=company)
    if active_only:
        queryset = queryset.filter(is_active=True)
    code = normalize_property_type_code(text)
    match = queryset.filter(code=code).first() or queryset.filter(name__iexact=text).first()
    if match or not fallback:
        return match
    seed_default_property_types(company)
    return PropertyType.objects.filter(company=company, code='other').first()
