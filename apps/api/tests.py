import json

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils.timezone import now
from rest_framework.test import APIClient
from unittest.mock import patch

from apps.chatlens_core.models import SystemSettings
from apps.tenancy.models import CommunicationAccount, Company, CompanyMembership, ConnectionProvider
from apps.trading.models import FormattedPriceList, Inquiry, MessageClassification, Product, PromptConfig
from apps.trading.services.inquiry_service import process_inquiry
from apps.whatsapp_bridge.models import WhatsAppAccount, WhatsAppChat, WhatsAppContact, WhatsAppMessage


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
        self.assertEqual(payload['current_company']['ai_parsing_enabled'], True)
        self.assertEqual(payload['current_company']['role'], CompanyMembership.ROLE_SUPER_USER)
        self.assertEqual({m['company']['id'] for m in payload['memberships']}, {self.company_a.id, self.company_b.id})

    def test_company_admin_can_toggle_current_company_ai_parsing(self):
        self.client.force_authenticate(self.user_a)

        resp = self.client.patch(
            '/api/auth/current-company-settings/',
            {'ai_parsing_enabled': False},
            format='json',
        )

        self.assertEqual(resp.status_code, 200)
        self.company_a.refresh_from_db()
        self.assertFalse(self.company_a.ai_parsing_enabled)
        self.assertEqual(resp.json()['current_company']['ai_parsing_enabled'], False)

    def test_company_toggle_rejects_non_admin_member(self):
        CompanyMembership.objects.filter(company=self.company_b, user=self.user_a).update(role=CompanyMembership.ROLE_USER)
        self.client.force_authenticate(self.user_a)
        self.client.post('/api/auth/select-company/', {'company_id': self.company_b.id}, format='json')

        resp = self.client.patch(
            '/api/auth/current-company-settings/',
            {'ai_parsing_enabled': False},
            format='json',
        )

        self.assertEqual(resp.status_code, 403)

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

    def test_start_session_sends_persisted_account_settings_to_worker(self):
        self.account_a.sync_history = False
        self.account_a.history_days = 14
        self.account_a.idle_disconnect_minutes = 30
        self.account_a.auto_download_media = False
        self.account_a.save(update_fields=[
            'sync_history',
            'history_days',
            'idle_disconnect_minutes',
            'auto_download_media',
        ])

        class _WorkerResponse:
            status_code = 201

            def json(self):
                return {'status': 'pending_qr'}

        self.client.force_authenticate(self.user_a)
        with patch('apps.api.views.requests.post', return_value=_WorkerResponse()) as post_mock:
            resp = self.client.post(f'/api/accounts/{self.account_a.pk}/start-session/')

        self.assertEqual(resp.status_code, 201)
        self.assertEqual(post_mock.call_count, 1)
        self.assertEqual(post_mock.call_args.kwargs['json'], {
            'session_id': str(self.account_a.pk),
            'sync_history': False,
            'history_days': 14,
            'idle_disconnect_minutes': 30,
            'auto_download_media': False,
        })

    def _restore_upload(self, chats):
        return SimpleUploadedFile(
            'backup.json',
            json.dumps({'chats': chats}).encode('utf-8'),
            content_type='application/json',
        )

    def _restore_chat(self, *message_ids):
        return {
            'wa_chat_id': '971500000099@s.whatsapp.net',
            'chat_type': 'individual',
            'name': 'Restore Contact',
            'messages': [
                {
                    'provider_message_id': message_id,
                    'sender_number': '971500000099',
                    'direction': 'inbound',
                    'message_type': 'text',
                    'message_text': f'Message {message_id}',
                    'message_time': now().isoformat(),
                    'has_media': False,
                }
                for message_id in message_ids
            ],
        }

    def test_restore_messages_reports_inserted_rows_for_clean_backup(self):
        self.client.force_authenticate(self.user_a)

        resp = self.client.post(
            f'/api/accounts/{self.account_a.pk}/restore-messages/',
            {'file': self._restore_upload([self._restore_chat('RESTORE-1', 'RESTORE-2')])},
            format='multipart',
        )

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['restored_messages'], 2)
        self.assertEqual(resp.json()['skipped_existing'], 0)
        self.assertEqual(resp.json()['invalid_rows'], 0)
        self.assertEqual(
            WhatsAppMessage.objects.filter(account=self.account_a, provider_message_id__startswith='RESTORE-').count(),
            2,
        )

    def test_restore_messages_reports_existing_rows_on_repeat_backup(self):
        self.client.force_authenticate(self.user_a)
        backup = [self._restore_chat('RESTORE-REPEAT-1', 'RESTORE-REPEAT-2')]

        first = self.client.post(
            f'/api/accounts/{self.account_a.pk}/restore-messages/',
            {'file': self._restore_upload(backup)},
            format='multipart',
        )
        second = self.client.post(
            f'/api/accounts/{self.account_a.pk}/restore-messages/',
            {'file': self._restore_upload(backup)},
            format='multipart',
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.json()['restored_messages'], 2)
        self.assertEqual(second.json()['restored_messages'], 0)
        self.assertEqual(second.json()['skipped_existing'], 2)

    def test_restore_messages_reports_partial_overlap(self):
        self.client.force_authenticate(self.user_a)
        initial = [self._restore_chat('RESTORE-OVERLAP-1')]
        overlap = [self._restore_chat('RESTORE-OVERLAP-1', 'RESTORE-OVERLAP-2')]

        self.client.post(
            f'/api/accounts/{self.account_a.pk}/restore-messages/',
            {'file': self._restore_upload(initial)},
            format='multipart',
        )
        resp = self.client.post(
            f'/api/accounts/{self.account_a.pk}/restore-messages/',
            {'file': self._restore_upload(overlap)},
            format='multipart',
        )

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['restored_messages'], 1)
        self.assertEqual(resp.json()['skipped_existing'], 1)
        self.assertEqual(
            WhatsAppMessage.objects.filter(account=self.account_a, provider_message_id__startswith='RESTORE-OVERLAP-').count(),
            2,
        )

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

    def test_processed_inquiry_is_bound_to_message_company_and_visible(self):
        contact = WhatsAppContact.objects.create(
            account=self.account_a,
            wa_contact_id='971544732206@s.whatsapp.net',
            push_name='Buyer',
            phone_number='971544732206',
        )
        chat = WhatsAppChat.objects.create(
            account=self.account_a,
            wa_chat_id='971544732206@s.whatsapp.net',
            chat_type='individual',
            contact=contact,
        )
        message = WhatsAppMessage.objects.create(
            account=self.account_a,
            chat=chat,
            contact=contact,
            provider_message_id='MSG-INQUIRY-COMPANY',
            sender_number='971544732206',
            direction='inbound',
            message_type='text',
            message_text='Need Product A',
            message_time=now(),
        )
        classification = MessageClassification.objects.create(
            message=message,
            tags=['wtb'],
            products=[{'product_id': self.product_a.pk, 'canonical_name': 'Product A'}],
            is_inquiry=True,
            inquiry_type='buy',
            ai_summary='Need Product A',
            dedup_key='buy:product-a:1:971544732206',
            raw_response={},
        )

        process_inquiry(message, classification)

        inquiry = Inquiry.objects.get(dedup_key='buy:product-a:1:971544732206')
        self.assertEqual(inquiry.company_id, self.company_a.id)

        self.client.force_authenticate(self.user_a)
        resp = self.client.get('/api/inquiries/')
        self.assertEqual(resp.status_code, 200)
        ids = {row['id'] for row in resp.json()}
        self.assertIn(inquiry.pk, ids)

        resp = self.client.get('/api/inquiries/open-feed/', {'type': 'buy'})
        self.assertEqual(resp.status_code, 200)
        feed_ids = {row['id'] for row in resp.json()['results']}
        self.assertIn(inquiry.pk, feed_ids)

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
