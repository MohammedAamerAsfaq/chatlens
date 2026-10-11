from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.real_estate.models import (
    ActivityType,
    ClassificationStatus,
    RealEstateOpportunity,
    RealEstateParseLog,
    RealEstateSettings,
)
from apps.task_management.models import BackgroundTask
from apps.tenancy.models import Company, CommunicationAccount, ConnectionProvider
from apps.trading.models import AiParsingLog
from apps.whatsapp_bridge.models import (
    ChatType,
    MessageDirection,
    MessageType,
    WhatsAppAccount,
    WhatsAppChat,
    WhatsAppContact,
    WhatsAppMessage,
)
from apps.whatsapp_bridge.services.ingestion_service import _log_ai_parsing_and_classify


class RealEstatePipelineTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            name='Property Pipeline', slug='property-pipeline',
            industry_type=Company.INDUSTRY_REAL_ESTATE,
        )
        self.owner = get_user_model().objects.create_user('property-worker')
        provider, _ = ConnectionProvider.objects.get_or_create(
            key='pipeline-baileys',
            defaults={'name': 'Pipeline Baileys', 'channel': ConnectionProvider.CHANNEL_WHATSAPP},
        )
        communication = CommunicationAccount.objects.create(
            company=self.company, provider=provider,
            channel=ConnectionProvider.CHANNEL_WHATSAPP, name='Property WhatsApp',
        )
        self.account = WhatsAppAccount.objects.create(
            owner=self.owner, communication_account=communication,
            display_name='Property WhatsApp', ai_parsing_enabled=True,
            ai_parsing_enabled_at=timezone.now(),
        )
        self.contact = WhatsAppContact.objects.create(
            account=self.account, wa_contact_id='971500000001@s.whatsapp.net',
            phone_number='971500000001', display_name='Property Client',
        )
        self.chat = WhatsAppChat.objects.create(
            account=self.account, wa_chat_id='971500000001@s.whatsapp.net',
            chat_type=ChatType.INDIVIDUAL, contact=self.contact, ai_parsing=True,
        )
        self.message = WhatsAppMessage.objects.create(
            account=self.account, chat=self.chat, contact=self.contact,
            provider_message_id='real-estate-message-1',
            direction=MessageDirection.INBOUND, message_type=MessageType.TEXT,
            message_text='Looking to buy a two-bedroom apartment in Dubai Marina.',
            message_time=timezone.now(),
        )

    def test_ingestion_routes_real_estate_to_its_gate_queue_only(self):
        _log_ai_parsing_and_classify(self.message)

        task = BackgroundTask.objects.get(task_key='real_estate.gate_message')
        self.assertEqual(task.company, self.company)
        self.assertEqual(task.queue_name, 'real_estate_gate')
        self.assertEqual(task.payload['message_id'], self.message.pk)
        self.assertEqual(
            RealEstateParseLog.objects.get(message=self.message).status,
            RealEstateParseLog.STATUS_GATE_PENDING,
        )
        self.assertFalse(AiParsingLog.objects.filter(message=self.message).exists())

    def test_disabled_gate_enqueues_extraction_without_calling_ai(self):
        RealEstateSettings.objects.update_or_create(
            company=self.company,
            defaults={'gate_mode': RealEstateSettings.GATE_DISABLED},
        )
        _log_ai_parsing_and_classify(self.message)
        task = BackgroundTask.objects.get(task_key='real_estate.gate_message')

        from apps.real_estate.task_handlers import gate_message
        result = gate_message(task.payload, SimpleNamespace(task_id=task.pk))

        self.assertEqual(result['decision'], 'disabled')
        self.assertFalse(result['stopped'])
        self.assertTrue(BackgroundTask.objects.filter(
            task_key='real_estate.extract_message', company=self.company,
        ).exists())

    @patch('apps.real_estate.services.gate_service.run_gate', return_value='not_real_estate')
    def test_enforced_gate_stops_negative_message(self, mocked_gate):
        RealEstateSettings.objects.update_or_create(
            company=self.company,
            defaults={'gate_mode': RealEstateSettings.GATE_ENFORCED},
        )
        _log_ai_parsing_and_classify(self.message)
        task = BackgroundTask.objects.get(task_key='real_estate.gate_message')

        from apps.real_estate.task_handlers import gate_message
        result = gate_message(task.payload, SimpleNamespace(task_id=task.pk))

        self.assertTrue(result['stopped'])
        self.assertFalse(BackgroundTask.objects.filter(task_key='real_estate.extract_message').exists())
        opportunity = RealEstateOpportunity.objects.get(source_message=self.message)
        self.assertEqual(opportunity.classification_status, ClassificationStatus.NOT_REAL_ESTATE)
        self.assertEqual(opportunity.status, RealEstateOpportunity.STATUS_IRRELEVANT)
        mocked_gate.assert_called_once()

    @patch('apps.real_estate.services.extraction_service.call_real_estate_agent')
    def test_extraction_persists_one_canonical_activity(self, mocked_agent):
        mocked_agent.return_value = (
            '{"decision":"leasing_inquiry","summary":"Tenant needs a two-bedroom flat",'
            '"confidence":0.94,"property":{"property_type":"apartment"}}'
        )
        _log_ai_parsing_and_classify(self.message)
        parse_log = RealEstateParseLog.objects.get(message=self.message)

        from apps.real_estate.services.extraction_service import run_extraction
        opportunity, parsed = run_extraction(self.message, parse_log, self.company)

        self.assertEqual(parsed['decision'], ActivityType.LEASING_INQUIRY)
        self.assertEqual(opportunity.activity_type, ActivityType.LEASING_INQUIRY)
        self.assertEqual(opportunity.classification_status, ClassificationStatus.CLASSIFIED)
        parse_log.refresh_from_db()
        self.assertEqual(parse_log.status, RealEstateParseLog.STATUS_COMPLETE)
        self.assertEqual(parse_log.extraction_result['property']['property_type'], 'apartment')

    def test_general_company_does_not_fall_through_to_trading(self):
        self.company.industry_type = Company.INDUSTRY_GENERAL
        self.company.save(update_fields=['industry_type'])

        _log_ai_parsing_and_classify(self.message)

        self.assertFalse(BackgroundTask.objects.filter(
            payload__message_id=self.message.pk,
        ).exists())
        self.assertFalse(AiParsingLog.objects.filter(message=self.message).exists())
        self.assertFalse(RealEstateParseLog.objects.filter(message=self.message).exists())

