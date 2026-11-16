from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.utils.timezone import now
from rest_framework.test import APIClient

from apps.tenancy.models import (
    AuthorizationAuditEvent, CommunicationAccount, CommunicationAccountAssignment, Company,
    CompanyMembership, CompanyRole, ConnectionProvider,
)
from apps.tenancy.services.enrollment_service import CompanyEnrollmentService
from apps.trading.models import InquirySharingRule
from apps.whatsapp_bridge.models import WhatsAppAccount

STRONG = 'Harbor-Violet-58-Kite'


class CompanyUserAdminTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        result = CompanyEnrollmentService().enroll_company(
            company_name='Admin Co', email='owner@admin.test', username='admin_owner', password=STRONG,
        )
        self.company = Company.objects.get(pk=result.company_id)
        self.owner = get_user_model().objects.get(pk=result.user_id)
        self.owner_membership = CompanyMembership.objects.get(pk=result.membership_id)
        self.client.force_authenticate(self.owner)
        self.member = self.create('shoeb', 'shoeb@admin.test')

    def create(self, username, email, role_key='user'):
        role = CompanyRole.objects.get(company=self.company, key=role_key)
        resp = self.client.post('/api/company/users/', {
            'username': username, 'email': email, 'password': STRONG, 'role_ids': [role.pk],
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        return CompanyMembership.objects.select_related('user').get(pk=resp.json()['id'])

    def url(self, membership, suffix=''):
        return f'/api/company/users/{membership.pk}/{suffix}'

    def test_weak_password_is_refused_on_create_and_reset(self):
        role = CompanyRole.objects.get(company=self.company, key='user')
        resp = self.client.post('/api/company/users/', {
            'username': 'weak', 'email': 'weak@admin.test', 'password': '12345678', 'role_ids': [role.pk],
        }, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('too common', resp.json()['detail'])
        self.assertFalse(get_user_model().objects.filter(username='weak').exists())

        resp = self.client.post(self.url(self.member, 'password/'), {'password': 'shoeb123'}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.member.user.refresh_from_db()
        self.assertTrue(self.member.user.check_password(STRONG))
        self.assertTrue(self.client.get('/api/company/users/password-rules/').json()['rules'])

    def test_admin_sets_a_new_password_and_old_sessions_end(self):
        browser = Client()
        browser.force_login(self.member.user)
        self.assertEqual(browser.get('/api/company/users/').status_code, 403)  # signed in, just not allowed

        resp = self.client.post(self.url(self.member, 'password/'), {'password': 'Lantern-Cobalt-73-Reef'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.member.user.refresh_from_db()
        self.assertTrue(self.member.user.check_password('Lantern-Cobalt-73-Reef'))
        self.assertIn(browser.get('/api/company/users/').status_code, (401, 403))
        self.assertNotIn('_auth_user_id', browser.session)
        event = AuthorizationAuditEvent.objects.get(event_type='membership.password_set')
        self.assertNotIn('Lantern', str(event.after_snapshot) + str(event.before_snapshot))

    def test_change_username(self):
        resp = self.client.patch(self.url(self.member), {'username': 'shoeb.k'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.json()['user']['username'], 'shoeb.k')
        self.assertEqual(self.client.patch(self.url(self.member), {'username': 'ADMIN_OWNER'}, format='json').status_code, 400)
        self.assertEqual(self.client.patch(self.url(self.member), {'username': 'bad name'}, format='json').status_code, 400)
        self.assertEqual(self.client.patch(self.url(self.member), {'username': 'x-deleted-1'}, format='json').status_code, 400)

    def test_failed_role_change_does_not_keep_the_new_username(self):
        resp = self.client.patch(self.url(self.member), {'username': 'renamed', 'role_ids': []}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.member.user.refresh_from_db()
        self.assertEqual(self.member.user.username, 'shoeb')

    def test_remove_keeps_records_and_frees_the_username_and_email(self):
        comm = CommunicationAccount.objects.create(
            company=self.company, provider=ConnectionProvider.objects.get(key='baileys'), channel='whatsapp', name='S',
        )
        CommunicationAccountAssignment.objects.create(
            company=self.company, communication_account=comm, membership=self.member,
            access_level=CommunicationAccountAssignment.ACCESS_OWNER,
        )
        account = WhatsAppAccount.objects.create(owner=self.member.user, communication_account=comm, phone_number='97150')
        rule = InquirySharingRule.objects.create(
            company=self.company, owner=self.member.user, recipient=self.owner, started_at=now(),
        )

        resp = self.client.delete(self.url(self.member))
        self.assertEqual(resp.status_code, 204, resp.content)

        user = get_user_model().objects.get(pk=self.member.user_id)
        self.assertTrue(user.username.startswith('shoeb-deleted-'))
        self.assertEqual(user.email, '')
        self.assertFalse(user.is_active)
        self.assertFalse(user.has_usable_password())
        self.assertTrue(WhatsAppAccount.objects.filter(pk=account.pk, owner=user).exists())
        rule.refresh_from_db()
        self.assertIsNotNone(rule.ended_at)
        self.member.refresh_from_db()
        self.assertIsNotNone(self.member.removed_at)
        self.assertEqual(self.member.removed_by, self.owner)
        event = AuthorizationAuditEvent.objects.get(event_type='membership.removed')
        self.assertEqual(event.before_snapshot['user']['username'], 'shoeb')

        listed = [row['user']['username'] for row in self.client.get('/api/company/users/').json()]
        self.assertNotIn(user.username, listed)
        self.assertEqual(self.client.patch(self.url(self.member), {'is_active': True}, format='json').status_code, 409)
        self.assertEqual(self.client.post(self.url(self.member, 'password/'), {'password': STRONG}, format='json').status_code, 409)
        self.create('shoeb', 'shoeb@admin.test')

    def test_cannot_remove_yourself_and_only_owner_touches_owner(self):
        self.assertEqual(self.client.delete(self.url(self.owner_membership)).status_code, 400)
        admin = self.create('helper', 'helper@admin.test', role_key='admin')
        self.client.force_authenticate(admin.user)
        self.assertEqual(self.client.delete(self.url(self.owner_membership)).status_code, 403)
        self.assertEqual(
            self.client.post(self.url(self.owner_membership, 'password/'), {'password': STRONG}, format='json').status_code, 403,
        )
        self.assertEqual(self.client.patch(self.url(self.owner_membership), {'username': 'x'}, format='json').status_code, 403)

    def test_login_shared_with_another_company_is_not_changed_from_here(self):
        other = Company.objects.create(name='Other', slug='other-admin', industry_type=Company.INDUSTRY_TRADING)
        CompanyMembership.objects.create(company=other, user=self.member.user, role=CompanyMembership.ROLE_USER)
        self.assertEqual(self.client.delete(self.url(self.member)).status_code, 409)
        self.assertEqual(self.client.post(self.url(self.member, 'password/'), {'password': STRONG}, format='json').status_code, 409)

    def test_members_without_manage_permission_are_refused(self):
        self.client.force_authenticate(self.member.user)
        self.assertEqual(self.client.delete(self.url(self.owner_membership)).status_code, 403)
        self.assertEqual(self.client.post(self.url(self.owner_membership, 'password/'), {'password': STRONG}, format='json').status_code, 403)
