from decimal import Decimal

from django.db import transaction

from apps.real_estate.models import (
    PropertyAttributeAlias, PropertyAttributeDefinition, PropertyAttributeOption,
    PropertyTypeFieldDefinition,
)


DEFAULT_ATTRIBUTES = (
    ('bedrooms', 'Bedrooms', 'number', 'numeric_distance', 'rooms', (
        ('studio', 'Studio', 0, ('bachelor', '0 bedroom', '0 br', '0 bhk')),
        *tuple((str(value), f'{value} Bedroom', value, (
            f'{value} bedrooms', f'{value} bed', f'{value} beds', f'{value} br', f'{value} bhk',
        )) for value in range(1, 11)),
    ), ('bedroom', 'bedrooms', 'bed', 'beds', 'br', 'bhk')),
    ('bathrooms', 'Bathrooms', 'number', 'numeric_distance', 'rooms', (
        *tuple((str(value), f'{value} Bathroom', value, (
            f'{value} bathrooms', f'{value} bath', f'{value} baths',
        )) for value in range(0, 11)),
    ),
     ('bathroom', 'bathrooms', 'bath', 'baths', 'washroom', 'washrooms')),
    ('furnishing', 'Furnishing', 'select', 'exact', '', (
        ('furnished', 'Furnished', None, ('fully furnished', 'furnished unit')),
        ('semi_furnished', 'Semi-furnished', None, ('semi furnished', 'part furnished')),
        ('unfurnished', 'Unfurnished', None, ('not furnished', 'bare')),
    ), ('furnishing status', 'furniture status')),
    ('tenure', 'Tenure', 'select', 'taxonomy', '', (
        ('freehold', 'Freehold', None, ('free hold',)),
        ('long_lease', 'Long lease', None, ('long leasehold', 'leasehold')),
        ('lease_99_year', '99 year lease', None, ('99-year lease', '99 years lease')),
    ), ('tenure type', 'ownership tenure')),
    ('ownership_eligibility', 'Ownership eligibility', 'select', 'taxonomy', '', (
        ('locals_only', 'Locals only', None, ('uae nationals only', 'emiratis only', 'local only')),
        ('gcc_only', 'GCC only', None, ('gcc nationals only', 'gcc citizens only')),
        ('all', 'All buyers', None, ('open to all', 'all nationalities', 'any nationality')),
    ), ('buyer eligibility', 'ownership eligibility', 'purchase eligibility')),
    ('price', 'Price / budget', 'number', 'numeric_distance', 'AED', (),
     ('budget', 'asking price', 'sale price', 'rent', 'amount')),
    ('area', 'Area', 'number', 'numeric_distance', 'sqft', (),
     ('size', 'built up area', 'bua', 'plot area', 'gfa')),
    ('view', 'View', 'text', 'semantic', '', (), ('views', 'outlook')),
    ('floor', 'Floor', 'number', 'numeric_distance', '', (), ('level', 'storey')),
    ('parking', 'Parking spaces', 'number', 'numeric_distance', 'spaces', (),
     ('parking space', 'parking spaces', 'car park')),
    ('balconies', 'Balconies', 'number', 'numeric_distance', '', (), ('balcony',)),
    ('maids_room', "Maid's room", 'boolean', 'exact', '', (
        ('yes', 'Yes', None, ('true', 'included', 'available', 'with maid room')),
        ('no', 'No', None, ('false', 'not included', 'without maid room')),
    ),
     ('maid room', 'maids room', "maid's room")),
    ('facilities', 'Facilities', 'list', 'semantic', '', (), ('amenities', 'features')),
)


@transaction.atomic
def seed_attribute_catalog(company):
    definitions = {}
    for order, values in enumerate(DEFAULT_ATTRIBUTES, start=1):
        code, label, data_type, matching, unit, options, aliases = values
        definition, _ = PropertyAttributeDefinition.objects.get_or_create(
            company=company, code=code,
            defaults={
                'label': label, 'data_type': data_type, 'matching_strategy': matching,
                'unit_hint': unit, 'sort_order': order * 10, 'is_system': True,
            },
        )
        definitions[code] = definition
        _seed_aliases(company, definition, aliases)
        for option_order, option_values in enumerate(options, start=1):
            option_code, option_label, numeric_value, option_aliases = option_values
            option, _ = PropertyAttributeOption.objects.get_or_create(
                company=company, definition=definition, code=option_code,
                defaults={
                    'label': option_label, 'numeric_value': numeric_value,
                    'sort_order': option_order * 10,
                },
            )
            _seed_aliases(company, definition, option_aliases, option=option)
    _link_type_fields(company, definitions)
    return list(definitions.values())


def _seed_aliases(company, definition, aliases, *, option=None):
    for alias in aliases:
        PropertyAttributeAlias.objects.get_or_create(
            company=company, definition=definition,
            normalized_alias=PropertyAttributeAlias.normalize(alias),
            defaults={'alias': alias, 'option': option},
        )


def _link_type_fields(company, definitions):
    for field in PropertyTypeFieldDefinition.objects.filter(
        company=company, attribute_definition__isnull=True,
    ):
        definition = definitions.get(field.code)
        if definition:
            field.attribute_definition = definition
            field.save(update_fields=['attribute_definition'])
        if field.data_type == field.TYPE_SELECT:
            _seed_field_options(company, field, definition)


def _seed_field_options(company, field, definition):
    if not definition:
        definition, _ = PropertyAttributeDefinition.objects.get_or_create(
            company=company, code=field.code,
            defaults={
                'label': field.label, 'data_type': field.data_type,
                'matching_strategy': PropertyAttributeDefinition.MATCH_EXACT,
            },
        )
        field.attribute_definition = definition
        field.save(update_fields=['attribute_definition'])
    for order, value in enumerate(field.options or [], start=1):
        label = str(value).replace('_', ' ').title()
        PropertyAttributeOption.objects.get_or_create(
            company=company, definition=definition, code=str(value),
            defaults={'label': label, 'sort_order': order * 10},
        )


def option_numeric_value(option):
    return Decimal(option.numeric_value) if option and option.numeric_value is not None else None
