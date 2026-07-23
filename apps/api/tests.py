from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.chatlens_core.models import SystemSettings
from apps.tenancy.models import CommunicationAccount, Company, CompanyMembership, ConnectionProvider
from apps.trading.models import FormattedPriceList, Inquiry, Product, PromptConfig
from apps.whatsapp_bridge.models import WhatsAppAccount


class TenantScopedApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.user_a = user_model.objects.create_user(username='user_a', password='pw', email='a@example.com')
        cls.user_b = user_model.objects.create_user(username='user_b', password='pw', email='b@example.com')
        cls.control_admin = user_model.objects.create_user(username='control_admin', password='pw', email='control@example.com')

        cls.company_a = Company.objects.create(name='Company A', slug='company-a', industry_type=Company.INDUSTRY_TRADING)
        cls.company_b = Company.objects.create(name='Company B', slug='company-b', industry_type=Company.INDUSTRY_TRADING)
        cls.control_company = Company.objects.filter(company_type=Company.TYPE_CONTROL).first()
        if cls.control_company is None:
            cls.control_company = Company.objects.create(name='Control Company', slug='control-company', company_type=Company.TYPE_CONTROL)
        CompanyMembership.objects.create(company=cls.company_a, user=cls.user_a, role=CompanyMembership.ROLE_SUPER_USER)
        CompanyMembership.objects.create(company=cls.company_b, user=cls.user_a, role=CompanyMembership.ROLE_ADMIN)
        CompanyMembership.objects.create(company=cls.company_b, user=cls.user_b, role=CompanyMembership.ROLE_SUPER_USER)
        CompanyMembership.objects.create(company=cls.control_company, user=cls.control_admin, role=CompanyMembership.ROLE_SUPER_USER)

        provider = ConnectionProvider.objects.get(key='baileys')
        comm_a = CommunicationAccount.objects.create(
            company=cls.company_a,
            provider=provider,
            channel='whatsapp',
            name='A WhatsApp',
        )
        comm_b = CommunicationAccount.objects.create(
            company=cls.company_b,
            provider=provider,
            channel='whatsapp',
            name='B WhatsApp',
        )
        cls.account_a = WhatsAppAccount.objects.create(
            owner=cls.user_a,
            communication_account=comm_a,
            display_name='Account A',
            phone_number='971500000001',
        )
        cls.account_b = WhatsAppAccount.objects.create(
            owner=cls.user_b,
            communication_account=comm_b,
            display_name='Account B',
            phone_number='971500000002',
        )
        Product.objects.create(company=cls.company_a, name='Product A', brand='Brand')
        Product.objects.create(company=cls.company_b, name='Product B', brand='Brand')
        cls.product_a = Product.objects.get(company=cls.company_a)
        cls.product_b = Product.objects.get(company=cls.company_b)
        cls.inquiry_a = Inquiry.objects.create(
            company=cls.company_a,
            account=cls.account_a,
            inquiry_type='buy',
            products=[{'canonical_name': 'Placeholder'}],
            summary='Need one unit',
            dedup_key='buy:test:1:contact-a',
            source_type='direct',
            first_seen_at='2026-07-22T10:00:00Z',
        )
        PromptConfig.objects.create(
            company=cls.company_a,
            key=PromptConfig.KEY_PRODUCT_EXTRACTION,
            label='Product Extraction (bulk import)',
            body='Tenant A prompt',
        )
        PromptConfig.objects.create(
            company=cls.company_b,
            key=PromptConfig.KEY_PRODUCT_EXTRACTION,
            label='Product Extraction (bulk import)',
            body='Tenant B prompt',
        )
        FormattedPriceList.objects.create(
            company=cls.company_a,
            body='Price list A',
        )
        FormattedPriceList.objects.create(
            company=cls.company_b,
            body='Price list B',
        )
        SystemSettings.objects.create(
            company=cls.company_a,
            key='trading_wts_reply_settings',
            value='{"heading":"A Heading"}',
        )
        SystemSettings.objects.create(
            company=cls.company_b,
            key='trading_wts_reply_settings',
            value='{"heading":"B Heading"}',
        )

    def setUp(self):
        self.client = APIClient()

    def test_accounts_list_is_company_scoped(self):
        self.client.force_authenticate(self.user_a)
        resp = self.client.get('/api/accounts/')
        self.assertEqual(resp.status_code, 200)
        ids = {row['id'] for row in resp.json()}
        self.assertEqual(ids, {self.account_a.id})

    def test_auth_me_exposes_current_company_context(self):
        self.client.force_authenticate(self.user_a)
        resp = self.client.get('/api/auth/me/')
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertEqual(payload['username'], 'user_a')
        self.assertEqual(payload['current_company']['id'], self.company_a.id)
        self.assertEqual(payload['current_company']['name'], 'Company A')
        self.assertEqual(payload['current_company']['role'], CompanyMembership.ROLE_SUPER_USER)
        self.assertEqual({m['company']['id'] for m in payload['memberships']}, {self.company_a.id, self.company_b.id})

    def test_select_company_changes_scoped_workspace(self):
        resp = self.client.post('/api/auth/login/', {'username': 'user_a', 'password': 'pw'}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['current_company']['id'], self.company_a.id)

        resp = self.client.post('/api/auth/select-company/', {'company_id': self.company_b.id}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['current_company']['id'], self.company_b.id)

        resp = self.client.get('/api/products/')
        self.assertEqual(resp.status_code, 200)
        names = {row['name'] for row in resp.json()}
        self.assertEqual(names, {'Product B'})

    def test_products_list_is_company_scoped(self):
        self.client.force_authenticate(self.user_a)
        resp = self.client.get('/api/products/')
        self.assertEqual(resp.status_code, 200)
        names = {row['name'] for row in resp.json()}
        self.assertEqual(names, {'Product A'})

    def test_creating_whatsapp_account_binds_to_default_company_and_provider(self):
        self.client.force_authenticate(self.user_a)
        resp = self.client.post('/api/accounts/', {
            'display_name': 'New Account',
            'phone_number': '971500000010',
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        account = WhatsAppAccount.objects.get(pk=resp.json()['id'])
        self.assertEqual(account.owner_id, self.user_a.id)
        self.assertIsNotNone(account.communication_account_id)
        self.assertEqual(account.communication_account.company_id, self.company_a.id)
        self.assertEqual(account.communication_account.provider.key, 'baileys')
        self.assertIsNotNone(account.primary_endpoint_id)
        self.assertEqual(account.primary_endpoint.value, '971500000010')

    def test_bulk_inventory_update_cannot_modify_other_company_product(self):
        self.client.force_authenticate(self.user_a)
        resp = self.client.post('/api/products/bulk-update-inventory/', {
            'items': [
                {'product_id': self.product_b.id, 'qty': 99},
            ],
        }, format='json')
        self.assertEqual(resp.status_code, 200)
        self.product_b.refresh_from_db()
        self.assertEqual(self.product_b.qty, 0)
        self.assertEqual(resp.json()['updated'], [])

    def test_inquiry_correct_match_rejects_other_company_product(self):
        self.client.force_authenticate(self.user_a)
        resp = self.client.post(
            f'/api/inquiries/{self.inquiry_a.id}/correct-match/',
            {'index': 0, 'product_id': self.product_b.id},
            format='json',
        )
        self.assertEqual(resp.status_code, 400)
        self.inquiry_a.refresh_from_db()
        self.assertEqual(self.inquiry_a.products[0], {'canonical_name': 'Placeholder'})

    def test_prompt_configs_are_company_scoped(self):
        self.client.force_authenticate(self.user_a)
        resp = self.client.get('/api/prompts/')
        self.assertEqual(resp.status_code, 200)
        payload = {row['key']: row for row in resp.json()}
        self.assertEqual(payload[PromptConfig.KEY_PRODUCT_EXTRACTION]['body'], 'Tenant A prompt')

    def test_formatted_price_list_is_company_scoped(self):
        self.client.force_authenticate(self.user_a)
        resp = self.client.get('/api/products/price-list/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['body'], 'Price list A')

    def test_trading_settings_are_company_scoped(self):
        self.client.force_authenticate(self.user_a)
        resp = self.client.get('/api/trading-settings/wts-reply/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['heading'], 'A Heading')

    def test_control_admin_can_list_companies(self):
        self.client.force_authenticate(self.control_admin)
        resp = self.client.get('/api/admin/companies/')
        self.assertEqual(resp.status_code, 200)
        company_names = {row['name'] for row in resp.json()}
        self.assertIn('Company A', company_names)
        self.assertIn(self.control_company.name, company_names)

    def test_regular_tenant_cannot_access_control_admin_endpoints(self):
        self.client.force_authenticate(self.user_a)
        resp = self.client.get('/api/admin/companies/')
        self.assertEqual(resp.status_code, 403)

    def test_control_admin_can_enroll_company(self):
        self.client.force_authenticate(self.control_admin)
        resp = self.client.post('/api/admin/companies/enroll/', {
            'company_name': 'Company C',
            'industry_type': Company.INDUSTRY_REAL_ESTATE,
            'email': 'c-admin@example.com',
            'username': 'company_c_admin',
            'password': 'pw123456',
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(Company.objects.filter(name='Company C', industry_type=Company.INDUSTRY_REAL_ESTATE).exists())

    def test_control_admin_can_create_company_user(self):
        self.client.force_authenticate(self.control_admin)
        resp = self.client.post('/api/admin/users/', {
            'company_id': self.company_a.id,
            'email': 'new-user@example.com',
            'username': 'company_a_user',
            'password': 'pw123456',
            'role': CompanyMembership.ROLE_MANAGER,
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(
            CompanyMembership.objects.filter(
                company=self.company_a,
                user__username='company_a_user',
                role=CompanyMembership.ROLE_MANAGER,
            ).exists()
        )
