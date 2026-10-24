from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta

from apps.tenancy.models import Company, CompanyMembership, CommunicationAccount, ConnectionProvider
from apps.tenancy.models import (
    AuthorizationAuditEvent, CommunicationAccountAssignment, CompanyRole,
    MembershipRoleAssignment,
)
from apps.tenancy.services.enrollment_service import CompanyEnrollmentService
from apps.tenancy.services.access import can_user_access_company, visible_accounts_queryset
from apps.tenancy.services.authorization import effective_permission_grants
from apps.chatlens_core.models import SystemSettings
from apps.whatsapp_bridge.models import WhatsAppAccount, WhatsAppChat, WhatsAppContact, WhatsAppMessage
from apps.trading.models import Inquiry
from apps.trading.services.trading_settings_service import (
    INQUIRY_PRODUCT_SAVE_KEY,
    V2_MATCHING_SETTINGS_KEY,
)
from rest_framework.test import APIClient


class TenancySeedMigrationTests(TestCase):
    def test_control_company_exists(self):
        company = Company.objects.get(slug='control-account')
        self.assertEqual(company.company_type, Company.TYPE_CONTROL)
        self.assertEqual(company.industry_type, Company.INDUSTRY_TRADING)

    def test_default_baileys_provider_exists(self):
        provider = ConnectionProvider.objects.get(key='baileys')
        self.assertEqual(provider.channel, ConnectionProvider.CHANNEL_WHATSAPP)
        self.assertTrue(provider.is_default_for_channel)


class CompanyEnrollmentServiceTests(TestCase):
    def test_enroll_company_creates_company_user_and_membership(self):
        result = CompanyEnrollmentService().enroll_company(
            company_name='Acme Trading',
            email='owner@acme.test',
            username='acme_owner',
            password='secret-pass-123',
            industry_type=Company.INDUSTRY_TRADING,
        )

        company = Company.objects.get(pk=result.company_id)
        user = get_user_model().objects.get(pk=result.user_id)
        membership = CompanyMembership.objects.get(pk=result.membership_id)

        self.assertEqual(company.slug, 'acme-trading')
        self.assertEqual(company.industry_type, Company.INDUSTRY_TRADING)
        self.assertEqual(user.username, 'acme_owner')
        self.assertEqual(membership.company_id, company.pk)
        self.assertEqual(membership.user_id, user.pk)
        self.assertEqual(membership.role, CompanyMembership.ROLE_SUPER_USER)
        self.assertSetEqual(
            set(SystemSettings.objects.filter(company=company).values_list('key', flat=True)),
            {INQUIRY_PRODUCT_SAVE_KEY, V2_MATCHING_SETTINGS_KEY},
        )

    def test_enroll_company_rejects_duplicate_username(self):
        user_model = get_user_model()
        user_model.objects.create_user(
            username='existing_user',
            email='existing@example.com',
            password='pw',
        )

        with self.assertRaisesMessage(ValueError, "Username 'existing_user' already exists"):
            CompanyEnrollmentService().enroll_company(
                company_name='Beta Trading',
                email='beta@example.com',
                username='existing_user',
                password='secret-pass-123',
            )


class CommunicationAccountValidationTests(TestCase):
    def test_channel_must_match_provider_channel(self):
        company = Company.objects.get(slug='control-account')
        provider = ConnectionProvider.objects.get(key='baileys')

        with self.assertRaisesMessage(Exception, 'Provider channel must match communication account channel.'):
            CommunicationAccount.objects.create(
                company=company,
                provider=provider,
                channel=ConnectionProvider.CHANNEL_GMAIL,
                name='Mismatched Account',
            )


class CompanyValidityTests(TestCase):
    def test_validity_is_observational_until_enforcement_is_enabled(self):
        user = get_user_model().objects.create_user('validity-user')
        company = Company.objects.create(
            name='Future Company', slug='future-company',
            valid_from=timezone.localdate() + timedelta(days=1),
            enforce_validity_period=False,
        )
        CompanyMembership.objects.create(
            company=company, user=user, role=CompanyMembership.ROLE_ADMIN,
        )
        self.assertEqual(company.validity_status, 'not_started')
        self.assertTrue(can_user_access_company(user, company.pk))
        company.enforce_validity_period = True
        company.save(update_fields=['enforce_validity_period'])
        self.assertFalse(can_user_access_company(user, company.pk))


class CompanyAuthorizationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        result = CompanyEnrollmentService().enroll_company(
            company_name='RBAC Company', email='owner@rbac.test', username='rbac_owner',
            password='secret-pass-123',
        )
        self.company = Company.objects.get(pk=result.company_id)
        self.owner = get_user_model().objects.get(pk=result.user_id)
        self.owner_membership = CompanyMembership.objects.get(pk=result.membership_id)
        self.client.force_authenticate(self.owner)

    def test_enrollment_seeds_owner_role_and_permissions(self):
        assignment = self.owner_membership.role_assignments.select_related('role').get()
        self.assertEqual(assignment.role.key, 'super_user')
        self.assertTrue(assignment.role.is_owner_role)
        grants, membership = effective_permission_grants(self.owner, self.company)
        self.assertEqual(membership, self.owner_membership)
        self.assertEqual(grants['users.roles.manage'], 'all')
        self.assertEqual(grants['clientpulse.clients.view'], 'all')

    def test_owner_can_create_role_and_assign_it_to_new_user(self):
        created_role = self.client.post(
            '/api/company/roles/',
            {'name': 'CRM Agent', 'key': 'crm-agent'},
            format='json',
        )
        self.assertEqual(created_role.status_code, 201)
        role_id = created_role.json()['id']
        updated_role = self.client.patch(
            f'/api/company/roles/{role_id}/',
            {'permissions': [
                {'code': 'clientpulse.clients.view', 'scope': 'assigned'},
                {'code': 'clientpulse.reminders.manage', 'scope': 'assigned'},
            ]},
            format='json',
        )
        self.assertEqual(updated_role.status_code, 200)

        created_user = self.client.post(
            '/api/company/users/',
            {
                'username': 'crm_agent', 'email': 'agent@rbac.test',
                'password': 'secret-pass-123', 'role_ids': [role_id],
            },
            format='json',
        )
        self.assertEqual(created_user.status_code, 201)
        membership = CompanyMembership.objects.get(pk=created_user.json()['id'])
        grants, _ = effective_permission_grants(membership.user, self.company)
        self.assertEqual(grants, {
            'clientpulse.clients.view': 'assigned',
            'clientpulse.reminders.manage': 'assigned',
        })
        self.assertTrue(AuthorizationAuditEvent.objects.filter(event_type='membership.created').exists())

    def test_last_owner_cannot_remove_owner_role_or_be_suspended(self):
        viewer = CompanyRole.objects.get(company=self.company, key='viewer')
        remove_owner = self.client.patch(
            f'/api/company/users/{self.owner_membership.pk}/',
            {'role_ids': [viewer.pk]},
            format='json',
        )
        suspend_owner = self.client.patch(
            f'/api/company/users/{self.owner_membership.pk}/',
            {'is_active': False},
            format='json',
        )
        self.assertEqual(remove_owner.status_code, 400)
        self.assertEqual(suspend_owner.status_code, 400)
        self.owner_membership.refresh_from_db()
        self.assertTrue(self.owner_membership.is_active)
        self.assertTrue(MembershipRoleAssignment.objects.filter(
            membership=self.owner_membership, role__is_owner_role=True,
        ).exists())

    def test_manager_cannot_manage_roles_and_owner_grants_are_immutable(self):
        result = CompanyEnrollmentService().create_company_user(
            company=self.company, email='manager@rbac.test', username='rbac_manager',
            password='secret-pass-123', role=CompanyMembership.ROLE_MANAGER,
        )
        manager = get_user_model().objects.get(pk=result.user_id)
        self.client.force_authenticate(manager)
        denied = self.client.get('/api/company/roles/')
        self.assertEqual(denied.status_code, 403)

        self.client.force_authenticate(self.owner)
        owner_role = CompanyRole.objects.get(company=self.company, is_owner_role=True)
        rejected = self.client.patch(
            f'/api/company/roles/{owner_role.pk}/',
            {'permissions': []}, format='json',
        )
        self.assertEqual(rejected.status_code, 400)


class CommunicationAccountAuthorizationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        result = CompanyEnrollmentService().enroll_company(
            company_name='Account Scope Company',
            email='owner@account-scope.test',
            username='account_scope_owner',
            password='secret-pass-123',
        )
        self.company = Company.objects.get(pk=result.company_id)
        self.owner = get_user_model().objects.get(pk=result.user_id)
        self.owner_membership = CompanyMembership.objects.get(pk=result.membership_id)
        user_result = CompanyEnrollmentService().create_company_user(
            company=self.company,
            email='agent@account-scope.test',
            username='account_scope_agent',
            password='secret-pass-123',
            role=CompanyMembership.ROLE_USER,
        )
        self.agent = get_user_model().objects.get(pk=user_result.user_id)
        self.agent_membership = CompanyMembership.objects.get(pk=user_result.membership_id)
        provider = ConnectionProvider.objects.get(key='baileys')
        self.account_one = self._create_account(provider, 'Account One')
        self.account_two = self._create_account(provider, 'Account Two')

    def _create_account(self, provider, name):
        communication_account = CommunicationAccount.objects.create(
            company=self.company,
            provider=provider,
            channel=ConnectionProvider.CHANNEL_WHATSAPP,
            name=name,
        )
        return WhatsAppAccount.objects.create(
            owner=self.owner,
            communication_account=communication_account,
            display_name=name,
            worker_session_id=name.lower().replace(' ', '-'),
        )

    def _create_message(self, account, suffix):
        chat = WhatsAppChat.objects.create(
            account=account,
            wa_chat_id=f'9715000000{suffix}@s.whatsapp.net',
            chat_type='individual',
        )
        return WhatsAppMessage.objects.create(
            account=account,
            chat=chat,
            provider_message_id=f'account-scope-{suffix}',
            direction='inbound',
            message_type='text',
            message_text=f'Message {suffix}',
            message_time=timezone.now(),
        )

    def test_owner_sees_every_company_account_and_agent_sees_only_assignments(self):
        owner_ids = set(visible_accounts_queryset(self.owner).values_list('pk', flat=True))
        self.assertSetEqual(owner_ids, {self.account_one.pk, self.account_two.pk})

        self.assertFalse(visible_accounts_queryset(self.agent).exists())
        CommunicationAccountAssignment.objects.create(
            company=self.company,
            communication_account=self.account_one.communication_account,
            membership=self.agent_membership,
            assigned_by=self.owner,
        )
        agent_ids = set(visible_accounts_queryset(self.agent).values_list('pk', flat=True))
        self.assertSetEqual(agent_ids, {self.account_one.pk})

    def test_administrator_sees_all_accounts_and_can_assign_an_agent(self):
        admin_result = CompanyEnrollmentService().create_company_user(
            company=self.company,
            email='admin@account-scope.test',
            username='account_scope_admin',
            password='secret-pass-123',
            role=CompanyMembership.ROLE_ADMIN,
        )
        admin = get_user_model().objects.get(pk=admin_result.user_id)
        admin_ids = set(visible_accounts_queryset(admin).values_list('pk', flat=True))
        self.assertSetEqual(admin_ids, {self.account_one.pk, self.account_two.pk})

        self.client.force_authenticate(admin)
        assigned = self.client.put(
            f'/api/company/users/{self.agent_membership.pk}/communication-accounts/',
            {'communication_account_ids': [self.account_one.communication_account_id]},
            format='json',
        )
        self.assertEqual(assigned.status_code, 200)
        self.assertEqual(
            assigned.json()['communication_account_ids'],
            [self.account_one.communication_account_id],
        )

    def test_admin_can_assign_accounts_and_the_api_enforces_the_assignment(self):
        self.client.force_authenticate(self.owner)
        assigned = self.client.put(
            f'/api/company/users/{self.agent_membership.pk}/communication-accounts/',
            {'communication_account_ids': [self.account_two.communication_account_id]},
            format='json',
        )
        self.assertEqual(assigned.status_code, 200)
        self.assertEqual(
            assigned.json()['communication_account_ids'],
            [self.account_two.communication_account_id],
        )

        self.client.force_authenticate(self.agent)
        response = self.client.get('/api/accounts/')
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        rows = payload.get('results', []) if isinstance(payload, dict) else payload
        self.assertEqual([row['id'] for row in rows], [self.account_two.pk])

    def test_user_cannot_assign_accounts_and_foreign_company_accounts_are_rejected(self):
        self.client.force_authenticate(self.agent)
        denied = self.client.put(
            f'/api/company/users/{self.agent_membership.pk}/communication-accounts/',
            {'communication_account_ids': [self.account_one.communication_account_id]},
            format='json',
        )
        self.assertEqual(denied.status_code, 403)

        other_company = Company.objects.create(name='Other Company', slug='other-account-scope')
        provider = ConnectionProvider.objects.get(key='baileys')
        foreign_account = CommunicationAccount.objects.create(
            company=other_company,
            provider=provider,
            channel=ConnectionProvider.CHANNEL_WHATSAPP,
            name='Foreign Account',
        )
        self.client.force_authenticate(self.owner)
        rejected = self.client.put(
            f'/api/company/users/{self.agent_membership.pk}/communication-accounts/',
            {'communication_account_ids': [foreign_account.pk]},
            format='json',
        )
        self.assertEqual(rejected.status_code, 400)

    def test_inquiry_endpoints_only_return_assigned_account_data(self):
        CommunicationAccountAssignment.objects.create(
            company=self.company,
            communication_account=self.account_one.communication_account,
            membership=self.agent_membership,
            assigned_by=self.owner,
        )
        contact_one = WhatsAppContact.objects.create(
            account=self.account_one,
            wa_contact_id='971500000001@s.whatsapp.net',
            phone_number='971500000001',
            display_name='Visible contact',
        )
        contact_two = WhatsAppContact.objects.create(
            account=self.account_two,
            wa_contact_id='971500000002@s.whatsapp.net',
            phone_number='971500000002',
            display_name='Hidden contact',
        )
        visible = Inquiry.objects.create(
            company=self.company,
            account=self.account_one,
            contact=contact_one,
            inquiry_type='buy',
            summary='Visible inquiry',
            dedup_key='visible-inquiry',
            source_type='direct',
            first_seen_at=timezone.now(),
        )
        hidden = Inquiry.objects.create(
            company=self.company,
            account=self.account_two,
            contact=contact_two,
            inquiry_type='sell',
            summary='Hidden inquiry',
            dedup_key='hidden-inquiry',
            source_type='direct',
            first_seen_at=timezone.now(),
        )

        self.client.force_authenticate(self.agent)
        inquiry_list = self.client.get('/api/inquiries/')
        self.assertEqual(inquiry_list.status_code, 200)
        rows = inquiry_list.json()
        rows = rows.get('results', rows) if isinstance(rows, dict) else rows
        self.assertEqual([row['id'] for row in rows], [visible.pk])

        stats = self.client.get('/api/inquiries/stats/')
        self.assertEqual(stats.status_code, 200)
        self.assertEqual(stats.json()['today']['wtb_total'], 1)
        self.assertEqual(stats.json()['today']['wts_total'], 0)

        hidden_detail = self.client.get(f'/api/inquiries/{hidden.pk}/')
        self.assertEqual(hidden_detail.status_code, 404)

        self.client.force_authenticate(self.owner)
        owner_list = self.client.get('/api/inquiries/')
        owner_rows = owner_list.json()
        owner_rows = owner_rows.get('results', owner_rows) if isinstance(owner_rows, dict) else owner_rows
        self.assertSetEqual({row['id'] for row in owner_rows}, {visible.pk, hidden.pk})

    def test_message_intelligence_only_uses_assigned_accounts(self):
        CommunicationAccountAssignment.objects.create(
            company=self.company,
            communication_account=self.account_one.communication_account,
            membership=self.agent_membership,
            assigned_by=self.owner,
        )
        self._create_message(self.account_one, '11')
        self._create_message(self.account_two, '22')

        self.client.force_authenticate(self.agent)
        aggregate = self.client.get('/api/intelligence/embedding-status/')
        self.assertEqual(aggregate.status_code, 200)
        self.assertEqual(aggregate.json()['total'], 1)

        hidden_status = self.client.get(
            '/api/intelligence/embedding-status/',
            {'account_id': self.account_two.pk},
        )
        self.assertEqual(hidden_status.status_code, 404)

        hidden_search = self.client.post(
            '/api/intelligence/search/',
            {'account_id': self.account_two.pk, 'query': 'Message'},
            format='json',
        )
        self.assertEqual(hidden_search.status_code, 404)

        self.client.force_authenticate(self.owner)
        owner_aggregate = self.client.get('/api/intelligence/embedding-status/')
        self.assertEqual(owner_aggregate.status_code, 200)
        self.assertEqual(owner_aggregate.json()['total'], 2)
