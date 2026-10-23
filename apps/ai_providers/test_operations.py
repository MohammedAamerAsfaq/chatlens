from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.tenancy.models import Company, CompanyMembership
from apps.task_management.models import BackgroundTask
from apps.trading.models import AgentCallLog


class AIOperationsApiTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            name='AI Operations Customer', slug='ai-operations-customer',
            industry_type=Company.INDUSTRY_TRADING,
        )
        self.other_company = Company.objects.create(
            name='Other AI Customer', slug='other-ai-customer',
            industry_type=Company.INDUSTRY_TRADING,
        )
        self.admin = get_user_model().objects.create_user('ai-ops-admin', password='pw')
        self.manager = get_user_model().objects.create_user('ai-ops-manager', password='pw')
        CompanyMembership.objects.create(
            company=self.company, user=self.admin, role=CompanyMembership.ROLE_ADMIN,
        )
        CompanyMembership.objects.create(
            company=self.company, user=self.manager, role=CompanyMembership.ROLE_MANAGER,
        )
        for number in range(30):
            AgentCallLog.objects.create(
                company=self.company, purpose=AgentCallLog.PURPOSE_INQUIRY_GATE_V2,
                provider='openrouter', model=f'company-model-{number}', messages=[],
                response='YES', input_tokens=10, output_tokens=1, duration_ms=20,
            )
        AgentCallLog.objects.create(
            company=self.other_company, purpose=AgentCallLog.PURPOSE_CLASSIFICATION,
            provider='other', model='private-other-model', messages=[], response='NO',
            input_tokens=999, output_tokens=999, duration_ms=20,
        )
        self.client = APIClient()

    def test_company_admin_gets_company_scoped_summary(self):
        self.client.force_authenticate(self.admin)

        response = self.client.get('/api/ai-operations/overview/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['company'], self.company.name)
        self.assertEqual(response.data['counts']['calls'], 30)
        self.assertEqual(response.data['tokens'], {'input': 300, 'output': 30})
        self.assertEqual(response.data['statuses']['calls'], {'succeeded': 30, 'failed': 0})

    def test_records_are_paginated_and_do_not_cross_company_boundary(self):
        self.client.force_authenticate(self.admin)

        response = self.client.get(
            '/api/ai-operations/records/',
            {'section': 'calls', 'page': 2, 'page_size': 10, 'search': 'company-model'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 30)
        self.assertEqual(len(response.data['results']), 10)
        body = str(response.data)
        self.assertNotIn('private-other-model', body)
        self.assertNotIn('api_key', body)

    def test_expanded_task_data_redacts_credentials(self):
        BackgroundTask.objects.create(
            company=self.company, task_key='trading.classify_message', queue_name='ai',
            available_at=timezone.now(), payload={'api_key': 'must-not-leak'},
        )
        self.client.force_authenticate(self.admin)

        response = self.client.get('/api/ai-operations/records/', {'section': 'tasks'})

        self.assertEqual(response.status_code, 200)
        body = str(response.data)
        self.assertNotIn('must-not-leak', body)
        self.assertIn('[redacted]', body)

    def test_non_admin_company_member_cannot_read_ai_operations(self):
        self.client.force_authenticate(self.manager)

        response = self.client.get('/api/ai-operations/overview/')

        self.assertEqual(response.status_code, 403)

    def test_raw_trading_ai_log_is_also_admin_only(self):
        self.client.force_authenticate(self.manager)

        response = self.client.get('/api/agent-logs/')

        self.assertEqual(response.status_code, 403)
