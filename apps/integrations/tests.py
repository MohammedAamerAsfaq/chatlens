from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.integrations.models import AdministrativeArea, City, Country, IntegrationConnection, Locality
from apps.integrations.services.geography_sync import sync_country
from apps.queue_management.models import QueueDefinition
from apps.task_management.models import BackgroundTask
from apps.tenancy.models import Company, CompanyMembership


class FakeGeoNamesClient:
    def __init__(self, username):
        self.username = username

    def country(self, country_code):
        return {
            'countryCode': country_code, 'countryName': 'United Arab Emirates',
            'isoAlpha3': 'ARE', 'geonameId': 290557,
            'north': 26.084, 'south': 22.633, 'east': 56.381, 'west': 51.583,
        }

    def administrative_areas(self, country_code):
        return [{
            'name': 'Dubai', 'geonameId': 292224, 'adminCode1': '03',
            'lat': '25.2695', 'lng': '55.3088',
        }]

    def cities(self, country_code):
        return [
            {
                'name': 'Dubai', 'geonameId': 292223, 'adminCode1': '03',
                'lat': '25.0773', 'lng': '55.3093', 'population': 3478300,
                'fcode': 'PPLA', 'timezone': {'timeZoneId': 'Asia/Dubai'},
            },
            {
                'name': 'Dubai Marina', 'geonameId': 1200001, 'adminCode1': '03',
                'adminName2': 'Dubai', 'lat': '25.0805', 'lng': '55.1403',
                'population': 55052, 'fcode': 'PPLX',
                'timezone': {'timeZoneId': 'Asia/Dubai'},
            },
            {'name': 'Invalid coordinates', 'geonameId': 999999, 'adminCode1': '03'},
        ]


class GeographySyncTests(TestCase):
    def setUp(self):
        self.connection = IntegrationConnection.objects.create(
            scope=IntegrationConnection.SCOPE_PLATFORM,
            provider=IntegrationConnection.PROVIDER_GEONAMES,
            display_name='GeoNames Geography', configuration={'username': 'test-user'},
            is_enabled=True,
        )

    @patch('apps.integrations.services.geography_sync.GeoNamesClient', FakeGeoNamesClient)
    def test_sync_creates_normalized_master_records_and_skips_invalid_coordinates(self):
        counters = sync_country(self.connection, 'AE')

        country = Country.objects.get(iso2='AE')
        area = AdministrativeArea.objects.get(country=country, code='03')
        city = City.objects.get(country=country, name='Dubai')
        locality = Locality.objects.get(country=country, name='Dubai Marina')
        self.assertEqual(country.normalized_name, 'united arab emirates')
        self.assertEqual(city.administrative_area, area)
        self.assertEqual(city.timezone, 'Asia/Dubai')
        self.assertEqual(locality.city, city)
        self.assertEqual(locality.mapping_status, Locality.MAPPING_MAPPED)
        self.assertEqual(counters['cities_total'], 1)
        self.assertEqual(counters['cities_skipped'], 0)
        self.assertEqual(counters['localities_total'], 1)
        self.assertEqual(counters['localities_mapped'], 1)
        self.assertEqual(counters['localities_skipped'], 1)

    @patch('apps.integrations.services.geography_sync.GeoNamesClient', FakeGeoNamesClient)
    def test_populated_place_is_not_stored_as_a_city(self):
        sync_country(self.connection, 'AE')

        self.assertFalse(City.objects.filter(name='Dubai Marina', is_active=True).exists())
        self.assertTrue(Locality.objects.filter(name='Dubai Marina', is_active=True).exists())


class IntegrationApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.control = Company.objects.filter(company_type=Company.TYPE_CONTROL).first()
        if not self.control:
            self.control = Company.objects.create(
                name='Control Workspace', slug='control-workspace',
                company_type=Company.TYPE_CONTROL,
            )
        self.user = get_user_model().objects.create_user('integration-admin', password='pw')
        CompanyMembership.objects.create(
            company=self.control, user=self.user, role=CompanyMembership.ROLE_SUPER_USER,
        )
        self.client.force_authenticate(self.user)
        session = self.client.session
        session['active_company_id'] = self.control.pk
        session.save()

    def test_control_admin_can_configure_and_view_sanitized_source(self):
        response = self.client.put('/api/integrations/geography-source/', {
            'username': 'geo-user', 'is_enabled': True,
        }, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['username'], 'geo-user')
        self.assertNotIn('secret_reference', response.data)

        overview = self.client.get('/api/integrations/overview/')
        self.assertEqual(overview.status_code, 200)
        self.assertTrue(overview.data['can_manage_platform'])
        self.assertEqual(overview.data['geonames']['username'], 'geo-user')

    def test_control_admin_can_manage_platform_source_from_customer_workspace(self):
        customer = Company.objects.create(name='Real Estate', slug='real-estate')
        CompanyMembership.objects.create(
            company=customer, user=self.user, role=CompanyMembership.ROLE_SUPER_USER,
        )
        session = self.client.session
        session['active_company_id'] = customer.pk
        session.save()

        response = self.client.put('/api/integrations/geography-source/', {
            'username': 'geo-user', 'is_enabled': True,
        }, format='json')
        self.assertEqual(response.status_code, 200)
        overview = self.client.get('/api/integrations/overview/')
        self.assertTrue(overview.data['can_manage_platform'])

    def test_platform_sync_is_owned_by_control_company_from_customer_workspace(self):
        customer = Company.objects.create(name='Real Estate', slug='real-estate-sync')
        CompanyMembership.objects.create(
            company=customer, user=self.user, role=CompanyMembership.ROLE_SUPER_USER,
        )
        session = self.client.session
        session['active_company_id'] = customer.pk
        session.save()
        QueueDefinition.objects.update_or_create(
            name='integrations', defaults={'display_name': 'Integrations', 'is_enabled': True},
        )
        IntegrationConnection.objects.create(
            scope='platform', provider='geonames', display_name='GeoNames',
            configuration={'username': 'geo-user'}, is_enabled=True, status='ready',
        )

        response = self.client.post(
            '/api/integrations/geography-source/sync/', {'country_code': 'AE'}, format='json',
        )
        self.assertEqual(response.status_code, 202)
        task = BackgroundTask.objects.get(pk=response.data['background_task_id'])
        self.assertEqual(task.company, self.control)

    @patch('apps.integrations.views.GeoNamesClient.country')
    def test_connection_test_reports_country(self, country):
        country.return_value = {'countryName': 'United Arab Emirates', 'countryCode': 'AE'}
        IntegrationConnection.objects.create(
            scope='platform', provider='geonames', display_name='GeoNames',
            configuration={'username': 'geo-user'}, is_enabled=True,
        )
        response = self.client.post('/api/integrations/geography-source/test/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['sample']['iso2'], 'AE')

    def test_sync_creates_run_and_durable_integration_task(self):
        QueueDefinition.objects.update_or_create(
            name='integrations', defaults={'display_name': 'Integrations', 'is_enabled': True},
        )
        IntegrationConnection.objects.create(
            scope='platform', provider='geonames', display_name='GeoNames',
            configuration={'username': 'geo-user'}, is_enabled=True, status='ready',
        )
        response = self.client.post(
            '/api/integrations/geography-source/sync/', {'country_code': 'AE'}, format='json',
        )
        self.assertEqual(response.status_code, 202)
        task = BackgroundTask.objects.get(pk=response.data['background_task_id'])
        self.assertEqual(task.queue_name, 'integrations')
        self.assertEqual(task.task_key, 'integrations.sync_geography')
        self.assertEqual(task.company, self.control)

        repeated = self.client.post(
            '/api/integrations/geography-source/sync/', {'country_code': 'AE'}, format='json',
        )
        self.assertEqual(repeated.status_code, 202)
        self.assertEqual(repeated.data['id'], response.data['id'])
        self.assertEqual(BackgroundTask.objects.filter(task_key='integrations.sync_geography').count(), 1)

    def test_customer_company_cannot_manage_platform_source(self):
        customer = Company.objects.create(name='Customer', slug='integration-customer')
        user = get_user_model().objects.create_user('customer-admin')
        CompanyMembership.objects.create(
            company=customer, user=user, role=CompanyMembership.ROLE_SUPER_USER,
        )
        client = APIClient()
        client.force_authenticate(user)
        session = client.session
        session['active_company_id'] = customer.pk
        session.save()

        response = client.put(
            '/api/integrations/geography-source/', {'username': 'not-allowed'}, format='json',
        )
        self.assertEqual(response.status_code, 403)

    def test_locations_endpoint_exposes_locality_hierarchy(self):
        country = Country.objects.create(
            iso2='AE', name='United Arab Emirates', normalized_name='united arab emirates',
        )
        area = AdministrativeArea.objects.create(
            country=country, name='Dubai', normalized_name='dubai', geoname_id=292224,
        )
        city = City.objects.create(
            country=country, administrative_area=area, name='Dubai', normalized_name='dubai',
            geoname_id=292223, feature_code='PPLA', latitude=25.0773, longitude=55.3093,
        )
        Locality.objects.create(
            country=country, administrative_area=area, city=city,
            name='Dubai Marina', normalized_name='dubai marina', geoname_id=1200001,
            feature_code='PPLX', latitude=25.0805, longitude=55.1403,
            mapping_status=Locality.MAPPING_MAPPED,
        )

        response = self.client.get('/api/integrations/locations/?level=locality&city_id=%s' % city.pk)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['city_name'], 'Dubai')
