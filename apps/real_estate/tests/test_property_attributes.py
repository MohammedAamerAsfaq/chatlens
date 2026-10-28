from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.real_estate.models import PropertyTypeFieldDefinition
from apps.real_estate.services.property_attributes import normalize_attributes
from apps.real_estate.services.property_types import seed_default_property_types
from apps.tenancy.models import Company


class NormalizeAttributesTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name='Attr Co', slug='attr-co', industry_type='real_estate')
        self.property_type = seed_default_property_types(self.company)[0]  # 'apartment' - already seeds 'floor' (number)
        self.floor = self.property_type.field_definitions.get(code='floor')
        self.parking = PropertyTypeFieldDefinition.objects.create(
            company=self.company, property_type=self.property_type,
            code='parking_spaces', label='Parking Spaces',
            data_type=PropertyTypeFieldDefinition.TYPE_NUMBER, is_required=True,
        )

    def test_strict_mode_still_raises_on_invalid_value(self):
        with self.assertRaises(ValidationError) as ctx:
            normalize_attributes(self.property_type, {'floor': 'Ground'}, strict=True)
        self.assertIn('floor: Enter a valid number.', ctx.exception.message_dict['attributes'])

    def test_strict_mode_still_raises_on_missing_required_value(self):
        with self.assertRaises(ValidationError) as ctx:
            normalize_attributes(self.property_type, {'floor': '3'}, strict=True)
        self.assertIn('parking_spaces: This field is required.', ctx.exception.message_dict['attributes'])

    def test_non_strict_mode_drops_invalid_value_instead_of_raising(self):
        result = normalize_attributes(
            self.property_type, {'floor': 'Ground', 'parking_spaces': '2'}, strict=False,
        )
        self.assertNotIn('floor', result)
        self.assertEqual(result['parking_spaces'], '2')

    def test_non_strict_mode_drops_missing_required_value_instead_of_raising(self):
        result = normalize_attributes(self.property_type, {'floor': '3'}, strict=False)
        self.assertEqual(result, {'floor': '3'})

    def test_non_strict_mode_keeps_all_values_when_everything_is_valid(self):
        result = normalize_attributes(
            self.property_type, {'floor': '12', 'parking_spaces': '1'}, strict=False,
        )
        self.assertEqual(result, {'floor': '12', 'parking_spaces': '1'})
