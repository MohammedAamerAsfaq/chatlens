from unittest.mock import patch
from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.tenancy.models import CommunicationAccount, Company, ConnectionProvider
from apps.trading.models import AiParseV2Log, AutomatedPriceCapture, AutomationRule, AutomationRuleSource
from apps.trading.services.classification_service import (
    _reconcile_stale_pass1_logs,
    classify_message_v2,
)
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

    @override_settings(BACKGROUND_AUTOMATION_MODE='db_queue')
    @patch('apps.queue_management.services.enqueue_task')
    @patch('apps.whatsapp_bridge.services.ingestion_service.threading.Thread')
    def test_db_queue_mode_enqueues_automation_without_thread_fallback(self, thread, enqueue):
        from apps.whatsapp_bridge.services.ingestion_service import _process_automation_in_background

        message = self._message(provider_message_id='queue-automation')
        from apps.queue_management.runtime_settings import get_task_runtime_settings
        runtime = get_task_runtime_settings()
        runtime.automation_mode = 'db_queue'
        runtime.save(update_fields=['automation_mode', 'updated_at'])
        AutomationRuleSource.objects.create(
            rule=self.rule,
            source_type=AutomationRuleSource.SOURCE_CONTACT,
            contact=self.contact,
        )
        _process_automation_in_background(message.pk)

        enqueue.assert_called_once()
        self.assertEqual(enqueue.call_args.kwargs['task_key'], 'whatsapp.process_automation_rules')
        self.assertEqual(enqueue.call_args.kwargs['payload'], {'version': 1, 'message_id': message.pk, 'rule_id': self.rule.pk})
        thread.assert_not_called()

    @override_settings(BACKGROUND_AUTOMATION_MODE='db_queue')
    @patch('apps.queue_management.services.enqueue_task')
    def test_db_queue_mode_does_not_enqueue_unmatched_message(self, enqueue):
        from apps.whatsapp_bridge.services.ingestion_service import _process_automation_in_background

        message = self._message(provider_message_id='unmatched-automation')
        _process_automation_in_background(message.pk)

        enqueue.assert_not_called()


class V2ClassificationRecoveryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='v2-tester', password='pw')
        self.company = Company.objects.create(
            name='V2 Test Co',
            slug='v2-test-co',
            industry_type=Company.INDUSTRY_TRADING,
            default_classification_version=Company.CLASSIFICATION_V2,
        )
        self.provider = ConnectionProvider.objects.create(
            key='whatsapp-v2-test',
            name='WhatsApp V2 Test',
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
            phone_number='971500000111',
        )
        self.contact = WhatsAppContact.objects.create(
            account=self.account,
            wa_contact_id='971522222222@s.whatsapp.net',
            phone_number='971522222222',
            push_name='Supplier',
        )
        self.chat = WhatsAppChat.objects.create(
            account=self.account,
            wa_chat_id='971522222222@s.whatsapp.net',
            chat_type=ChatType.INDIVIDUAL,
            contact=self.contact,
            last_message_at=timezone.now(),
        )

    def _message(self, provider_message_id='v2-msg-1', text='WTB iPhone 17 Pro 256 Orange 10pcs'):
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

    @patch('apps.trading.services.classification_service._call_agent_with_timeout')
    def test_pass1_timeout_marks_v2_log_error(self, call_with_timeout):
        call_with_timeout.side_effect = TimeoutError('V2 pass 1 AI call exceeded 180 seconds')
        message = self._message(provider_message_id='v2-timeout')

        with self.assertRaises(TimeoutError):
            classify_message_v2(message)

        log = AiParseV2Log.objects.get(message=message)
        self.assertEqual(log.status, AiParseV2Log.STATUS_ERROR)
        self.assertIn('exceeded 180 seconds', log.error)
        self.assertIsNotNone(log.pass1_total_ms)
        self.assertIsNotNone(log.total_ms)

    def test_reconcile_stale_pass1_logs_marks_orphaned_rows_error(self):
        message = self._message(provider_message_id='v2-stale')
        log = AiParseV2Log.objects.create(
            message=message,
            account=self.account,
            chat=self.chat,
            status=AiParseV2Log.STATUS_PASS1_STARTED,
            pass1_request={'messages': []},
        )
        stale_time = timezone.now() - timedelta(minutes=20)
        AiParseV2Log.objects.filter(pk=log.pk).update(
            created_at=stale_time,
            updated_at=stale_time,
        )

        reconciled = _reconcile_stale_pass1_logs(account_id=self.account.pk, stale_after_seconds=60)

        self.assertEqual(reconciled, 1)
        log.refresh_from_db()
        self.assertEqual(log.status, AiParseV2Log.STATUS_ERROR)
        self.assertIn('remained in started state', log.error)
        self.assertIsNotNone(log.pass1_total_ms)
        self.assertEqual(log.total_ms, log.pass1_total_ms)
