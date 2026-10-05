from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.clientpulse.models import (
    ClientActivity, ClientProfile, ClientPulseSettings, ClientTag, ContactConsent,
)
from apps.tenancy.models import Company, CompanyContact, CompanyMembership
from apps.whatsapp_bridge.models import WhatsAppAccount, WhatsAppContact


class ClientPulseApiTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.company = Company.objects.create(name='CRM Company', slug='crm-company')
        self.other = Company.objects.create(name='Other CRM', slug='other-crm')
        self.owner_user = User.objects.create_user('crm-owner')
        self.owner_membership = CompanyMembership.objects.create(
            company=self.company, user=self.owner_user,
            role=CompanyMembership.ROLE_SUPER_USER,
        )
        self.agent_user = User.objects.create_user('crm-agent')
        self.agent_membership = CompanyMembership.objects.create(
            company=self.company, user=self.agent_user, role=CompanyMembership.ROLE_USER,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.owner_user)

    def _profile(self, name, owner=None, company=None):
        company = company or self.company
        contact = CompanyContact.objects.create(company=company, display_name=name)
        return ClientProfile.objects.create(
            company=company, contact=contact, owner=owner,
            created_by=self.owner_user if company == self.company else None,
        )

    def test_create_and_list_profile_with_identity_and_tag(self):
        tag = ClientTag.objects.create(company=self.company, name='VIP')
        response = self.client.post('/api/clientpulse/clients/', {
            'display_name': 'Acme Buyer', 'lifecycle_stage': 'prospect',
            'owner_id': self.owner_membership.pk, 'tag_ids': [tag.pk],
            'identities': [{'identity_type': 'phone', 'value': '+971 50 100 2000'}],
        }, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['identities'][0]['value'], '+971 50 100 2000')
        self.assertEqual(ClientActivity.objects.filter(title='Client profile created').count(), 1)
        listed = self.client.get('/api/clientpulse/clients/').data
        self.assertEqual(listed['count'], 1)

    def test_company_boundary_hides_foreign_profile(self):
        foreign = self._profile('Foreign', company=self.other)
        response = self.client.get(f'/api/clientpulse/clients/{foreign.pk}/')
        self.assertEqual(response.status_code, 404)

    def test_assigned_scope_only_returns_agent_assignments(self):
        assigned = self._profile('Assigned', owner=self.agent_membership)
        self._profile('Not Assigned', owner=self.owner_membership)
        self.client.force_authenticate(self.agent_user)
        response = self.client.get('/api/clientpulse/clients/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item['id'] for item in response.data['results']], [assigned.pk])

    def test_note_and_consent_changes_create_timeline_events(self):
        profile = self._profile('Timeline Client', owner=self.owner_membership)
        note = self.client.post(
            f'/api/clientpulse/clients/{profile.pk}/notes/',
            {'body': 'Call after delivery.', 'is_pinned': True}, format='json',
        )
        self.assertEqual(note.status_code, 201)
        consent = self.client.put(
            f'/api/clientpulse/clients/{profile.pk}/consents/',
            {'channel': 'whatsapp', 'purpose': 'follow_up', 'status': 'granted'}, format='json',
        )
        self.assertEqual(consent.status_code, 200)
        self.assertTrue(ContactConsent.objects.filter(profile=profile, status='granted').exists())
        timeline = self.client.get(f'/api/clientpulse/clients/{profile.pk}/timeline/').data
        self.assertEqual({item['title'] for item in timeline}, {'Note added', 'Consent updated'})

    def test_cross_company_owner_and_tag_are_rejected(self):
        foreign_user = get_user_model().objects.create_user('foreign-owner')
        foreign_owner = CompanyMembership.objects.create(
            company=self.other, user=foreign_user, role=CompanyMembership.ROLE_ADMIN,
        )
        foreign_tag = ClientTag.objects.create(company=self.other, name='Foreign')
        response = self.client.post('/api/clientpulse/clients/', {
            'display_name': 'Unsafe', 'owner_id': foreign_owner.pk,
            'tag_ids': [foreign_tag.pk],
        }, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(ClientProfile.objects.filter(contact__display_name='Unsafe').exists())

    def test_settings_api_keeps_automated_follow_up_locked_off(self):
        response = self.client.patch('/api/clientpulse/settings/', {
            'consent_mode': 'enforced', 'automated_follow_up_enabled': True,
        }, format='json')
        self.assertEqual(response.status_code, 200)
        settings = ClientPulseSettings.objects.get(company=self.company)
        self.assertEqual(settings.consent_mode, 'enforced')
        self.assertFalse(settings.automated_follow_up_enabled)

    def test_viewer_cannot_create_client(self):
        viewer = get_user_model().objects.create_user('crm-viewer')
        CompanyMembership.objects.create(
            company=self.company, user=viewer, role=CompanyMembership.ROLE_VIEWER,
        )
        self.client.force_authenticate(viewer)
        response = self.client.post(
            '/api/clientpulse/clients/', {'display_name': 'Forbidden'}, format='json',
        )
        self.assertEqual(response.status_code, 403)

    def test_deactivate_preserves_contact_and_client_can_be_reactivated(self):
        profile = self._profile('Retained Contact', owner=self.owner_membership)
        response = self.client.post(f'/api/clientpulse/clients/{profile.pk}/deactivate/')
        self.assertEqual(response.status_code, 200, response.data)
        profile.refresh_from_db(); profile.contact.refresh_from_db()
        self.assertEqual(profile.status, 'paused')
        self.assertTrue(profile.contact.is_active)
        response = self.client.post(f'/api/clientpulse/clients/{profile.pk}/activate/')
        self.assertEqual(response.status_code, 200, response.data)
        profile.refresh_from_db()
        self.assertEqual(profile.status, 'active')
        self.assertEqual(
            list(profile.activities.values_list('title', flat=True)),
            ['Client reactivated', 'Client deactivated'],
        )

    def test_client_list_includes_linked_communication_accounts(self):
        profile = self._profile('Account-linked Client', owner=self.owner_membership)
        account = WhatsAppAccount.objects.create(
            owner=self.owner_user, display_name='Sales Line', phone_number='971500000001',
        )
        WhatsAppContact.objects.create(
            account=account, company_contact=profile.contact,
            wa_contact_id='971511111111@s.whatsapp.net', display_name='Buyer',
        )
        response = self.client.get('/api/clientpulse/clients/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['results'][0]['communication_accounts'], [{
            'id': account.pk, 'name': 'Sales Line', 'phone_number': '971500000001',
            'session_status': account.session_status,
        }])
