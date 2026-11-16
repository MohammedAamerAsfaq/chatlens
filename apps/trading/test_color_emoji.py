import importlib

from django.apps import apps as django_apps
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.chatlens_core.models import SystemSettings
from apps.tenancy.models import Company, CompanyMembership
from apps.trading.models import Product, ProductAttribute
from apps.trading.services.color_emoji import COLOR_EMOJI_KEY, saved_color_emoji

URL = '/api/trading-settings/color-emoji/'


class ColorEmojiSettingsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username='u', password='pw')
        cls.company = Company.objects.create(name='Emoji Co', slug='emoji-co', industry_type=Company.INDUSTRY_TRADING)
        CompanyMembership.objects.create(company=cls.company, user=cls.user, role=CompanyMembership.ROLE_ADMIN)
        other = Company.objects.create(name='Other', slug='other-emoji', industry_type=Company.INDUSTRY_TRADING)
        for company, name, color in [
            (cls.company, 'A', 'Silver'), (cls.company, 'B', 'Silver'), (cls.company, 'C', 'Glacier'),
            (cls.company, 'D', 'Jet Black'), (other, 'E', 'Teal'),
        ]:
            product = Product.objects.create(company=company, name=name)
            ProductAttribute.objects.create(product=product, key='Color', value=color)

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_lists_every_catalog_color_of_the_company_with_its_emoji(self):
        SystemSettings.objects.create(company=self.company, key=COLOR_EMOJI_KEY, value='{"Silver": "⚪"}')
        data = self.client.get(URL).json()
        self.assertEqual(data['emoji'], {'Silver': '⚪'})
        self.assertEqual(
            [(c['color'], c['emoji'], c['products']) for c in data['colors']],
            [('Glacier', '', 1), ('Jet Black', '', 1), ('Silver', '⚪', 2)],
        )

    def test_save_maps_exact_values_and_blank_unmaps(self):
        resp = self.client.put(URL, {'emoji': {'Glacier': ' 🔵 ', 'Silver': '', 'Jet Black': '⚫'}}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(saved_color_emoji(self.company), {'Glacier': '🔵', 'Jet Black': '⚫'})

    def test_invalid_payload_is_rejected(self):
        self.assertEqual(self.client.put(URL, {'emoji': ['🔵']}, format='json').status_code, 400)
        self.assertEqual(self.client.put(URL, {'emoji': {'Glacier': 'x' * 17}}, format='json').status_code, 400)
        self.assertEqual(self.client.put(URL, {'emoji': {' ': '🔵'}}, format='json').status_code, 400)
        self.assertEqual(saved_color_emoji(self.company), {})

    def test_migration_reproduces_the_retired_table_for_existing_colors_only(self):
        migration = importlib.import_module('apps.trading.migrations.0068_seed_color_emoji')
        migration.seed(django_apps, None)
        self.assertEqual(saved_color_emoji(self.company), {'Silver': '⚪'})
        self.assertFalse(
            SystemSettings.objects.filter(company__slug='other-emoji', key=COLOR_EMOJI_KEY).exists()
        )
