from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from .kiwi_router_service import execute_agent, reserve_agent
from .models import AIProviderConfig, KiwiRouter, KiwiRouterMember, KiwiRouterReservation
from .serializers import KiwiRouterSerializer


class KiwiRouterReservationTests(TestCase):
    def setUp(self):
        self.router = KiwiRouter.objects.create(name='Inquiry router', capability='agent')
        self.first = self._member('DeepSeek', 1, 3)
        self.second = self._member('Gemini', 2, 5)
        self.third = self._member('Nemotron', 3, 2)

    def _member(self, name, priority, rpm_limit):
        config = AIProviderConfig.objects.create(
            display_name=name, provider='deepseek', capability='agent',
            api_key='test-key', model='test-model', is_active=True,
        )
        return KiwiRouterMember.objects.create(
            router=self.router, provider_config=config, priority=priority,
            rpm_limit=rpm_limit,
        )

    def test_ordered_capacity_fill_uses_member_rpm_in_priority_order(self):
        selected_member_ids = []
        for number in range(10):
            selection = reserve_agent(
                self.router.pk, workflow_key='inquiry_pass1',
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
            reserve_agent(self.router.pk, workflow_key='inquiry_pass1', correlation_id=f'message:{number}')

        selection = reserve_agent(self.router.pk, workflow_key='inquiry_pass1', correlation_id='message:full')

        self.assertIsNone(selection.member)
        self.assertIsNotNone(selection.available_at)

    def test_expired_dispatch_no_longer_uses_concurrency_capacity(self):
        self.first.max_concurrency = 1
        self.first.save(update_fields=['max_concurrency'])
        first_selection = reserve_agent(
            self.router.pk, workflow_key='inquiry_pass1', correlation_id='message:active',
        )
        first_selection.reservation.expires_at = timezone.now() - timedelta(seconds=1)
        first_selection.reservation.save(update_fields=['expires_at'])

        replacement = reserve_agent(
            self.router.pk, workflow_key='inquiry_pass1', correlation_id='message:replacement',
        )

        first_selection.reservation.refresh_from_db()
        self.assertEqual(first_selection.reservation.status, KiwiRouterReservation.STATUS_EXPIRED)
        self.assertEqual(replacement.member, self.first)

    def test_used_member_can_be_updated_without_replacing_history(self):
        reserve_agent(self.router.pk, workflow_key='inquiry_pass1', correlation_id='message:history')
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
