from datetime import timedelta
from unittest.mock import Mock, patch

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from django.contrib.auth import get_user_model
from apps.tenancy.models import Company, CompanyMembership

from .kiwi_router_service import execute_agent, reserve_agent
from .models import AIProviderConfig, KiwiRouter, KiwiRouterMember, KiwiRouterReservation
from .provider_deadline import _run_provider_call
from .serializers import KiwiRouterSerializer
from apps.tenancy.testing import create_member


class KiwiRouterReservationTests(TestCase):
    def setUp(self):
        self.company = Company.objects.get(slug='control-account')
        self.router = KiwiRouter.objects.create(
            company=self.company, name='Inquiry router', capability='agent',
        )
        self.first = self._member('DeepSeek', 1, 3)
        self.second = self._member('Gemini', 2, 5)
        self.third = self._member('Nemotron', 3, 2)

    def _member(self, name, priority, rpm_limit):
        config = AIProviderConfig.objects.create(
            company=self.company,
            display_name=name, provider='deepseek', capability='agent',
            api_key='test-key', model='test-model', is_active=False,
        )
        return KiwiRouterMember.objects.create(
            router=self.router, provider_config=config, priority=priority,
            rpm_limit=rpm_limit,
        )

    def test_ordered_capacity_fill_uses_member_rpm_in_priority_order(self):
        selected_member_ids = []
        for number in range(10):
            selection = reserve_agent(
                self.router.pk, company=self.company, workflow_key='inquiry_pass1',
                correlation_id=f'message:{number}', task_id=number,
            )
            self.assertIsNotNone(selection.member)
            selected_member_ids.append(selection.member.pk)

        self.assertEqual(selected_member_ids, [
            self.first.pk, self.first.pk, self.first.pk,
            self.second.pk, self.second.pk, self.second.pk, self.second.pk, self.second.pk,
            self.third.pk, self.third.pk,
        ])
        self.assertEqual(KiwiRouterReservation.objects.count(), 10)

    def test_full_router_returns_durable_deferral(self):
        for number in range(10):
            reserve_agent(self.router.pk, company=self.company, workflow_key='inquiry_pass1', correlation_id=f'message:{number}')

        selection = reserve_agent(self.router.pk, company=self.company, workflow_key='inquiry_pass1', correlation_id='message:full')

        self.assertIsNone(selection.member)
        self.assertIsNotNone(selection.available_at)

    def test_expired_dispatch_no_longer_uses_concurrency_capacity(self):
        self.first.max_concurrency = 1
        self.first.save(update_fields=['max_concurrency'])
        first_selection = reserve_agent(
            self.router.pk, company=self.company, workflow_key='inquiry_pass1', correlation_id='message:active',
        )
        first_selection.reservation.expires_at = timezone.now() - timedelta(seconds=1)
        first_selection.reservation.save(update_fields=['expires_at'])

        replacement = reserve_agent(
            self.router.pk, company=self.company, workflow_key='inquiry_pass1', correlation_id='message:replacement',
        )

        first_selection.reservation.refresh_from_db()
        self.assertEqual(first_selection.reservation.status, KiwiRouterReservation.STATUS_EXPIRED)
        self.assertEqual(replacement.member, self.first)

    def test_used_member_can_be_updated_without_replacing_history(self):
        reserve_agent(self.router.pk, company=self.company, workflow_key='inquiry_pass1', correlation_id='message:history')
        data = {
            'name': self.router.name,
            'description': self.router.description,
            'capability': self.router.capability,
            'strategy': self.router.strategy,
            'default_request_timeout_seconds': self.router.default_request_timeout_seconds,
            'is_active': self.router.is_active,
            'members': [{
                'id': member.pk,
                'provider_config': member.provider_config_id,
                'priority': member.priority,
                'is_enabled': member.is_enabled,
                'rpm_limit': 8 if member == self.first else member.rpm_limit,
                'tpm_limit': member.tpm_limit,
                'max_concurrency': member.max_concurrency,
                'input_cost_per_million': member.input_cost_per_million,
                'output_cost_per_million': member.output_cost_per_million,
                'metadata_source': member.metadata_source,
                'request_timeout_seconds': member.request_timeout_seconds,
            } for member in (self.first, self.second, self.third)],
        }

        serializer = KiwiRouterSerializer(instance=self.router, data=data)

        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()
        self.first.refresh_from_db()
        self.assertEqual(self.first.rpm_limit, 8)
        self.assertEqual(self.first.reservations.count(), 1)

    @patch('apps.ai_providers.kiwi_router_service.call_provider_with_deadline')
    def test_execution_uses_the_shorter_caller_timeout_once(self, call_provider):
        call_provider.return_value = {'content': 'ok'}

        response, member = execute_agent(
            self.router.pk,
            company=self.company,
            messages=[{'role': 'user', 'content': 'test'}],
            workflow_key='inquiry_pass1',
            correlation_id='message:timeout',
            request_timeout=20,
        )

        self.assertEqual(response, {'content': 'ok'})
        self.assertEqual(member, self.first)
        call_provider.assert_called_once_with(
            self.first.provider_config_id,
            [{'role': 'user', 'content': 'test'}], request_timeout=20,
            timeout_seconds=20,
        )
        reservation = KiwiRouterReservation.objects.get(correlation_id='message:timeout')
        self.assertEqual(reservation.status, KiwiRouterReservation.STATUS_SUCCEEDED)

    @patch('django.setup')
    @patch('apps.ai_providers.provider_deadline.traceback.format_exc')
    @patch('apps.ai_providers.manager.build_provider')
    @patch('django.db.close_old_connections')
    def test_spawned_provider_process_initializes_django(
        self, close_connections, build_provider, format_exc, setup,
    ):
        connection = Mock()
        provider = build_provider.return_value
        provider.chat.return_value = {'content': 'ok'}

        _run_provider_call(
            connection,
            self.first.provider_config_id,
            [{'role': 'user', 'content': 'test'}],
            {'request_timeout': 10},
        )

        setup.assert_called_once_with()
        provider.chat.assert_called_once_with(
            [{'role': 'user', 'content': 'test'}], request_timeout=10,
        )
        connection.send.assert_called_once_with(('ok', {'content': 'ok'}))
        connection.close.assert_called_once_with()
        self.assertEqual(close_connections.call_count, 2)
        format_exc.assert_not_called()


class CompanyOwnedProviderApiTests(TestCase):
    def setUp(self):
        self.company_a = Company.objects.create(name='Provider A', slug='provider-a')
        self.company_b = Company.objects.create(name='Provider B', slug='provider-b')
        self.user = get_user_model().objects.create_user('provider-admin', password='pw')
        create_member(
            company=self.company_a, user=self.user, role='admin',
        )
        self.provider_a = AIProviderConfig.objects.create(
            company=self.company_a, display_name='A Agent', provider='deepseek',
            capability='agent', api_key='a', model='a-model',
        )
        self.provider_b = AIProviderConfig.objects.create(
            company=self.company_b, display_name='B Agent', provider='deepseek',
            capability='agent', api_key='b', model='b-model',
        )
        self.client = APIClient()
        self.client.login(username='provider-admin', password='pw')

    def test_provider_list_and_detail_are_company_scoped(self):
        response = self.client.get('/api/ai-providers/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual({row['id'] for row in response.json()}, {self.provider_a.pk})
        hidden = self.client.get(f'/api/ai-providers/{self.provider_b.pk}/')
        self.assertEqual(hidden.status_code, 404)

    def test_router_rejects_provider_from_another_company(self):
        response = self.client.post('/api/kiwi-routers/', {
            'name': 'A Router',
            'capability': 'agent',
            'strategy': 'ordered_capacity_fill',
            'default_request_timeout_seconds': 60,
            'is_active': True,
            'members': [{
                'provider_config': self.provider_b.pk,
                'priority': 1,
                'is_enabled': True,
            }],
        }, format='json')
        self.assertEqual(response.status_code, 400)


CATALOG = {'data': [
    {
        'id': 'openai/gpt-4o-mini', 'name': 'OpenAI: GPT-4o-mini', 'context_length': 128000,
        'pricing': {'prompt': '0.00000015', 'completion': '0.0000006'},
        'top_provider': {'context_length': 128000, 'max_completion_tokens': 16384},
        'supported_parameters': ['tools', 'temperature', 'max_tokens'],
        'architecture': {'input_modalities': ['text', 'image']},
    },
    {
        'id': 'anthropic/claude-sonnet-4.6', 'name': 'Anthropic: Claude Sonnet 4.6', 'context_length': 200000,
        'pricing': {'prompt': '0.000003', 'completion': '0.000015'},
        'top_provider': {'max_completion_tokens': 64000}, 'supported_parameters': ['tools'],
    },
    {'id': 'someone/gpt-4o-mini', 'pricing': {'prompt': '1', 'completion': '1'}},
    {'id': 'openrouter/auto', 'pricing': {'prompt': '-1', 'completion': '-1'}},
]}


def _response(payload):
    response = Mock()
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    return response


class ModelLookupApiTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name='Lookup Co', slug='lookup-co')
        self.user = get_user_model().objects.create_user('lookup-admin', password='pw')
        create_member(company=self.company, user=self.user, role='admin')
        self.client = APIClient()
        self.client.login(username='lookup-admin', password='pw')

    def lookup(self, **data):
        payload = {'provider': 'openai', 'capability': 'agent', 'api_key': 'sk-test', **data}
        return self.client.post('/api/ai-providers/lookup-model/', payload, format='json')

    @patch('apps.ai_providers.model_lookup.requests.get', return_value=_response(CATALOG))
    @patch('apps.ai_providers.providers.openai_provider.OpenAIChatProvider.list_models', return_value=['gpt-4o', 'gpt-4o-mini'])
    def test_verifies_name_and_reads_rates_from_vendor_listing(self, _list, _get):
        response = self.lookup(model='GPT-4o-mini')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['verified'])
        self.assertEqual(data['model'], 'gpt-4o-mini')
        self.assertEqual(data['info_source'], 'openrouter_catalog')
        info = data['info']
        self.assertEqual(info['catalog_id'], 'openai/gpt-4o-mini')
        self.assertEqual((info['input_cost_per_million'], info['output_cost_per_million']), (0.15, 0.6))
        self.assertEqual((info['context_length'], info['max_output_tokens']), (128000, 16384))
        self.assertEqual(info['supported_parameters'], ['max_tokens', 'temperature', 'tools'])

    @patch('apps.ai_providers.model_lookup.requests.get', return_value=_response(CATALOG))
    @patch('apps.ai_providers.providers.openai_provider.OpenAIChatProvider.list_models', return_value=['gpt-4o', 'gpt-4o-mini'])
    def test_unknown_name_is_refused_with_close_names(self, _list, _get):
        data = self.lookup(model='gpt-4o-mni').json()
        self.assertFalse(data['verified'])
        self.assertIn('gpt-4o-mini', data['suggestions'])
        self.assertIn('has no model named "gpt-4o-mni"', data['detail'])

    @patch('apps.ai_providers.model_lookup.requests.get', return_value=_response(CATALOG))
    @patch('apps.ai_providers.providers.anthropic_provider.AnthropicChatProvider.list_models', return_value=['claude-sonnet-4-6'])
    def test_matches_catalog_names_written_with_dots(self, _list, _get):
        data = self.lookup(provider='anthropic', model='claude-sonnet-4-6').json()
        self.assertTrue(data['verified'])
        self.assertEqual(data['info']['catalog_id'], 'anthropic/claude-sonnet-4.6')
        self.assertEqual(data['info']['output_cost_per_million'], 15.0)

    @patch('apps.ai_providers.model_lookup.requests.get', return_value=_response(CATALOG))
    @patch('apps.ai_providers.providers.openai_provider.OpenAIChatProvider.test_connection', return_value={'ok': True})
    @patch('apps.ai_providers.providers.openai_provider.OpenAIChatProvider.list_models', return_value=[])
    def test_provider_without_model_list_is_checked_with_a_test_call(self, _list, test, _get):
        data = self.lookup(provider='grok', model='gpt-4o-mini').json()
        self.assertTrue(data['verified'])
        self.assertEqual(data['method'], 'test_call')
        test.assert_called_once()
        # Grok's own model is only x-ai's listing, never another vendor's namesake.
        self.assertIsNone(data['info'])
        self.assertIn('no listing', data['info_detail'])

    @patch('apps.ai_providers.model_lookup.requests.get')
    def test_openrouter_uses_its_own_catalog(self, public_get):
        with patch('requests.Session.get', return_value=_response(CATALOG)) as session_get:
            data = self.lookup(provider='openrouter', model='claude-sonnet-4.6').json()
            ambiguous = self.lookup(provider='openrouter', model='gpt-4o-mini').json()
        public_get.assert_not_called()
        self.assertEqual(session_get.call_count, 2)
        self.assertTrue(data['verified'])
        self.assertEqual(data['model'], 'anthropic/claude-sonnet-4.6')
        self.assertEqual(data['info_source'], 'provider')
        self.assertEqual(data['info']['context_length'], 200000)
        # Two vendors list that name: not guessed, both offered.
        self.assertFalse(ambiguous['verified'])
        self.assertEqual(set(ambiguous['suggestions']), {'openai/gpt-4o-mini', 'someone/gpt-4o-mini'})

    def test_requires_a_name(self):
        response = self.lookup(model='  ')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], 'Enter a model name to look up.')
