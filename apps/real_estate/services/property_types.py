from django.utils.text import slugify

from apps.real_estate.models import PropertyType, PropertyTypeFieldDefinition
from apps.real_estate.services.property_type_schema import TYPE_DEFINITIONS


DEFAULT_PROPERTY_TYPES = tuple(item[:4] for item in TYPE_DEFINITIONS)


def seed_default_property_types(company):
    existing = list(PropertyType.objects.filter(
        company=company,
        code__in=[item[0] for item in TYPE_DEFINITIONS],
    ).prefetch_related('field_definitions'))
    by_code = {record.code: record for record in existing}
    if all(_type_is_seeded(by_code.get(code), definitions) for code, _, _, _, definitions in TYPE_DEFINITIONS):
        return [by_code[code] for code, *_ in TYPE_DEFINITIONS]

    records = []
    for order, (code, name, category, aliases) in enumerate(DEFAULT_PROPERTY_TYPES, start=1):
        record, _ = PropertyType.objects.get_or_create(
            company=company,
            code=code,
            defaults={
                'name': name, 'category': category, 'aliases': list(aliases),
                'sort_order': order * 10,
            },
        )
        _seed_field_definitions(record, TYPE_DEFINITIONS[order - 1][4])
        records.append(record)
    return records


def normalize_property_type_code(value):
    return slugify(str(value or '').strip()).replace('-', '_')[:50]


def resolve_property_type(company, value, *, active_only=True, fallback=False):
    if isinstance(value, PropertyType):
        return value if value.company_id == company.pk else None
    text = str(value or '').strip()
    match = None
    if text:
        queryset = PropertyType.objects.filter(company=company)
        if active_only:
            queryset = queryset.filter(is_active=True)
        code = normalize_property_type_code(text)
        match = queryset.filter(code=code).first() or queryset.filter(name__iexact=text).first()
        if not match:
            folded = text.casefold()
            match = next(
                (record for record in queryset if folded in {
                    str(alias).strip().casefold() for alias in record.aliases
                }),
                None,
            )
    # An empty/unrecognized value with fallback=True still needs a resolution - that's
    # exactly the case a caller requests fallback for (e.g. a for-sale listing whose
    # extraction didn't produce any property type at all), not just a near-miss label.
    if match or not fallback:
        return match
    seed_default_property_types(company)
    return PropertyType.objects.filter(company=company, code='other').first()


def _seed_field_definitions(property_type, definitions):
    existing = set(property_type.field_definitions.values_list('code', flat=True))
    pending = []
    for order, values in enumerate(definitions, start=1):
        code, label, data_type = values[:3]
        if code in existing:
            continue
        options = list(values[3]) if len(values) > 3 else []
        condition_field = values[4] if len(values) > 4 else ''
        condition_value = values[5] if len(values) > 5 else ''
        pending.append(PropertyTypeFieldDefinition(
            company=property_type.company,
            property_type=property_type,
            code=code,
            label=label,
            data_type=data_type,
            options=options,
            is_required=bool(condition_field),
            condition_field=condition_field,
            condition_value=condition_value,
            sort_order=order * 10,
        ))
    PropertyTypeFieldDefinition.objects.bulk_create(pending, ignore_conflicts=True)


def _type_is_seeded(record, definitions):
    if record is None:
        return False
    existing = {item.code for item in record.field_definitions.all()}
    return all(values[0] in existing for values in definitions)
