from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.tenancy.models import Company, CommunicationAccount, ConnectionProvider
from apps.tenancy.testing import create_member
from apps.trading.models import MessageClassification, TradingMessageReview
from apps.whatsapp_bridge.models import WhatsAppAccount, WhatsAppChat, WhatsAppMessage


class TradingReviewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='reviewer')
        self.company = Company.objects.create(name='Review Co', slug='review-co', industry_type=Company.INDUSTRY_TRADING)
        create_member(company=self.company, user=self.user, role='super_user')
        provider = ConnectionProvider.objects.get(key='baileys')
        def message(company, key):
            comm = CommunicationAccount.objects.create(company=company, provider=provider, channel='whatsapp', name=key)
            account = WhatsAppAccount.objects.create(owner=self.user, communication_account=comm, display_name=key, phone_number=key)
            chat = WhatsAppChat.objects.create(account=account, wa_chat_id=key, chat_type='individual')
            msg = WhatsAppMessage.objects.create(account=account, chat=chat, provider_message_id=key, direction='inbound', message_type='text', message_text='Need 2 phones', message_time=timezone.now())
            MessageClassification.objects.create(message=msg, is_inquiry=True, inquiry_type='buy', products=[{'canonical_name': 'phones'}])
            return msg
        self.message = message(self.company, 'one')
        other = Company.objects.create(name='Other Co', slug='other-review-co', industry_type=Company.INDUSTRY_TRADING)
        self.foreign = message(other, 'two')
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_review_records_snapshot_and_excludes_reviewed(self):
        url = '/api/trading-ai-review/'
        result = self.client.get(url + 'next/')
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()['message_id'], self.message.id)
        label = {'is_inquiry': True, 'direction': 'buy', 'products': [{'name': 'phones', 'quantity': '2'}]}
        result = self.client.post(url + 'submit/', {'message_id': self.message.id, 'label': label}, format='json')
        self.assertEqual(result.status_code, 201, result.content)
        review = TradingMessageReview.objects.get()
        self.assertEqual(review.source_text, 'Need 2 phones')
        self.assertEqual(review.reviewed_by, self.user)
        self.assertEqual(review.label['products'][0]['quantity'], '2')
        self.assertEqual(self.client.get(url + 'next/').json(), {'done': True})
        self.assertEqual(self.client.post(url + 'submit/', {'message_id': self.message.id, 'label': label}, format='json').status_code, 409)

    def test_cannot_submit_foreign_message_or_inconsistent_label(self):
        url = '/api/trading-ai-review/submit/'
        label = {'is_inquiry': False, 'direction': '', 'products': []}
        self.assertEqual(self.client.post(url, {'message_id': self.foreign.id, 'label': label}, format='json').status_code, 404)
        label['direction'] = 'buy'
        self.assertEqual(self.client.post(url, {'message_id': self.message.id, 'label': label}, format='json').status_code, 400)
        self.assertFalse(TradingMessageReview.objects.exists())

