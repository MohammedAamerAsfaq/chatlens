from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.clientpulse.models import ClientActivity, ClientProfile
from apps.tenancy.models import (
    CommunicationAccount, Company, CompanyContact, CompanyContactIdentity,
    CompanyMembership, ConnectionProvider,
)
from apps.whatsapp_bridge.models import WhatsAppAccount, WhatsAppContact


class ConversationConversionTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name='Conversation CRM', slug='conversation-crm')
        self.other_company = Company.objects.create(name='Foreign CRM', slug='foreign-crm')
        self.user = get_user_model().objects.create_user('conversation-owner')
        CompanyMembership.objects.create(
            company=self.company, user=self.user, role=CompanyMembership.ROLE_SUPER_USER,
        )
        provider = ConnectionProvider.objects.create(
            key='conversation-baileys', name='Conversation Baileys', channel='whatsapp',
        )
        communication = CommunicationAccount.objects.create(
            company=self.company, provider=provider, channel='whatsapp', name='Primary WhatsApp',
        )
        self.account = WhatsAppAccount.objects.create(
            owner=self.user, communication_account=communication,
        )
        self.whatsapp_contact = WhatsAppContact.objects.create(
            account=self.account,
            wa_contact_id='971500001234@s.whatsapp.net',
            phone_number='971500001234',
            display_name='Conversation Buyer',
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def _convert(self, stage):
        return self.client.post(
            f'/api/clientpulse/conversation-contacts/{self.whatsapp_contact.pk}/convert/',
            {'lifecycle_stage': stage}, format='json',
        )

    def test_creates_linked_profile_and_updates_it_idempotently(self):
        created = self._convert('prospect')
        self.assertEqual(created.status_code, 201, created.data)
        self.whatsapp_contact.refresh_from_db()
        profile = ClientProfile.objects.get(contact=self.whatsapp_contact.company_contact)
        self.assertEqual(profile.lifecycle_stage, 'prospect')
        self.assertEqual(profile.source, 'whatsapp')
        self.assertEqual(profile.preferred_channel, 'whatsapp')
        self.assertEqual(profile.contact.identities.count(), 2)

        updated = self._convert('active_customer')
        self.assertEqual(updated.status_code, 200, updated.data)
        self.assertTrue(updated.data['changed'])
        self.assertEqual(ClientProfile.objects.count(), 1)
        profile.refresh_from_db()
        self.assertEqual(profile.lifecycle_stage, 'active_customer')
        self.assertEqual(ClientActivity.objects.count(), 2)

        unchanged = self._convert('active_customer')
        self.assertEqual(unchanged.status_code, 200)
        self.assertFalse(unchanged.data['created'])
        self.assertFalse(unchanged.data['changed'])
        self.assertEqual(ClientActivity.objects.count(), 2)

    def test_reuses_an_exact_company_contact(self):
        contact = CompanyContact.objects.create(company=self.company, display_name='Existing Buyer')
        CompanyContactIdentity.objects.create(
            contact=contact, identity_type='phone', value='+971 50 000 1234',
        )
        response = self._convert('lead')
        self.assertEqual(response.status_code, 201, response.data)
        self.whatsapp_contact.refresh_from_db()
        self.assertEqual(self.whatsapp_contact.company_contact_id, contact.pk)
        self.assertEqual(ClientProfile.objects.get().contact_id, contact.pk)

    def test_ambiguous_identity_is_rejected_without_creating_a_profile(self):
        for name in ('Duplicate One', 'Duplicate Two'):
            contact = CompanyContact.objects.create(company=self.company, display_name=name)
            CompanyContactIdentity.objects.create(
                contact=contact, identity_type='phone', value='971500001234',
            )
        response = self._convert('lead')
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data['code'], 'ambiguous_contact')
        self.assertFalse(ClientProfile.objects.exists())
        self.whatsapp_contact.refresh_from_db()
        self.assertIsNone(self.whatsapp_contact.company_contact_id)

    def test_foreign_company_contact_is_not_available(self):
        other_user = get_user_model().objects.create_user('foreign-conversation-owner')
        provider = self.account.communication_account.provider
        communication = CommunicationAccount.objects.create(
            company=self.other_company, provider=provider, channel='whatsapp', name='Foreign WhatsApp',
        )
        account = WhatsAppAccount.objects.create(owner=other_user, communication_account=communication)
        foreign = WhatsAppContact.objects.create(
            account=account, wa_contact_id='971500009999@s.whatsapp.net',
        )
        response = self.client.post(
            f'/api/clientpulse/conversation-contacts/{foreign.pk}/convert/',
            {'lifecycle_stage': 'lead'}, format='json',
        )
        self.assertEqual(response.status_code, 404)

    def test_scoped_user_cannot_update_an_unassigned_profile(self):
        contact = CompanyContact.objects.create(company=self.company, display_name='Owner Client')
        profile = ClientProfile.objects.create(
            company=self.company, contact=contact, created_by=self.user,
        )
        self.whatsapp_contact.company_contact = contact
        self.whatsapp_contact.save(update_fields=['company_contact', 'updated_at'])
        agent = get_user_model().objects.create_user('conversation-agent')
        CompanyMembership.objects.create(
            company=self.company, user=agent, role=CompanyMembership.ROLE_USER,
        )
        self.client.force_authenticate(agent)

        response = self._convert('active_customer')

        self.assertEqual(response.status_code, 404)
        profile.refresh_from_db()
        self.assertEqual(profile.lifecycle_stage, 'lead')
