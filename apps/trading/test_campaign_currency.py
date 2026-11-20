from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from apps.tenancy.models import Company
from apps.tenancy.testing import create_member
from apps.trading.models import SellingOffer

SETTINGS_URL = '/api/trading-settings/campaign-currency/'


def settings_payload(**changes):
    data = {
        'primary': {'code': 'aed', 'symbol': 'د.إ'},
        'label': 'code',
        'label_position': 'prefix',
        'decimals': 2,
        'trim_zeros': True,
        'separator': ' / ',
        'others': [
            {'code': 'USD', 'symbol': '$', 'rate': 0.2723, 'enabled': True},
            {'code': 'SAR', 'symbol': '', 'rate': 1.02, 'enabled': False},
        ],
    }
    data.update(changes)
    return data


class CampaignCurrencySettingsTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name='Currency Co', slug='currency-co')
        self.admin = User.objects.create_user('currency-admin', password='pw')
        self.operator = User.objects.create_user('currency-operator', password='pw')
        create_member(company=self.company, user=self.admin, role='admin')
        create_member(company=self.company, user=self.operator, role='campaign_operator')
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def test_company_starts_with_a_single_currency(self):
        data = self.client.get(SETTINGS_URL).data
        self.assertEqual(data['primary']['code'], 'AED')
        self.assertEqual(data['others'], [])

    def test_admin_saves_primary_and_converted_currencies(self):
        response = self.client.put(SETTINGS_URL, settings_payload(), format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['primary'], {'code': 'AED', 'symbol': 'د.إ'})
        usd, sar = response.data['others']
        self.assertEqual((usd['code'], usd['rate'], usd['enabled']), ('USD', 0.2723, True))
        self.assertEqual((sar['symbol'], sar['enabled']), ('SAR', False))
        self.assertTrue(usd['rate_updated_at'])
        self.assertEqual(self.client.get(SETTINGS_URL).data, response.data)

    def test_rate_date_changes_only_when_the_rate_changes(self):
        first = self.client.put(SETTINGS_URL, settings_payload(), format='json').data
        same = self.client.put(SETTINGS_URL, settings_payload(), format='json').data
        self.assertEqual(same['others'][0]['rate_updated_at'], first['others'][0]['rate_updated_at'])
        payload = settings_payload()
        payload['others'][0]['rate'] = 0.28
        changed = self.client.put(SETTINGS_URL, payload, format='json').data
        self.assertNotEqual(changed['others'][0]['rate_updated_at'], first['others'][0]['rate_updated_at'])
        self.assertEqual(changed['others'][1]['rate_updated_at'], first['others'][1]['rate_updated_at'])

    def test_invalid_settings_are_rejected_not_defaulted(self):
        bad_rate = settings_payload()
        bad_rate['others'][0]['rate'] = 0
        for payload, field in (
            (settings_payload(primary={'code': 'DIRHAM'}), 'primary.code'),
            (bad_rate, 'others.0.rate'),
            (settings_payload(others=[{'code': 'AED', 'rate': 1}]), 'others.0.code'),
            (settings_payload(label='flag'), 'label'),
            (settings_payload(decimals=7), 'decimals'),
        ):
            response = self.client.put(SETTINGS_URL, payload, format='json')
            self.assertEqual(response.status_code, 400, field)
            self.assertIn(field, response.data)
        self.assertEqual(self.client.get(SETTINGS_URL).data['others'], [])

    def test_only_company_admins_change_the_company_settings(self):
        self.client.force_authenticate(self.operator)
        self.assertEqual(self.client.get(SETTINGS_URL).status_code, 200)
        self.assertEqual(self.client.put(SETTINGS_URL, settings_payload(), format='json').status_code, 403)

    def test_campaign_overrides_and_clears_its_currency_display(self):
        offer = SellingOffer.objects.create(company=self.company, name='Export', created_by=self.operator)
        self.client.force_authenticate(self.operator)
        override = settings_payload(primary={'code': 'USD', 'symbol': '$'}, label='symbol', others=[])
        response = self.client.patch(f'/api/selling-offers/{offer.pk}/', {'currency_settings': override}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['currency_settings']['primary'], {'code': 'USD', 'symbol': '$'})

        response = self.client.patch(f'/api/selling-offers/{offer.pk}/', {'currency_settings': {'primary': {'code': 'X'}}}, format='json')
        self.assertEqual(response.status_code, 400)

        response = self.client.patch(f'/api/selling-offers/{offer.pk}/', {'currency_settings': None}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data['currency_settings'])
