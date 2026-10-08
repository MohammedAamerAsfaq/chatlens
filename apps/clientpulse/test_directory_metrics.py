from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.clientpulse.models import ClientProfile, ClientReminder
from apps.tenancy.models import (
    CommunicationAccount, Company, CompanyContact, CompanyMembership,
    ConnectionProvider,
)
from apps.whatsapp_bridge.models import (
    ChatType, MessageDirection, MessageType, WhatsAppAccount, WhatsAppChat,
    WhatsAppContact, WhatsAppMessage,
)


class ClientDirectoryMetricsTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name='Metrics Company', slug='metrics-company')
        self.user = get_user_model().objects.create_user('metrics-owner')
        self.membership = CompanyMembership.objects.create(
            company=self.company, user=self.user, role=CompanyMembership.ROLE_SUPER_USER,
        )
        provider = ConnectionProvider.objects.create(
            key='metrics-baileys', name='Metrics Baileys', channel='whatsapp',
        )
        communication = CommunicationAccount.objects.create(
            company=self.company, provider=provider, channel='whatsapp', name='Metrics WhatsApp',
        )
        account = WhatsAppAccount.objects.create(
            owner=self.user, communication_account=communication, display_name='Metrics Account',
        )
        contact = CompanyContact.objects.create(company=self.company, display_name='Metrics Client')
        self.profile = ClientProfile.objects.create(company=self.company, contact=contact)
        wa_contact = WhatsAppContact.objects.create(
            account=account, company_contact=contact,
            wa_contact_id='971500001111@s.whatsapp.net', display_name='Metrics Client',
        )
        chat = WhatsAppChat.objects.create(
            account=account, contact=wa_contact,
            wa_chat_id=wa_contact.wa_contact_id, chat_type=ChatType.INDIVIDUAL,
        )
        now = timezone.now()
        self.last_reply = now - timedelta(hours=2)
        self.last_contact = now - timedelta(hours=1)
        self.next_follow_up = now + timedelta(hours=3)
        WhatsAppMessage.objects.create(
            account=account, chat=chat, contact=wa_contact, provider_message_id='metrics-inbound',
            direction=MessageDirection.INBOUND, message_type=MessageType.TEXT,
            message_text='Customer reply', message_time=self.last_reply,
        )
        WhatsAppMessage.objects.create(
            account=account, chat=chat, contact=None, provider_message_id='metrics-outbound',
            direction=MessageDirection.OUTBOUND, message_type=MessageType.TEXT,
            message_text='Company follow-up', message_time=self.last_contact,
        )
        ClientReminder.objects.create(
            company=self.company, profile=self.profile, title='Completed reminder',
            due_at=now + timedelta(hours=1), status='completed', completed_at=now,
        )
        ClientReminder.objects.create(
            company=self.company, profile=self.profile, title='Next reminder',
            due_at=self.next_follow_up, status='pending',
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_list_derives_contact_reply_and_follow_up_dates(self):
        response = self.client.get('/api/clientpulse/clients/')

        self.assertEqual(response.status_code, 200, response.data)
        item = response.data['results'][0]
        self.assertEqual(item['last_contacted_at'], self.last_contact)
        self.assertEqual(item['last_replied_at'], self.last_reply)
        self.assertEqual(item['next_follow_up_at'], self.next_follow_up)
