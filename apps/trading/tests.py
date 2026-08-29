from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from apps.tenancy.models import CommunicationAccount, Company, ConnectionProvider
from apps.trading.models import AutomatedPriceCapture, AutomationRule
from apps.trading.services import price_update_automation
from apps.whatsapp_bridge.models import ChatType, WhatsAppAccount, WhatsAppChat, WhatsAppContact, WhatsAppMessage


class AutomatedPriceCapturePersistenceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester', password='pw')
        self.company = Company.objects.create(
            name='Automation Test Co',
            slug='automation-test-co',
            industry_type=Company.INDUSTRY_TRADING,
        )
        self.provider = ConnectionProvider.objects.create(
            key='whatsapp-test',
            name='WhatsApp Test',
            channel=ConnectionProvider.CHANNEL_WHATSAPP,
        )
        self.communication_account = CommunicationAccount.objects.create(
            channel=ConnectionProvider.CHANNEL_WHATSAPP,
            company=self.company,
            provider=self.provider,
            name='Desk Number',
        )
        self.account = WhatsAppAccount.objects.create(
            owner=self.user,
            communication_account=self.communication_account,
            display_name='Desk',
            phone_number='971500000000',
        )
        self.contact = WhatsAppContact.objects.create(
            account=self.account,
            wa_contact_id='971511111111@s.whatsapp.net',
            phone_number='971511111111',
            push_name='Supplier',
        )
        self.chat = WhatsAppChat.objects.create(
            account=self.account,
            wa_chat_id='971511111111@s.whatsapp.net',
            chat_type=ChatType.INDIVIDUAL,
            contact=self.contact,
            last_message_at=timezone.now(),
        )
        self.rule = AutomationRule.objects.create(
            name='Direct auto rule',
            trigger_ai_detect=True,
            action_mode=AutomationRule.ACTION_AUTO,
        )

    def _message(self, provider_message_id='msg-1', text='Expert Devices - Price List'):
        return WhatsAppMessage.objects.create(
            account=self.account,
            chat=self.chat,
            contact=self.contact,
            provider_message_id=provider_message_id,
            sender_number=self.contact.phone_number,
            direction='inbound',
            message_type='text',
            message_text=text,
            message_time=timezone.now(),
        )

    @patch('apps.trading.services.price_update_service.parse_against_inventory')
    def test_parse_failure_creates_persistent_capture(self, parse_against_inventory):
        parse_against_inventory.side_effect = ValueError('bad json payload')
        message = self._message(provider_message_id='parse-fail')

        price_update_automation._process_match(self.rule, message)

        capture = AutomatedPriceCapture.objects.get(message=message)
        self.rule.refresh_from_db()
        self.assertEqual(capture.status, AutomatedPriceCapture.STATUS_PARSE_FAILED)
        self.assertEqual(capture.items, [])
        self.assertIn('bad json payload', capture.error)
        self.assertEqual(self.rule.trigger_count, 1)
        self.assertIsNotNone(self.rule.last_triggered_at)

    @patch('apps.trading.services.price_update_service.parse_against_inventory')
    def test_no_priced_items_creates_persistent_capture(self, parse_against_inventory):
        parse_against_inventory.return_value = [
            {'product_id': None, 'canonical_name': 'Unknown item', 'sale_price': None, 'currency': 'AED'},
        ]
        message = self._message(provider_message_id='no-priced')

        price_update_automation._process_match(self.rule, message)

        capture = AutomatedPriceCapture.objects.get(message=message)
        self.rule.refresh_from_db()
        self.assertEqual(capture.status, AutomatedPriceCapture.STATUS_NO_PRICED_ITEMS)
        self.assertEqual(capture.items, parse_against_inventory.return_value)
        self.assertEqual(capture.error, '')
        self.assertEqual(self.rule.trigger_count, 1)
        self.assertIsNotNone(self.rule.last_triggered_at)

    @patch('apps.trading.services.price_update_automation.apply_capture')
    @patch('apps.trading.services.price_update_service.parse_against_inventory')
    def test_auto_apply_failure_is_persisted(self, parse_against_inventory, apply_capture):
        parse_against_inventory.return_value = [
            {'product_id': 1, 'canonical_name': 'Matched item', 'sale_price': 3860, 'currency': 'AED'},
        ]
        apply_capture.side_effect = RuntimeError('inventory write failed')
        message = self._message(provider_message_id='apply-fail')

        price_update_automation._process_match(self.rule, message)

        capture = AutomatedPriceCapture.objects.get(message=message)
        self.rule.refresh_from_db()
        self.assertEqual(capture.status, AutomatedPriceCapture.STATUS_APPLY_FAILED)
        self.assertEqual(capture.items, parse_against_inventory.return_value)
        self.assertIn('inventory write failed', capture.error)
        self.assertIsNone(capture.applied_at)
        self.assertEqual(self.rule.trigger_count, 1)
