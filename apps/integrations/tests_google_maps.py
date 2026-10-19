from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.integrations.models import (
    AdministrativeArea, City, Country, GeographyExternalReference,
    IntegrationConnection, IntegrationUsagePeriod, Locality,
)
from apps.integrations.services.google_maps import current_period_start
from apps.tenancy.models import Company, CompanyMembership


class FakeGoogleMapsClient:
    def autocomplete(self, query, *, country_code, session_token):
        return [{
            'place_id': 'google-dubai-marina', 'text': 'Dubai Marina, Dubai, UAE',
            'main_text': 'Dubai Marina', 'secondary_text': 'Dubai, UAE',
            'types': ['neighborhood'],
        }]

    def place_details(self, place_id, *, session_token):
        return {
            'id': place_id,
            'formattedAddress': 'Dubai Marina, Dubai, United Arab Emirates',
            'location': {'latitude': 25.0805, 'longitude': 55.1403},
            'addressComponents': [
                {'longText': 'Dubai Marina', 'types': ['neighborhood']},
                {'longText': 'Dubai', 'types': ['locality']},
                {'longText': 'Dubai', 'types': ['administrative_area_level_1']},
                {
                    'shortText': 'AE', 'longText': 'United Arab Emirates',
                    'types': ['country'],
                },
            ],
        }

    def reverse_geocode(self, latitude, longitude):
        details = self.place_details('google-dubai-marina', session_token='reverse')
        details['location'] = {'latitude': latitude, 'longitude': longitude}
        return details


class GoogleMapsApiTests(TestCase):
    def setUp(self):
        self.control = Company.objects.filter(company_type=Company.TYPE_CONTROL).first()
        if not self.control:
            self.control = Company.objects.create(
                name='Control Workspace', slug='google-control',
                company_type=Company.TYPE_CONTROL,
            )
        self.user = get_user_model().objects.create_user('google-admin', password='pw')
        CompanyMembership.objects.create(
            company=self.control, user=self.user, role=CompanyMembership.ROLE_SUPER_USER,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        session = self.client.session
        session['active_company_id'] = self.control.pk
        session.save()
        self.country = Country.objects.create(
            iso2='AE', name='United Arab Emirates', normalized_name='united arab emirates',
        )
        self.area = AdministrativeArea.objects.create(
            country=self.country, name='Dubai', normalized_name='dubai', geoname_id=292224,
        )
        self.city = City.objects.create(
            country=self.country, administrative_area=self.area,
            name='Dubai', normalized_name='dubai', geoname_id=292223,
            latitude=25.0773, longitude=55.3093,
        )
        self.locality = Locality.objects.create(
            country=self.country, administrative_area=self.area,
            name='Dubai Marina', normalized_name='dubai marina', geoname_id=1200001,
            latitude=25.0805, longitude=55.1403,
        )

    def configure(self, limit=100, browser_key='browser-google-maps-key'):
        response = self.client.post('/api/integrations/google-maps/', {
            'monthly_request_limit': limit, 'is_enabled': True,
            'api_key': 'test-google-maps-key',
            'browser_api_key': browser_key,
        }, format='json')
        self.assertEqual(response.status_code, 200)
        return IntegrationConnection.objects.get(provider='google_maps')

    def test_configuration_stores_write_only_key_and_returns_mask(self):
        connection = self.configure()
        self.assertEqual(connection.secret_reference, '')
        self.assertEqual(connection.secret_value, 'test-google-maps-key')
        self.assertNotIn('api_key', connection.configuration)
        self.assertEqual(connection.configuration['browser_api_key'], 'browser-google-maps-key')
        overview = self.client.get('/api/integrations/overview/')
        self.assertEqual(overview.status_code, 200)
        google = overview.data['google_maps']
        self.assertTrue(google['api_key_configured'])
        self.assertEqual(google['api_key_masked'], 'test****-key')
        self.assertTrue(google['browser_api_key_configured'])
        self.assertNotContains(overview, 'browser-google-maps-key')
        self.assertNotContains(overview, 'test-google-maps-key')
        self.assertNotIn('secret_value', google)
        self.assertNotIn('secret_reference', google)

    def test_property_map_config_returns_browser_key_to_property_manager(self):
        self.configure()
        response = self.client.get('/api/integrations/google-maps/property-map-config/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['browser_api_key'], 'browser-google-maps-key')

    @patch('apps.integrations.views_property_maps.client_for', return_value=FakeGoogleMapsClient())
    def test_property_address_search_returns_source_fields_and_coordinates(self, client_for):
        connection = self.configure()
        suggestions = self.client.post(
            '/api/integrations/google-maps/property-address-suggestions/',
            {
                'query': 'Dubai Marina', 'country_code': 'AE',
                'session_token': 'property-session',
            }, format='json',
        )
        self.assertEqual(suggestions.status_code, 200)
        details = self.client.post(
            '/api/integrations/google-maps/property-place-details/',
            {
                'place_id': suggestions.data['results'][0]['place_id'],
                'country_code': 'AE', 'session_token': 'property-session',
            }, format='json',
        )
        self.assertEqual(details.status_code, 200)
        self.assertEqual(details.data['address']['community'], 'Dubai Marina')
        self.assertEqual(details.data['address']['city'], 'Dubai')
        self.assertEqual(details.data['address']['latitude'], 25.0805)
        self.assertEqual(
            IntegrationUsagePeriod.objects.get(connection=connection).request_count, 2,
        )

    @patch('apps.integrations.views_property_maps.client_for', return_value=FakeGoogleMapsClient())
    def test_property_map_click_reverse_geocodes_source_address(self, client_for):
        connection = self.configure()
        response = self.client.post(
            '/api/integrations/google-maps/property-reverse-geocode/',
            {'latitude': 25.0805, 'longitude': 55.1403, 'country_code': 'AE'},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['address']['state_region'], 'Dubai')
        self.assertEqual(response.data['address']['city'], 'Dubai')
        self.assertEqual(response.data['address']['community'], 'Dubai Marina')
        self.assertEqual(
            response.data['address']['normalized_location'],
            'Dubai Marina, Dubai, United Arab Emirates',
        )
        self.assertEqual(
            IntegrationUsagePeriod.objects.get(connection=connection).request_count, 1,
        )

    def test_blank_key_preserves_existing_credential_and_status(self):
        connection = self.configure()
        connection.status = IntegrationConnection.STATUS_READY
        connection.save(update_fields=['status'])
        response = self.client.post('/api/integrations/google-maps/', {
            'monthly_request_limit': 250, 'is_enabled': True,
        }, format='json')
        self.assertEqual(response.status_code, 200)
        connection.refresh_from_db()
        self.assertEqual(connection.secret_value, 'test-google-maps-key')
        self.assertEqual(connection.status, IntegrationConnection.STATUS_READY)
        self.assertEqual(connection.configuration['monthly_request_limit'], 250)
        self.assertEqual(connection.configuration['browser_api_key'], 'browser-google-maps-key')

    @patch('apps.integrations.views_google_maps.client_for', return_value=FakeGoogleMapsClient())
    def test_manual_resolution_records_place_id_and_canonical_city(self, client_for):
        connection = self.configure()
        suggestions = self.client.post(
            f'/api/integrations/google-maps/localities/{self.locality.pk}/suggestions/',
            {'query': 'Dubai Marina, Dubai'}, format='json',
        )
        self.assertEqual(suggestions.status_code, 200)
        result = suggestions.data['results'][0]
        resolved = self.client.post(
            f'/api/integrations/google-maps/localities/{self.locality.pk}/resolve/',
            {
                'place_id': result['place_id'],
                'session_token': suggestions.data['session_token'],
                'city_id': self.city.pk,
            }, format='json',
        )
        self.assertEqual(resolved.status_code, 200)
        self.locality.refresh_from_db()
        self.assertEqual(self.locality.city, self.city)
        self.assertEqual(self.locality.mapping_status, Locality.MAPPING_MAPPED)
        reference = GeographyExternalReference.objects.get(locality=self.locality)
        self.assertEqual(reference.external_id, 'google-dubai-marina')
        self.assertEqual(IntegrationUsagePeriod.objects.get(connection=connection).request_count, 2)

    def test_monthly_cap_blocks_request_without_calling_google(self):
        connection = self.configure(limit=1)
        IntegrationUsagePeriod.objects.create(
            connection=connection, period_start=current_period_start(), request_count=1,
        )
        with patch('apps.integrations.views_google_maps.client_for') as client_for:
            response = self.client.post(
                f'/api/integrations/google-maps/localities/{self.locality.pk}/suggestions/',
                {}, format='json',
            )
        self.assertEqual(response.status_code, 429)
        client_for.assert_not_called()

    def test_customer_workspace_admin_cannot_manage_shared_google_source(self):
        customer = Company.objects.create(name='Customer', slug='google-customer')
        user = get_user_model().objects.create_user('google-customer-admin')
        CompanyMembership.objects.create(
            company=customer, user=user, role=CompanyMembership.ROLE_SUPER_USER,
        )
        client = APIClient()
        client.force_authenticate(user)
        session = client.session
        session['active_company_id'] = customer.pk
        session.save()
        response = client.post('/api/integrations/google-maps/', {
            'api_key': 'customer-key', 'monthly_request_limit': 100,
            'is_enabled': True,
        }, format='json')
        self.assertEqual(response.status_code, 403)
