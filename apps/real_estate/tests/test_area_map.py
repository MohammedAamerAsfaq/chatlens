from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.integrations.connectors import GoogleMapsError
from apps.integrations.models import City, Country, IntegrationConnection, Locality
from apps.real_estate.models import AreaLocation, OpportunityItem, RealEstateOpportunity
from apps.tenancy.models import Company
from apps.tenancy.testing import create_member

URL = '/api/real-estate/opportunities/area-map/'
CLIENT = 'apps.real_estate.services.area_map.client_for'


def google_place(name, lat, lng, country='AE'):
    return {
        'formattedAddress': f'{name}, Dubai, {country}',
        'location': {'latitude': lat, 'longitude': lng},
        'addressComponents': [{'shortText': country, 'longText': country, 'types': ['country']}],
    }


class FakeClient:
    def __init__(self, results):
        self.results, self.queries = results, []

    def search_text(self, query, *, region_code):
        self.queries.append((query, region_code))
        result = self.results.get(query.split(',')[0])
        if isinstance(result, Exception):
            raise result
        return result


class AreaMapTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name='Map Estate', slug='map-estate', industry_type='real_estate')
        self.user = get_user_model().objects.create_user('map-owner')
        create_member(company=self.company, user=self.user, role='super_user')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.country = Country.objects.get(iso2='AE')
        Locality.objects.create(
            country=self.country, name='Jumeirah Village Circle', normalized_name='jumeirah village circle',
            alternate_names=['JVC'], geoname_id=9100001, latitude=25.06, longitude=55.21,
        )
        # Two different places called "Al Barsha": the directory cannot choose, Google decides.
        for geoname_id, lat in ((9100002, 25.11), (9100003, 25.40)):
            Locality.objects.create(
                country=self.country, name='Al Barsha', normalized_name='al barsha',
                geoname_id=geoname_id, latitude=lat, longitude=55.20,
            )
        City.objects.create(country=self.country, name='Dubai', normalized_name='dubai', geoname_id=9100004, latitude=25.2, longitude=55.27)
        IntegrationConnection.objects.create(
            scope=IntegrationConnection.SCOPE_PLATFORM, provider=IntegrationConnection.PROVIDER_GOOGLE_MAPS,
            display_name='Google Maps', secret_value='server-key', is_enabled=True,
            configuration={'browser_api_key': 'browser-key', 'monthly_request_limit': 100},
        )

    def opportunity(self, activity, *locations, raw=''):
        opportunity = RealEstateOpportunity.objects.create(
            company=self.company, activity_type=activity, summary='x', original_message='x', classification_status='classified',
            first_seen_at=timezone.now(),
        )
        OpportunityItem.objects.create(
            company=self.company, opportunity=opportunity, item_kind='demand' if activity in ('buying', 'leasing_inquiry') else 'supply',
            locations=list(locations), location_raw=raw or ', '.join(locations), amount_role='budget',
        )
        return opportunity

    def test_counts_inquiries_per_area_and_places_them_from_the_directory(self):
        self.opportunity('buying', 'JVC')
        self.opportunity('leasing_inquiry', 'jvc')
        self.opportunity('selling', 'Jumeirah Village Circle', 'Dubai')
        self.opportunity('buying')  # no location at all
        data = self.client.get(URL).json()

        self.assertEqual((data['total_opportunities'], data['without_location']), (4, 1))
        self.assertEqual(data['browser_api_key'], 'browser-key')
        top = data['areas'][0]
        self.assertEqual((top['key'], top['count']), ('jvc', 2))
        self.assertEqual(top['by_activity'], {'buying': 1, 'leasing_inquiry': 1})
        self.assertEqual((top['status'], top['source'], top['latitude']), ('placed', 'directory', 25.06))
        dubai = next(area for area in data['areas'] if area['key'] == 'dubai')
        self.assertEqual(dubai['status'], 'placed')

    def test_filters_by_activity(self):
        self.opportunity('buying', 'JVC')
        self.opportunity('selling', 'JVC')
        data = self.client.get(URL, {'activity_type': 'selling'}).json()
        self.assertEqual(data['areas'][0]['by_activity'], {'selling': 1})

    def test_names_the_directory_cannot_place_wait_for_google_and_cost_nothing(self):
        self.opportunity('buying', 'Al Barsha')
        self.opportunity('buying', 'The One Hotel')
        with patch(CLIENT) as client_for:
            data = self.client.get(URL).json()
        client_for.assert_not_called()
        self.assertEqual({area['status'] for area in data['areas']}, {'pending'})
        self.assertEqual(data['google']['waiting'], 2)

    def test_google_places_waiting_names_inside_the_country_only(self):
        self.opportunity('buying', 'Al Barsha')
        self.opportunity('buying', 'The One Hotel')
        self.opportunity('buying', 'Unit 219')
        fake = FakeClient({
            'Al Barsha': google_place('Al Barsha', 25.11, 55.2),
            'The One Hotel': google_place('The One Hotel', 1.3, 103.8, country='SG'),
            'Unit 219': None,
        })
        with patch(CLIENT, return_value=fake):
            data = self.client.post(URL + 'place/').json()
        by_key = {area['key']: area for area in data['areas']}
        self.assertEqual((by_key['al barsha']['status'], by_key['al barsha']['source']), ('placed', 'google'))
        self.assertEqual(by_key['the one hotel']['status'], 'not_found')
        self.assertIn('outside United Arab Emirates', by_key['the one hotel']['error'])
        self.assertEqual(by_key['unit 219']['status'], 'not_found')
        self.assertIn(('Al Barsha, United Arab Emirates', 'AE'), fake.queries)
        self.assertEqual(data['google']['usage']['request_count'], 3)
        self.assertEqual(data['notice'], '')

        # Placed once: the next report does not ask Google again.
        with patch(CLIENT) as client_for:
            self.client.post(URL + 'place/')
        client_for.return_value.search_text.assert_not_called()

    def test_google_failure_is_reported_and_retried_later(self):
        self.opportunity('buying', 'Al Barsha')
        with patch(CLIENT, return_value=FakeClient({'Al Barsha': GoogleMapsError('API key not valid')})):
            data = self.client.post(URL + 'place/').json()
        self.assertIn('API key not valid', data['notice'])
        self.assertEqual(data['areas'][0]['status'], 'error')
        with patch(CLIENT, return_value=FakeClient({'Al Barsha': google_place('Al Barsha', 25.11, 55.2)})):
            data = self.client.post(URL + 'place/').json()
        self.assertEqual(data['areas'][0]['status'], 'placed')

    def test_monthly_cap_stops_lookups_with_a_notice(self):
        IntegrationConnection.objects.update(configuration={'browser_api_key': 'browser-key', 'monthly_request_limit': 1})
        self.opportunity('buying', 'Al Barsha')
        self.opportunity('buying', 'Al Barsha')
        self.opportunity('buying', 'The One Hotel')
        fake = FakeClient({'Al Barsha': google_place('Al Barsha', 25.11, 55.2)})
        with patch(CLIENT, return_value=fake):
            data = self.client.post(URL + 'place/').json()
        # The name with the most inquiries goes first.
        self.assertEqual(fake.queries, [('Al Barsha, United Arab Emirates', 'AE')])
        self.assertIn('monthly request cap', data['notice'])
        self.assertEqual(AreaLocation.objects.get(normalized_name='the one hotel').status, 'pending')

    def test_other_companies_inquiries_are_not_counted(self):
        other = Company.objects.create(name='Other', slug='other-map', industry_type='real_estate')
        opportunity = RealEstateOpportunity.objects.create(
            company=other, activity_type='buying', summary='x', original_message='x', classification_status='classified', first_seen_at=timezone.now(),
        )
        OpportunityItem.objects.create(company=other, opportunity=opportunity, item_kind='demand', locations=['JVC'], amount_role='budget')
        self.assertEqual(self.client.get(URL).json()['areas'], [])

    def test_bad_date_is_refused(self):
        self.assertEqual(self.client.get(URL, {'date_from': 'yesterday'}).status_code, 400)
