from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.clientpulse.models import ClientProfile
from apps.tenancy.models import (
    CommunicationAccount, Company, CompanyContact, CompanyMembership,
    ConnectionProvider,
)
from apps.whatsapp_bridge.models import (
    ChatType, MessageDirection, MessageType, WhatsAppAccount, WhatsAppChat,
    WhatsAppContact, WhatsAppGroup, WhatsAppMessage,
)


class ClientConversationHistoryTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name='History Company', slug='history-company')
        self.admin = get_user_model().objects.create_user('history-admin')
        CompanyMembership.objects.create(
            company=self.company, user=self.admin, role=CompanyMembership.ROLE_SUPER_USER,
        )
        self.member = get_user_model().objects.create_user('history-member')
        self.member_membership = CompanyMembership.objects.create(
            company=self.company, user=self.member, role=CompanyMembership.ROLE_USER,
        )
        self.provider = ConnectionProvider.objects.create(
            key='history-baileys', name='History Baileys', channel='whatsapp',
        )
        self.contact = CompanyContact.objects.create(
            company=self.company, display_name='History Client',
        )
        self.profile = ClientProfile.objects.create(
            company=self.company, contact=self.contact, owner=self.member_membership,
            created_by=self.admin,
        )
        self.admin_account, self.admin_contact = self._account_contact(
            self.admin, 'Admin WhatsApp', '971500000001',
        )
        self.member_account, self.member_contact = self._account_contact(
            self.member, 'Member WhatsApp', '971500000002',
        )
        self.admin_message = self._message(
            self.admin_account, self.admin_contact, 'admin-message', 'Admin account message',
        )
        self.member_message = self._message(
            self.member_account, self.member_contact, 'member-message', 'Member account message',
            timezone.now() + timedelta(seconds=1),
        )
        self.client = APIClient()

    def _account_contact(self, owner, name, number):
        communication = CommunicationAccount.objects.create(
            company=self.company, provider=self.provider, channel='whatsapp', name=name,
        )
        account = WhatsAppAccount.objects.create(
            owner=owner, communication_account=communication, display_name=name,
        )
        contact = WhatsAppContact.objects.create(
            account=account, company_contact=self.contact,
            wa_contact_id=f'{number}@s.whatsapp.net', phone_number=number,
            display_name='History Client',
        )
        return account, contact

    def _message(self, account, contact, provider_id, text, message_time=None):
        chat = WhatsAppChat.objects.create(
            account=account, contact=contact, wa_chat_id=contact.wa_contact_id,
            chat_type=ChatType.INDIVIDUAL,
        )
        return WhatsAppMessage.objects.create(
            account=account, chat=chat, contact=contact,
            provider_message_id=provider_id, direction=MessageDirection.INBOUND,
            message_type=MessageType.TEXT, message_text=text,
            message_time=message_time or timezone.now(),
        )

    def test_admin_sees_history_from_all_linked_company_accounts(self):
        self.client.force_authenticate(self.admin)
        response = self.client.get(
            f'/api/clientpulse/clients/{self.profile.pk}/conversations/',
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['count'], 2)
        self.assertEqual(len(response.data['accounts']), 2)
        account_payloads = {item['id']: item for item in response.data['accounts']}
        self.assertEqual(
            account_payloads[self.admin_account.pk]['whatsapp_contact_id'],
            self.admin_contact.pk,
        )
        self.assertEqual(response.data['results'][0]['id'], self.member_message.pk)

    def test_sender_name_distinguishes_customer_and_account(self):
        outbound = WhatsAppMessage.objects.create(
            account=self.admin_account, chat=self.admin_message.chat,
            contact=self.admin_contact, provider_message_id='admin-outbound',
            direction=MessageDirection.OUTBOUND, message_type=MessageType.TEXT,
            message_text='Account reply', message_time=timezone.now() + timedelta(minutes=1),
        )
        self.client.force_authenticate(self.admin)

        response = self.client.get(
            f'/api/clientpulse/clients/{self.profile.pk}/conversations/',
            {'account_id': self.admin_account.pk},
        )

        self.assertEqual(response.status_code, 200, response.data)
        messages = {item['id']: item for item in response.data['results']}
        self.assertEqual(messages[self.admin_message.pk]['sender_name'], 'History Client')
        self.assertEqual(messages[outbound.pk]['sender_name'], 'Admin WhatsApp')

    def test_account_filter_returns_only_selected_linked_account(self):
        self.client.force_authenticate(self.admin)
        response = self.client.get(
            f'/api/clientpulse/clients/{self.profile.pk}/conversations/',
            {'account_id': self.admin_account.pk},
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['id'], self.admin_message.pk)

    def test_regular_user_sees_only_an_owned_linked_account(self):
        self.client.force_authenticate(self.member)
        response = self.client.get(
            f'/api/clientpulse/clients/{self.profile.pk}/conversations/',
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['accounts'][0]['id'], self.member_account.pk)
        self.assertEqual(response.data['results'][0]['id'], self.member_message.pk)

    def test_group_messages_are_not_included(self):
        group_chat = WhatsAppChat.objects.create(
            account=self.member_account, contact=self.member_contact,
            wa_chat_id='120000000000@g.us', chat_type=ChatType.GROUP,
        )
        WhatsAppMessage.objects.create(
            account=self.member_account, chat=group_chat, contact=self.member_contact,
            provider_message_id='group-message', direction=MessageDirection.INBOUND,
            message_type=MessageType.TEXT, message_text='Group content',
            message_time=timezone.now(),
        )
        self.client.force_authenticate(self.admin)

        response = self.client.get(
            f'/api/clientpulse/clients/{self.profile.pk}/conversations/',
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['count'], 2)

    def test_group_and_announcement_sections_only_show_client_messages(self):
        group_chat = WhatsAppChat.objects.create(
            account=self.member_account, wa_chat_id='120000000001@g.us',
            chat_type=ChatType.GROUP, name='Sales Group',
        )
        WhatsAppGroup.objects.create(
            account=self.member_account, chat=group_chat,
            wa_group_id=group_chat.wa_chat_id, name=group_chat.name,
        )
        announcement_chat = WhatsAppChat.objects.create(
            account=self.member_account, wa_chat_id='120000000002@g.us',
            chat_type=ChatType.GROUP, name='Sales Announcements',
        )
        WhatsAppGroup.objects.create(
            account=self.member_account, chat=announcement_chat,
            wa_group_id=announcement_chat.wa_chat_id, name=announcement_chat.name,
            announce=True,
        )
        group_message = WhatsAppMessage.objects.create(
            account=self.member_account, chat=group_chat, contact=self.member_contact,
            provider_message_id='client-group-message', direction=MessageDirection.INBOUND,
            message_type=MessageType.TEXT, message_text='Client group message',
            message_time=timezone.now(),
        )
        announcement_message = WhatsAppMessage.objects.create(
            account=self.member_account, chat=announcement_chat, contact=self.member_contact,
            provider_message_id='client-announcement-message', direction=MessageDirection.INBOUND,
            message_type=MessageType.TEXT, message_text='Client announcement message',
            message_time=timezone.now(),
        )
        unrelated = WhatsAppContact.objects.create(
            account=self.member_account, wa_contact_id='971500009999@s.whatsapp.net',
            phone_number='971500009999', display_name='Unrelated Sender',
        )
        WhatsAppMessage.objects.create(
            account=self.member_account, chat=group_chat, contact=unrelated,
            provider_message_id='unrelated-group-message', direction=MessageDirection.INBOUND,
            message_type=MessageType.TEXT, message_text='Unrelated group message',
            message_time=timezone.now(),
        )
        self.client.force_authenticate(self.admin)

        groups = self.client.get(
            f'/api/clientpulse/clients/{self.profile.pk}/conversations/',
            {'conversation_type': 'group'},
        )
        announcements = self.client.get(
            f'/api/clientpulse/clients/{self.profile.pk}/conversations/',
            {'conversation_type': 'announcement'},
        )

        self.assertEqual(groups.status_code, 200, groups.data)
        self.assertEqual([item['id'] for item in groups.data['results']], [group_message.pk])
        self.assertEqual(groups.data['results'][0]['chat_name'], 'Sales Group')
        self.assertEqual(groups.data['results'][0]['conversation_type'], 'group')
        self.assertEqual(
            [item['id'] for item in announcements.data['results']],
            [announcement_message.pk],
        )
        self.assertEqual(announcements.data['results'][0]['conversation_type'], 'announcement')

    def test_invalid_conversation_type_is_rejected(self):
        self.client.force_authenticate(self.admin)
        response = self.client.get(
            f'/api/clientpulse/clients/{self.profile.pk}/conversations/',
            {'conversation_type': 'community'},
        )
        self.assertEqual(response.status_code, 400)
