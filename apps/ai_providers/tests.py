from django.test import TestCase

from .kiwi_router_service import reserve_agent
from .models import AIProviderConfig, KiwiRouter, KiwiRouterMember, KiwiRouterReservation


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
