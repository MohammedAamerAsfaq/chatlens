from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta

from apps.tenancy.models import Company, CompanyMembership, CommunicationAccount, ConnectionProvider
from apps.tenancy.models import AuthorizationAuditEvent, CompanyRole, MembershipRoleAssignment
from apps.tenancy.services.enrollment_service import CompanyEnrollmentService
from apps.tenancy.services.access import can_user_access_company
from apps.tenancy.services.authorization import effective_permission_grants
from apps.chatlens_core.models import SystemSettings
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
