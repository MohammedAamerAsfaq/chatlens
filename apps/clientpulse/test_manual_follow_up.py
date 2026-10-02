from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient

from apps.clientpulse.models import ClientActivity, ClientProfile, ClientPulseSettings, ContactConsent
from apps.task_management.models import BackgroundTask
from apps.tenancy.models import (
    CommunicationAccount, Company, CompanyContact, CompanyMembership, ConnectionProvider,
)
from apps.whatsapp_bridge.models import OutboundAsset, OutboundMessage, WhatsAppAccount, WhatsAppContact


class ManualFollowUpTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name='Follow Up Co', slug='follow-up-co')
        self.other = Company.objects.create(name='Other Follow Up', slug='other-follow-up')
        self.user = get_user_model().objects.create_user('follow-up-owner')
        self.membership = CompanyMembership.objects.create(
            company=self.company, user=self.user, role=CompanyMembership.ROLE_SUPER_USER,
        )
        provider, _ = ConnectionProvider.objects.get_or_create(
            key='follow-up-baileys',
            defaults={'name': 'Follow Up Baileys', 'channel': 'whatsapp'},
        )
        communication = CommunicationAccount.objects.create(
            company=self.company, provider=provider, channel='whatsapp', name='Sales WhatsApp',
        )
        self.account = WhatsAppAccount.objects.create(
            owner=self.user, communication_account=communication,
            display_name='Sales WhatsApp', outbound_sending_enabled=True,
            direct_sending_enabled=True, image_sending_enabled=True,
        )
        contact = CompanyContact.objects.create(company=self.company, display_name='Follow Up Client')
        self.profile = ClientProfile.objects.create(
            company=self.company, contact=contact, owner=self.membership, created_by=self.user,
        )
        self.wa_contact = WhatsAppContact.objects.create(
            account=self.account, company_contact=contact,
            wa_contact_id='971500001111@s.whatsapp.net', display_name='Follow Up Client',
        )
        ClientPulseSettings.objects.create(company=self.company)
        self.client = APIClient(); self.client.force_authenticate(self.user)

    def _send(self, **overrides):
        payload = {
            'whatsapp_contact_id': self.wa_contact.pk,
            'text': 'Checking in about your latest requirement.',
            'idempotency_key': 'manual-follow-up-1',
        }
        payload.update(overrides)
        return self.client.post(
            f'/api/clientpulse/clients/{self.profile.pk}/follow-up/', payload, format='json',
        )

    def test_queues_once_and_projects_live_outbound_status(self):
        first = self._send()
        second = self._send()
        self.assertEqual(first.status_code, 201, first.data)
        self.assertEqual(second.status_code, 200, second.data)
        self.assertEqual(OutboundMessage.objects.count(), 1)
        outbound = OutboundMessage.objects.get()
        self.assertEqual(outbound.status, OutboundMessage.STATUS_QUEUED)
        self.assertEqual(BackgroundTask.objects.filter(task_key='whatsapp.send_message').count(), 1)
        self.assertEqual(ClientActivity.objects.filter(source_model='outbound_message').count(), 1)

        outbound.status = OutboundMessage.STATUS_DELIVERED
        outbound.save(update_fields=['status', 'updated_at'])
        timeline = self.client.get(
            f'/api/clientpulse/clients/{self.profile.pk}/timeline/',
        ).data
        self.assertEqual(timeline[0]['outbound']['status'], 'delivered')

    def test_do_not_contact_is_hard_blocked(self):
        self.profile.do_not_contact = True
        self.profile.do_not_contact_reason = 'Customer requested no contact.'
        self.profile.save()
        response = self._send()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['code'], 'client_do_not_contact')
        self.assertFalse(OutboundMessage.objects.exists())

    def test_enforced_consent_requires_granted_follow_up(self):
        settings = ClientPulseSettings.objects.get(company=self.company)
        settings.consent_mode = 'enforced'; settings.save()
        blocked = self._send()
        self.assertEqual(blocked.status_code, 400)
        self.assertEqual(blocked.data['code'], 'follow_up_consent_unknown')
        ContactConsent.objects.create(
            company=self.company, profile=self.profile,
            channel='whatsapp', purpose='follow_up', status='granted',
        )
        self.assertEqual(self._send().status_code, 201)

    def test_new_chat_requires_explicit_confirmation(self):
        self.wa_contact.is_existing_chat = False
        self.wa_contact.save(update_fields=['is_existing_chat', 'updated_at'])
        response = self._send()
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data['code'], 'likely_new_chat_confirmation_required')
        self.assertFalse(OutboundMessage.objects.exists())

    def test_foreign_contact_and_asset_are_rejected(self):
        other_user = get_user_model().objects.create_user('follow-up-other')
        other_communication = CommunicationAccount.objects.create(
            company=self.other, provider=self.account.communication_account.provider,
            channel='whatsapp', name='Foreign WhatsApp',
        )
        other_account = WhatsAppAccount.objects.create(
            owner=other_user, communication_account=other_communication,
        )
        other_contact = WhatsAppContact.objects.create(
            account=other_account, wa_contact_id='971500009999@s.whatsapp.net',
        )
        response = self._send(whatsapp_contact_id=other_contact.pk)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['code'], 'whatsapp_contact_not_linked')

        foreign_asset = OutboundAsset.objects.create(
            company=self.other, original_filename='foreign.png', mime_type='image/png',
            size_bytes=3, sha256='0' * 64,
            file=SimpleUploadedFile('foreign.png', b'png', content_type='image/png'),
        )
        response = self._send(asset_id=foreign_asset.pk, idempotency_key='foreign-asset')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['code'], 'outbound_asset_not_found')

    def test_assigned_scope_cannot_send_for_unassigned_client(self):
        agent = get_user_model().objects.create_user('follow-up-agent')
        CompanyMembership.objects.create(
            company=self.company, user=agent, role=CompanyMembership.ROLE_USER,
        )
        self.client.force_authenticate(agent)
        response = self._send()
        self.assertEqual(response.status_code, 404)
