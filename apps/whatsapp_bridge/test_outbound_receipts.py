import json

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from apps.tenancy.models import CommunicationAccount, Company, ConnectionProvider
from apps.whatsapp_bridge.models import OutboundMessage, WhatsAppAccount


class OutboundReceiptTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name='Receipt Co', slug='receipt-co')
        provider, _ = ConnectionProvider.objects.get_or_create(
            key='receipt-baileys', defaults={'name': 'Receipt Baileys', 'channel': 'whatsapp'},
        )
        communication = CommunicationAccount.objects.create(
            company=self.company, provider=provider, channel='whatsapp', name='Receipt Account',
        )
        user = get_user_model().objects.create_user('receipt-owner')
        self.account = WhatsAppAccount.objects.create(owner=user, communication_account=communication)
        self.message = OutboundMessage.objects.create(
            company=self.company, whatsapp_account=self.account,
            destination_jid='971500001212@s.whatsapp.net',
            canonical_recipient_key='971500001212@s.whatsapp.net',
            content_payload={'text': 'Hello'}, idempotency_key='receipt-test',
            correlation_id='receipt-correlation', provider_message_id='provider-receipt-1',
            status=OutboundMessage.STATUS_SENT,
        )
        self.client = Client()

    def _receipt(self, status, provider_id='provider-receipt-1'):
        return self.client.post(
            '/api/internal/whatsapp/outbound-receipt/',
            data=json.dumps({
                'worker_session_id': self.account.pk,
                'provider_message_id': provider_id,
                'status': status,
            }),
            content_type='application/json', HTTP_X_INTERNAL_TOKEN='test-token',
        )

    def test_receipts_progress_without_duplicate_or_downgrade(self):
        from django.conf import settings
        settings.INTERNAL_API_TOKEN = 'test-token'
        self.assertTrue(self._receipt('delivered').json()['changed'])
        self.assertFalse(self._receipt('sent').json()['changed'])
        self.assertTrue(self._receipt('read').json()['changed'])
        self.assertFalse(self._receipt('read').json()['changed'])
        self.message.refresh_from_db()
        self.assertEqual(self.message.status, OutboundMessage.STATUS_READ)
        self.assertIsNotNone(self.message.delivered_at)
        self.assertIsNotNone(self.message.read_at)
        self.assertEqual(self.message.events.filter(event_type='delivered').count(), 1)
        self.assertEqual(self.message.events.filter(event_type='read').count(), 1)

    def test_unknown_provider_message_is_acknowledged_without_change(self):
        from django.conf import settings
        settings.INTERNAL_API_TOKEN = 'test-token'
        response = self._receipt('delivered', provider_id='not-chatlens')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['matched'])
