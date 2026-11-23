from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.ai_providers.models import AIProviderConfig
from apps.ai_providers.providers.anthropic_provider import AnthropicChatProvider
from apps.ai_providers.providers.openai_compatible import DeepSeekChatProvider, OpenRouterChatProvider
from apps.real_estate.models import (
    MarketPriceReference, PropertyType, RealEstatePromptConfig, RealEstateSettings,
)
from apps.real_estate.services.price_check import price_check_for, web_search_blockers
from apps.real_estate.services.prompts import DEFAULT_EXTRACTION_PROMPT
from apps.real_estate.tests import test_pipeline
from apps.tenancy.models import Company
from apps.tenancy.testing import create_member

AGENT = 'apps.real_estate.services.extraction_service.call_real_estate_agent'
LEASE_REPLY = '{"decision":"leasing_offer","summary":"Studio offered","confidence":0.9,"properties":[]}'


def set_mode(company, mode):
    RealEstateSettings.objects.update_or_create(company=company, defaults={'price_check_mode': mode})


class StockInstructionTests(TestCase):
    def test_cheques_mean_a_rental(self):
        self.assertIn('number of cheques', DEFAULT_EXTRACTION_PROMPT)
        self.assertIn('"4 chqs"', DEFAULT_EXTRACTION_PROMPT)
        self.assertIn('leasing_offer and a wanted property as leasing_inquiry', DEFAULT_EXTRACTION_PROMPT)
        self.assertIn('sale payment plan', DEFAULT_EXTRACTION_PROMPT)


class PriceCheckExtractionTests(TestCase):
    # The pipeline tests' fixture: company, account, chat and an inbound message.
    setUp = test_pipeline.RealEstatePipelineTests.setUp

    def extract(self):
        from apps.real_estate.models import RealEstateParseLog
        from apps.real_estate.services.extraction_service import run_extraction
        from apps.whatsapp_bridge.services.ingestion_service import _log_ai_parsing_and_classify

        _log_ai_parsing_and_classify(self.message)
        parse_log = RealEstateParseLog.objects.get(message=self.message)
        run_extraction(self.message, parse_log, self.company)
        parse_log.refresh_from_db()
        return parse_log

    @patch(AGENT, return_value=LEASE_REPLY)
    def test_default_uses_the_ais_own_market_knowledge(self, agent):
        self.extract()
        system = agent.call_args.kwargs['messages'][0]['content']
        self.assertIn('Sale price check', system)
        self.assertIn('your own knowledge of that market', system)
        self.assertNotIn('web_search', agent.call_args.kwargs)

    @patch(AGENT, return_value=LEASE_REPLY)
    def test_rule_is_added_to_a_companys_own_saved_prompt(self, agent):
        RealEstatePromptConfig.objects.create(
            company=self.company, key=RealEstatePromptConfig.KEY_EXTRACTION, label='Custom', body='Custom rules.',
        )
        self.extract()
        system = agent.call_args.kwargs['messages'][0]['content']
        self.assertTrue(system.startswith('Custom rules.'))
        self.assertIn('Sale price check', system)

    @patch(AGENT, return_value=LEASE_REPLY)
    def test_off_adds_nothing(self, agent):
        set_mode(self.company, RealEstateSettings.PRICE_CHECK_OFF)
        self.extract()
        self.assertNotIn('Sale price check', agent.call_args.kwargs['messages'][0]['content'])

    @patch(AGENT, return_value=LEASE_REPLY)
    def test_web_search_asks_for_search_results(self, agent):
        set_mode(self.company, RealEstateSettings.PRICE_CHECK_WEB)
        parse_log = self.extract()
        self.assertEqual(agent.call_args.kwargs['web_search'], {'max_results': 3})
        self.assertIn('web search results', agent.call_args.kwargs['messages'][0]['content'])
        self.assertEqual(parse_log.extraction_request['web_search'], {'max_results': 3})

    @patch(AGENT, return_value=LEASE_REPLY)
    def test_company_price_table_is_given_to_the_ai(self, agent):
        apartment = PropertyType.objects.create(company=self.company, name='Apartment', code='apartment')
        MarketPriceReference.objects.create(
            company=self.company, location='Dubai Marina', property_type=apartment, bedrooms=2,
            sale_price_min=1800000, sale_price_max=2600000,
        )
        MarketPriceReference.objects.create(
            company=self.company, location='JVC', bedrooms=0, sale_price_min=550000, sale_price_max=800000,
            notes='older buildings lower',
        )
        set_mode(self.company, RealEstateSettings.PRICE_CHECK_TABLE)
        self.extract()
        system = agent.call_args.kwargs['messages'][0]['content']
        self.assertIn("company's sale price table", system)
        self.assertIn('- Dubai Marina | Apartment | 2 bedrooms | AED 1,800,000 to 2,600,000', system)
        self.assertIn('- JVC | any property type | studio | AED 550,000 to 800,000 | older buildings lower', system)

    @patch(AGENT, return_value=LEASE_REPLY)
    def test_an_empty_price_table_fails_loudly(self, agent):
        set_mode(self.company, RealEstateSettings.PRICE_CHECK_TABLE)
        with self.assertRaisesMessage(ValueError, 'the table has no prices'):
            price_check_for(self.company)
        agent.assert_not_called()


class ProviderWebSearchTests(TestCase):
    def test_openrouter_turns_web_search_into_its_web_plugin(self):
        provider = OpenRouterChatProvider('key', 'some/model')
        provider.session = MagicMock()
        provider.session.post.return_value.json.return_value = {'choices': [{'message': {'content': 'ok'}}]}
        provider.chat([{'role': 'user', 'content': 'hi'}], web_search={'max_results': 3}, temperature=0)
        body = provider.session.post.call_args.kwargs['json']
        self.assertEqual(body['plugins'], [{'id': 'web', 'max_results': 3}])
        self.assertNotIn('web_search', body)

    def test_other_providers_refuse_web_search_instead_of_skipping_it(self):
        for provider in (DeepSeekChatProvider('key'), AnthropicChatProvider('key')):
            provider.session = MagicMock()
            with self.assertRaisesMessage(ValueError, 'only available on OpenRouter'):
                provider.chat([{'role': 'user', 'content': 'hi'}], web_search={'max_results': 3})
            provider.session.post.assert_not_called()


class PriceCheckSettingsApiTests(TestCase):
    URL = '/api/real-estate/prompts/price-check/'

    def setUp(self):
        self.company = Company.objects.create(name='Price Estate', slug='price-estate', industry_type='real_estate')
        self.user = get_user_model().objects.create_user('price-estate-owner')
        create_member(company=self.company, user=self.user, role='super_user')
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_defaults_to_the_ais_market_knowledge_and_lists_the_choices(self):
        data = self.client.get(self.URL).json()
        self.assertEqual(data['mode'], 'model_knowledge')
        self.assertEqual([c['value'] for c in data['choices']], ['off', 'model_knowledge', 'web_search', 'reference_table'])

    def test_switching_mode(self):
        response = self.client.put(self.URL, {'mode': 'off'}, format='json')
        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual(RealEstateSettings.objects.get(company=self.company).price_check_mode, 'off')
        self.assertEqual(self.client.put(self.URL, {'mode': 'guess'}, format='json').status_code, 400)

    def test_web_search_needs_openrouter_models(self):
        AIProviderConfig.objects.create(
            company=self.company, display_name='DeepSeek', provider='deepseek', capability='agent',
            model='deepseek-chat', api_key='k', is_active=True,
        )
        response = self.client.put(self.URL, {'mode': 'web_search'}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('DeepSeek (deepseek)', response.json()['mode'][0])

        AIProviderConfig.objects.filter(company=self.company).update(provider='openrouter')
        self.assertEqual(web_search_blockers(self.company), [])
        self.assertEqual(self.client.put(self.URL, {'mode': 'web_search'}, format='json').status_code, 200)

    def test_price_table_must_have_prices_before_it_is_chosen(self):
        self.assertEqual(self.client.put(self.URL, {'mode': 'reference_table'}, format='json').status_code, 400)
        response = self.client.post('/api/real-estate/market-prices/', {
            'location': ' Dubai Marina ', 'bedrooms': 2, 'sale_price_min': 1800000, 'sale_price_max': 2600000,
            'currency': 'aed',
        }, format='json')
        self.assertEqual(response.status_code, 201, response.json())
        self.assertEqual((response.json()['location'], response.json()['currency']), ('Dubai Marina', 'AED'))
        self.assertEqual(self.client.put(self.URL, {'mode': 'reference_table'}, format='json').status_code, 200)

    def test_price_rows_are_validated_and_company_scoped(self):
        other = Company.objects.create(name='Other', slug='other-price', industry_type='real_estate')
        foreign_type = PropertyType.objects.create(company=other, name='Villa', code='villa')
        response = self.client.post('/api/real-estate/market-prices/', {
            'location': 'Palm', 'property_type': foreign_type.pk,
            'sale_price_min': 5000000, 'sale_price_max': 4000000, 'currency': 'AED',
        }, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('property_type', response.json())
        MarketPriceReference.objects.create(company=other, location='Hidden', sale_price_min=1, sale_price_max=2)
        self.assertEqual(self.client.get('/api/real-estate/market-prices/').json(), [])
