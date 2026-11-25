import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.ai_providers.models import AIProviderConfig
from apps.integrations.connectors import GoogleMapsError
from apps.integrations.models import City, Country, IntegrationConnection, Locality
from apps.real_estate.models import (
    AreaLocation, OpportunityItem, RealEstateOpportunity, RealEstatePromptConfig, RealEstateSettings,
)
from apps.real_estate.services.location_service import TASK_KEY, enqueue_location, known_areas, locate_opportunity
from apps.real_estate.services.prompts import DEFAULT_PROMPTS
from apps.task_management.models import BackgroundTask
from apps.tenancy.models import Company
from apps.tenancy.testing import create_member

URL = '/api/real-estate/opportunities/area-map/'
AGENT = 'apps.real_estate.services.location_service.call_real_estate_agent'
CLIENT = 'apps.real_estate.services.area_map.client_for'


def reply(*entries):
    return json.dumps({'items': [
        {'sequence': seq, 'area': area, 'sub_area': sub, 'city': city, 'confidence': 0.9, 'basis': 'because'}
        for seq, area, sub, city in entries
    ]})


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
        self.queries.append(query)
        result = self.results.get(query.split(',')[0])
        if isinstance(result, Exception):
            raise result
        return result


class LocationTestCase(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name='Map Estate', slug='map-estate', industry_type='real_estate')
        self.user = get_user_model().objects.create_user('map-owner')
        create_member(company=self.company, user=self.user, role='super_user')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        country = Country.objects.get(iso2='AE')
        dubai = City.objects.create(country=country, name='Dubai', normalized_name='dubai', geoname_id=9100004, latitude=25.2, longitude=55.27)
        sharjah = City.objects.create(country=country, name='Sharjah', normalized_name='sharjah', geoname_id=9100005, latitude=25.34, longitude=55.41)
        Locality.objects.create(
            country=country, city=dubai, name='Jumeirah Village Circle', normalized_name='jumeirah village circle',
            alternate_names=['JVC'], geoname_id=9100001, latitude=25.06, longitude=55.21,
        )
        # Two places called "Al Barsha": the city decides.
        Locality.objects.create(country=country, city=dubai, name='Al Barsha', normalized_name='al barsha', geoname_id=9100002, latitude=25.11, longitude=55.20)
        Locality.objects.create(country=country, city=sharjah, name='Al Barsha', normalized_name='al barsha', geoname_id=9100003, latitude=25.40, longitude=55.50)
        IntegrationConnection.objects.create(
            scope=IntegrationConnection.SCOPE_PLATFORM, provider=IntegrationConnection.PROVIDER_GOOGLE_MAPS,
            display_name='Google Maps', secret_value='server-key', is_enabled=True,
            configuration={'browser_api_key': 'browser-key', 'monthly_request_limit': 100},
        )

    def opportunity(self, activity, *item_locations, message='x'):
        opportunity = RealEstateOpportunity.objects.create(
            company=self.company, activity_type=activity, summary='summary', original_message=message,
            classification_status='classified', first_seen_at=timezone.now(),
        )
        for sequence, locations in enumerate(item_locations or [[]], 1):
            OpportunityItem.objects.create(
                company=self.company, opportunity=opportunity, sequence=sequence,
                item_kind='demand' if activity in ('buying', 'leasing_inquiry') else 'supply',
                locations=list(locations), location_raw=', '.join(locations), amount_role='budget',
            )
        return opportunity


class LocateOpportunityTests(LocationTestCase):
    def test_stock_instructions_are_in_ai_instructions(self):
        prompt, label = DEFAULT_PROMPTS[RealEstatePromptConfig.KEY_LOCATION]
        self.assertEqual(label, 'Real Estate Location')
        self.assertIn('give the community it belongs to', prompt)
        self.assertIn('"sub_area"', prompt)

    @patch(AGENT, return_value=reply((1, 'Jumeirah Village Circle', 'Bloom Towers', 'Dubai')))
    def test_whole_inquiry_goes_to_the_ai_and_the_area_is_placed_from_the_directory(self, agent):
        opportunity = self.opportunity('buying', ['Bloom Towers'], message='Need 1BR in Bloom Towers')
        [item] = locate_opportunity(opportunity)

        kwargs = agent.call_args.kwargs
        self.assertEqual(kwargs['purpose'], 'location')
        self.assertIn('your own knowledge', kwargs['messages'][0]['content'])
        self.assertNotIn('web_search', kwargs)
        context = kwargs['messages'][1]['content']
        self.assertIn('Need 1BR in Bloom Towers', context)
        self.assertIn('location words: Bloom Towers', context)
        item.refresh_from_db()
        self.assertEqual((item.geo_status, item.geo_area, item.geo_sub_area, item.geo_city), ('located', 'Jumeirah Village Circle', 'Bloom Towers', 'Dubai'))
        self.assertEqual(item.geo_area_location.status, 'placed')
        self.assertEqual(item.geo_area_location.source, 'directory')

    @patch(AGENT, return_value=reply((1, 'Al Barsha', '', 'Sharjah')))
    def test_city_picks_between_places_with_the_same_name(self, agent):
        [item] = locate_opportunity(self.opportunity('buying', ['Al Barsha']))
        item.refresh_from_db()
        self.assertEqual(float(item.geo_area_location.latitude), 25.40)

    @patch(AGENT)
    def test_unknown_area_goes_to_google_with_its_city_once(self, agent):
        agent.return_value = reply((1, 'DAMAC Hills 2', 'Verona', 'Dubai'))
        fake = FakeClient({'DAMAC Hills 2': google_place('DAMAC Hills 2', 24.98, 55.39)})
        with patch(CLIENT, return_value=fake):
            locate_opportunity(self.opportunity('selling', ['Verona']))
            agent.return_value = reply((1, 'DAMAC Hills 2', 'Camelia', 'Dubai'))
            locate_opportunity(self.opportunity('buying', ['Camelia']))
        self.assertEqual(fake.queries, ['DAMAC Hills 2, Dubai, United Arab Emirates'])
        self.assertEqual(AreaLocation.objects.get().source, 'google')

    @patch(AGENT, return_value=reply((1, '', '', '')))
    def test_nothing_to_go_on_is_unknown(self, agent):
        [item] = locate_opportunity(self.opportunity('buying', []))
        item.refresh_from_db()
        self.assertEqual(item.geo_status, 'unknown')
        self.assertIsNone(item.geo_area_location)

    @patch(AGENT, return_value=reply((1, 'Jumeirah Village Circle', '', 'Dubai')))
    def test_a_property_the_ai_skipped_is_an_error(self, agent):
        opportunity = self.opportunity('buying', ['JVC'], ['Marina'])
        locate_opportunity(opportunity)
        statuses = dict(opportunity.items.values_list('sequence', 'geo_status'))
        self.assertEqual(statuses, {1: 'located', 2: 'error'})

    @patch(AGENT, side_effect=RuntimeError('provider down'))
    def test_ai_failure_marks_the_items_and_raises_for_a_retry(self, agent):
        opportunity = self.opportunity('buying', ['JVC'])
        with self.assertRaisesMessage(RuntimeError, 'provider down'):
            locate_opportunity(opportunity)
        item = opportunity.items.get()
        self.assertEqual((item.geo_status, item.geo_error), ('error', 'provider down'))

    @patch(AGENT, return_value='{"items": [{"sequence": 1, "area": "JVC", "confidence": 7}]}')
    def test_bad_confidence_is_refused(self, agent):
        with self.assertRaisesMessage(ValueError, 'between 0 and 1'):
            locate_opportunity(self.opportunity('buying', ['JVC']))

    @patch(AGENT, return_value=reply((1, 'Jumeirah Village Circle', '', 'Dubai')))
    def test_web_search_mode_asks_for_search_results(self, agent):
        RealEstateSettings.objects.update_or_create(company=self.company, defaults={'location_search_mode': 'web_search'})
        locate_opportunity(self.opportunity('buying', ['JVC']))
        self.assertEqual(agent.call_args.kwargs['web_search'], {'max_results': 3})
        self.assertIn('Web search results are provided', agent.call_args.kwargs['messages'][0]['content'])

    def test_enqueue_runs_on_the_maintenance_queue_once_per_opportunity(self):
        opportunity = self.opportunity('buying', ['JVC'])
        task = enqueue_location(opportunity)
        self.assertEqual((task.task_key, task.queue_name, task.priority), (TASK_KEY, 'real_estate_maintenance', 50))
        self.assertEqual(enqueue_location(opportunity).pk, task.pk)
        bare = RealEstateOpportunity.objects.create(
            company=self.company, activity_type='buying', summary='x', original_message='x',
            classification_status='classified', first_seen_at=timezone.now(),
        )
        self.assertIsNone(enqueue_location(bare))


class AreaMapApiTests(LocationTestCase):
    def locate(self, opportunity, *entries):
        with patch(AGENT, return_value=reply(*entries)):
            locate_opportunity(opportunity)

    def test_counts_inquiries_per_area_with_their_buildings(self):
        self.locate(self.opportunity('buying', ['Bloom Towers']), (1, 'Jumeirah Village Circle', 'Bloom Towers', 'Dubai'))
        self.locate(self.opportunity('selling', ['JVC']), (1, 'Jumeirah Village Circle', '', 'Dubai'))
        self.locate(self.opportunity('buying', ['?']), (1, '', '', ''))
        self.opportunity('buying', ['JLT'])  # not located yet
        data = self.client.get(URL).json()

        self.assertEqual(data['totals'], {'opportunities': 4, 'no_properties': 0, 'located': 2, 'unknown': 1, 'pending': 1, 'error': 0})
        [area] = data['areas']
        self.assertEqual((area['name'], area['city'], area['count'], area['status']), ('Jumeirah Village Circle', 'Dubai', 2, 'placed'))
        self.assertEqual(area['by_activity'], {'buying': 1, 'selling': 1})
        self.assertEqual(area['sub_areas'], [{'name': 'Bloom Towers', 'count': 1}])

    def test_backfill_queues_only_inquiries_not_located_yet(self):
        located = self.opportunity('buying', ['JVC'])
        self.locate(located, (1, 'Jumeirah Village Circle', '', 'Dubai'))
        waiting = self.opportunity('buying', ['JLT'])
        data = self.client.post(URL + 'locate/', {'scope': 'unlocated'}, format='json').json()
        self.assertEqual(data['queued'], 1)
        self.assertEqual(data['locating'], 1)
        task = BackgroundTask.objects.get(task_key=TASK_KEY)
        self.assertEqual((task.payload['opportunity_id'], task.priority), (waiting.pk, 200))

        data = self.client.post(URL + 'locate/', {'scope': 'all'}, format='json').json()
        self.assertEqual(data['queued'], 2)
        self.assertEqual(BackgroundTask.objects.filter(task_key=TASK_KEY).count(), 2)

    @patch(AGENT, side_effect=RuntimeError('No active agent provider configured.'))
    def test_backfill_status_counts_inquiries_without_an_area_and_why(self, agent):
        self.locate(self.opportunity('buying', ['JVC']), (1, 'Jumeirah Village Circle', '', 'Dubai'))
        self.opportunity('buying', ['JLT'])  # not located yet
        failed = self.opportunity('selling', ['Marina'])
        with self.assertRaises(RuntimeError):
            locate_opportunity(failed)
        # The AI skipped the second property (an error), but the first is located: the
        # inquiry counts as located, as on the map.
        self.locate(self.opportunity('buying', ['JVC'], ['Marina']), (1, 'Jumeirah Village Circle', '', 'Dubai'))
        OpportunityItem.objects.filter(opportunity=self.opportunity('buying')).delete()  # no properties

        data = self.client.get(URL + 'locate/').json()
        self.assertEqual((data['opportunities'], data['with_properties']), (5, 4))
        self.assertEqual((data['pending'], data['error'], data['locating']), (1, 1, 0))
        reasons = {reason['error']: reason['count'] for reason in data['error_reasons']}
        self.assertEqual(reasons.pop('No active agent provider configured.'), 1)
        self.assertEqual(sum(reasons.values()), 1)  # the skipped property, counted per property

    def test_google_button_places_waiting_areas_and_reports_the_cap(self):
        IntegrationConnection.objects.update(configuration={'browser_api_key': 'browser-key', 'monthly_request_limit': 1})
        with patch(CLIENT, return_value=FakeClient({'DAMAC Hills 2': GoogleMapsError('API key not valid')})):
            self.locate(self.opportunity('buying', ['Verona']), (1, 'DAMAC Hills 2', 'Verona', 'Dubai'))
        area = AreaLocation.objects.get()
        self.assertEqual((area.status, area.error), ('error', 'API key not valid'))

        data = self.client.post(URL + 'place/').json()
        self.assertIn('monthly request cap', data['notice'])
        self.assertEqual(data['areas'][0]['status'], 'error')

    def test_other_companies_inquiries_are_not_counted(self):
        other = Company.objects.create(name='Other', slug='other-map', industry_type='real_estate')
        opportunity = RealEstateOpportunity.objects.create(
            company=other, activity_type='buying', summary='x', original_message='x',
            classification_status='classified', first_seen_at=timezone.now(),
        )
        OpportunityItem.objects.create(company=other, opportunity=opportunity, item_kind='demand', locations=['JVC'], amount_role='budget')
        data = self.client.get(URL).json()
        self.assertEqual((data['areas'], data['totals']['opportunities']), ([], 0))
        self.assertEqual(self.client.post(URL + 'locate/', {}, format='json').json()['queued'], 0)

    def test_bad_input_is_refused(self):
        self.assertEqual(self.client.get(URL, {'date_from': 'yesterday'}).status_code, 400)
        self.assertEqual(self.client.post(URL + 'locate/', {'scope': 'some'}, format='json').status_code, 400)


class AreaMapInquiriesGridTests(LocationTestCase):
    GRID = URL + 'inquiries/'
    locate = AreaMapApiTests.locate

    def test_area_filter_lists_exactly_the_inquiries_counted_in_its_bubble(self):
        # Two properties in the same area: still one inquiry, as on the map.
        both = self.opportunity('buying', ['Bloom Towers'], ['JVC'], message='two in JVC')
        self.locate(both, (1, 'Jumeirah Village Circle', 'Bloom Towers', 'Dubai'), (2, 'Jumeirah Village Circle', '', 'Dubai'))
        self.locate(self.opportunity('selling', ['JVC'], message='jvc seller'), (1, 'Jumeirah Village Circle', '', 'Dubai'))
        self.locate(self.opportunity('buying', ['Barsha'], message='barsha'), (1, 'Al Barsha', '', 'Dubai'))
        self.opportunity('buying', ['JLT'], message='not located')

        [jvc, barsha] = self.client.get(URL).json()['areas']
        data = self.client.get(self.GRID, {'area': jvc['id']}).json()
        self.assertEqual(data['count'], jvc['count'])
        self.assertEqual({row['original_message'] for row in data['results']}, {'two in JVC', 'jvc seller'})
        row = next(row for row in data['results'] if row['original_message'] == 'two in JVC')
        self.assertEqual([(loc['area_id'], loc['sub_area']) for loc in row['locations']], [(jvc['id'], 'Bloom Towers'), (jvc['id'], '')])
        # What the WhatsApp buttons need to jump to the original message (none for these).
        self.assertEqual({key: row[key] for key in ('account', 'source_chat', 'source_message', 'source_message_time')},
                         {'account': None, 'source_chat': None, 'source_message': None, 'source_message_time': None})

        self.assertEqual(self.client.get(self.GRID, {'area': barsha['id']}).json()['count'], 1)
        self.assertEqual(self.client.get(self.GRID).json()['count'], 4)

    def test_map_filters_search_sort_and_pages_apply(self):
        for index in range(3):
            self.opportunity('buying', ['JLT'], message=f'buyer {index}')
        self.opportunity('selling', ['JLT'], message='seller')

        data = self.client.get(self.GRID, {'activity_type': 'buying', 'page_size': 2, 'ordering': 'first_seen_at'}).json()
        self.assertEqual(data['count'], 3)
        self.assertEqual([row['original_message'] for row in data['results']], ['buyer 0', 'buyer 1'])
        self.assertIsNotNone(data['next'])
        self.assertEqual(self.client.get(self.GRID, {'search': 'seller'}).json()['count'], 1)

    def test_bad_input_is_refused_and_other_companies_are_hidden(self):
        self.assertEqual(self.client.get(self.GRID, {'area': 'jvc'}).status_code, 400)
        self.assertEqual(self.client.get(self.GRID, {'ordering': 'summary'}).status_code, 400)
        self.assertEqual(self.client.get(self.GRID, {'date_to': 'soon'}).status_code, 400)
        other = Company.objects.create(name='Other', slug='other-grid', industry_type='real_estate')
        RealEstateOpportunity.objects.create(
            company=other, activity_type='buying', summary='x', original_message='x',
            classification_status='classified', first_seen_at=timezone.now(),
        )
        self.assertEqual(self.client.get(self.GRID).json()['count'], 0)


class LocationSearchSettingsTests(LocationTestCase):
    SETTINGS_URL = '/api/real-estate/prompts/location-search/'

    def test_web_search_needs_openrouter_for_the_location_prompt(self):
        self.assertEqual(self.client.get(self.SETTINGS_URL).json()['mode'], 'model_knowledge')
        AIProviderConfig.objects.create(
            company=self.company, display_name='DeepSeek', provider='deepseek', capability='agent',
            model='deepseek-chat', api_key='k', is_active=True,
        )
        response = self.client.put(self.SETTINGS_URL, {'mode': 'web_search'}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('Real Estate Location prompt', response.json()['mode'][0])
        AIProviderConfig.objects.filter(company=self.company).update(provider='openrouter')
        self.assertEqual(self.client.put(self.SETTINGS_URL, {'mode': 'web_search'}, format='json').status_code, 200)
        self.assertEqual(RealEstateSettings.objects.get(company=self.company).location_search_mode, 'web_search')


class InquiryCardLocationTests(LocationTestCase):
    def url(self, opportunity, action):
        return f'/api/real-estate/opportunities/{opportunity.pk}/{action}/'

    def test_set_by_hand_places_the_area_and_is_shown_on_the_inquiry(self):
        opportunity = self.opportunity('buying', ['Bloom'])
        item = opportunity.items.get()
        response = self.client.post(self.url(opportunity, 'location'), {
            'item': item.pk, 'action': 'set', 'area': ' Jumeirah Village Circle ', 'sub_area': 'Bloom Towers', 'city': 'Dubai',
        }, format='json')
        self.assertEqual(response.status_code, 200, response.json())
        [data] = response.json()['items']
        self.assertEqual((data['geo_status'], data['geo_source'], data['geo_area'], data['geo_sub_area']), ('located', 'manual', 'Jumeirah Village Circle', 'Bloom Towers'))
        self.assertEqual(data['geo_position']['latitude'], 25.06)
        self.assertEqual(data['geo_basis'], 'Set by map-owner.')

    def test_area_is_required_and_the_item_must_belong_to_the_inquiry(self):
        opportunity = self.opportunity('buying', ['Bloom'])
        other = self.opportunity('buying', ['JVC'])
        url = self.url(opportunity, 'location')
        self.assertEqual(self.client.post(url, {'item': opportunity.items.get().pk, 'action': 'set', 'area': ' '}, format='json').status_code, 400)
        self.assertEqual(self.client.post(url, {'item': other.items.get().pk, 'action': 'clear'}, format='json').status_code, 400)
        self.assertEqual(self.client.post(url, {'item': opportunity.items.get().pk, 'action': 'move'}, format='json').status_code, 400)

    def test_clear_removes_the_location_and_the_ai_does_not_put_it_back(self):
        opportunity = self.opportunity('buying', ['JVC'])
        with patch(AGENT, return_value=reply((1, 'Jumeirah Village Circle', '', 'Dubai'))):
            locate_opportunity(opportunity)
        item = opportunity.items.get()
        data = self.client.post(self.url(opportunity, 'location'), {'item': item.pk, 'action': 'clear'}, format='json').json()
        self.assertEqual((data['items'][0]['geo_status'], data['items'][0]['geo_area'], data['items'][0]['geo_position']), ('unknown', '', None))

        with patch(AGENT) as agent:
            locate_opportunity(opportunity)  # automatic step, e.g. after re-extraction
        agent.assert_not_called()
        self.assertEqual(self.client.post(URL + 'locate/', {'scope': 'all'}, format='json').json()['queued'], 0)

    def test_find_with_ai_on_the_card_replaces_a_location_set_by_hand(self):
        opportunity = self.opportunity('buying', ['Verona'])
        self.client.post(self.url(opportunity, 'location'), {'item': opportunity.items.get().pk, 'action': 'set', 'area': 'Somewhere'}, format='json')
        with patch(AGENT, return_value=reply((1, 'Al Barsha', '', 'Dubai'))):
            data = self.client.post(self.url(opportunity, 'locate')).json()
        self.assertEqual((data['items'][0]['geo_area'], data['items'][0]['geo_source']), ('Al Barsha', 'ai'))

    def test_find_with_ai_failure_is_reported(self):
        opportunity = self.opportunity('buying', ['Verona'])
        with patch(AGENT, side_effect=RuntimeError('provider down')):
            response = self.client.post(self.url(opportunity, 'locate'))
        self.assertEqual(response.status_code, 400)
        self.assertIn('provider down', str(response.json()['non_field_errors']))

    def test_location_cannot_be_written_through_the_item_api(self):
        opportunity = self.opportunity('buying', ['JVC'])
        item = opportunity.items.get()
        self.client.patch(f'/api/real-estate/opportunity-items/{item.pk}/', {'geo_area': 'Hacked', 'geo_status': 'located'}, format='json')
        item.refresh_from_db()
        self.assertEqual((item.geo_area, item.geo_status), ('', 'pending'))


class LocationFollowUpTests(LocationTestCase):
    def locate(self, opportunity, *entries):
        with patch(AGENT, return_value=reply(*entries)):
            locate_opportunity(opportunity)

    def agent_config(self, name):
        return AIProviderConfig.objects.create(
            company=self.company, display_name=name, provider='openrouter', capability='agent',
            model=f'{name}-model', api_key='k', is_active=False,
        )

    @patch(AGENT, return_value=reply((1, 'Jumeirah Village Circle', '', 'Dubai')))
    def test_location_prompt_without_a_model_uses_the_extraction_prompts_model(self, agent):
        extraction_agent = self.agent_config('extract')
        RealEstatePromptConfig.objects.create(
            company=self.company, key=RealEstatePromptConfig.KEY_EXTRACTION, label='x', body='x', agent_config=extraction_agent,
        )
        RealEstatePromptConfig.objects.create(company=self.company, key=RealEstatePromptConfig.KEY_LOCATION, label='x', body='Custom location rules.')
        locate_opportunity(self.opportunity('buying', ['JVC']))
        self.assertEqual(agent.call_args.kwargs['prompt_config'].agent_config, extraction_agent)
        self.assertTrue(agent.call_args.kwargs['messages'][0]['content'].startswith('Custom location rules.'))

        own = self.agent_config('own')
        RealEstatePromptConfig.objects.filter(key=RealEstatePromptConfig.KEY_LOCATION).update(agent_config=own)
        locate_opportunity(self.opportunity('buying', ['JVC']))
        self.assertEqual(agent.call_args.kwargs['prompt_config'].agent_config, own)

    def test_ai_instructions_say_what_no_model_means(self):
        rows = {row['key']: row for row in self.client.get('/api/real-estate/prompts/').json()}
        self.assertEqual(rows['location']['default_target_label'], 'Same as Real Estate V1 Classification and Extraction')
        self.assertEqual(rows['extraction']['default_target_label'], '')

    def test_naming_rule_and_known_areas_are_given_to_the_ai(self):
        self.locate(self.opportunity('buying', ['JVC']), (1, 'Jumeirah Village Circle', '', 'Dubai'))
        with patch(AGENT, return_value=reply((1, 'Jumeirah Village Circle', '', 'Dubai'))) as agent:
            locate_opportunity(self.opportunity('buying', ['JVC']))
        system = agent.call_args.kwargs['messages'][0]['content']
        self.assertIn("full official name and write it the same way every time", system)
        self.assertIn('- Jumeirah Village Circle, Dubai', system)

    def test_failure_reasons_are_shown_on_the_area_map(self):
        for _ in range(2):
            with patch(AGENT, side_effect=RuntimeError('No active agent provider configured.')):
                with self.assertRaises(RuntimeError):
                    locate_opportunity(self.opportunity('buying', ['JVC']))
        data = self.client.get(URL).json()
        self.assertEqual(data['error_reasons'], [{'error': 'No active agent provider configured.', 'count': 2}])

    def test_merging_moves_inquiries_and_sends_later_results_to_the_merged_area(self):
        fake = FakeClient({
            'Creek Harbour': google_place('Creek Harbour', 25.2, 55.35),
            'Dubai Creek Harbour': google_place('Dubai Creek Harbour', 25.2, 55.35),
        })
        with patch(CLIENT, return_value=fake):
            self.locate(self.opportunity('buying', ['Creek Horizon']), (1, 'Creek Harbour', 'Creek Horizon', 'Dubai'))
            self.locate(self.opportunity('selling', ['Rosewater']), (1, 'Dubai Creek Harbour', 'Rosewater', 'Dubai'))
        short, full = AreaLocation.objects.get(name='Creek Harbour'), AreaLocation.objects.get(name='Dubai Creek Harbour')

        data = self.client.post(URL + 'merge/', {'source': short.pk, 'target': full.pk}, format='json').json()
        self.assertEqual(data['merged'], 1)
        [area] = data['areas']
        self.assertEqual((area['name'], area['count']), ('Dubai Creek Harbour', 2))

        later = self.opportunity('buying', ['Creek Horizon'])
        self.locate(later, (1, 'Creek Harbour', 'Creek Horizon', 'Dubai'))
        item = later.items.get()
        self.assertEqual((item.geo_area_location_id, item.geo_area), (full.pk, 'Dubai Creek Harbour'))
        self.assertNotIn('- Creek Harbour, Dubai', known_areas(self.company))

    def test_merge_refuses_bad_choices(self):
        self.locate(self.opportunity('buying', ['JVC']), (1, 'Jumeirah Village Circle', '', 'Dubai'))
        area = AreaLocation.objects.get()
        self.assertEqual(self.client.post(URL + 'merge/', {'source': area.pk, 'target': area.pk}, format='json').status_code, 400)
        self.assertEqual(self.client.post(URL + 'merge/', {'source': area.pk}, format='json').status_code, 400)
        other = Company.objects.create(name='Other', slug='other-merge', industry_type='real_estate')
        foreign = AreaLocation.objects.create(company=other, normalized_name='x', name='X')
        self.assertEqual(self.client.post(URL + 'merge/', {'source': foreign.pk, 'target': area.pk}, format='json').status_code, 400)
