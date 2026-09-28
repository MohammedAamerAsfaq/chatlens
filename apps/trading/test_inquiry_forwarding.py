from types import SimpleNamespace
from unittest.mock import patch
from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from apps.tenancy.models import CommunicationAccount, Company, CompanyMembership, ConnectionProvider
from apps.trading.models import (
    Inquiry,
    InquiryForwardingExclusion,
    InquiryForwardingRule,
    InquiryForwardingRun,
    InquiryForwardingTarget,
    InquiryMessage,
    AiParseV2Log,
    MessageClassification,
    Product,
)
from apps.trading.services.inquiry_forwarding_service import (
    enqueue_inquiry_forwarding,
    process_inquiry_forwarding,
)
from apps.whatsapp_bridge.models import (
    ChatType,
    OutboundMessage,
    WhatsAppAccount,
    WhatsAppChat,
    WhatsAppContact,
    WhatsAppGroup,
    WhatsAppMessage,
)


class InquiryForwardingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='forwarder')
        self.company = Company.objects.create(name='Forward Co', slug='forward-co')
        CompanyMembership.objects.create(
            company=self.company, user=self.user, role=CompanyMembership.ROLE_ADMIN,
        )
        provider = ConnectionProvider.objects.create(
            key='forward-wa', name='WhatsApp', channel=ConnectionProvider.CHANNEL_WHATSAPP,
        )
        communication = CommunicationAccount.objects.create(
            company=self.company, provider=provider,
            channel=ConnectionProvider.CHANNEL_WHATSAPP, name='Sales',
        )
        self.account = WhatsAppAccount.objects.create(
            owner=self.user, communication_account=communication,
            outbound_sending_enabled=True, direct_sending_enabled=True,
        )
        self.source_contact = self._contact('971500000001', 'Source')
        self.destination = self._contact('971500000002', 'Destination')
        self.chat = WhatsAppChat.objects.create(
            account=self.account, contact=self.source_contact,
            wa_chat_id=self.source_contact.wa_contact_id, chat_type=ChatType.INDIVIDUAL,
        )
        self.message = WhatsAppMessage.objects.create(
            account=self.account, chat=self.chat, contact=self.source_contact,
            provider_message_id='source-1', sender_number=self.source_contact.phone_number,
            direction='inbound', message_type='text', message_text='WTB Phone X 10 pcs',
            message_time=timezone.now(),
        )
        self.exact_product = Product.objects.create(
            company=self.company, name='Phone X Exact', qty=4, sale_price=900, currency='AED',
        )
        self.near_product = Product.objects.create(
            company=self.company, name='Phone X Near', qty=8, sale_price=800, currency='AED',
        )
        products = [
            {'canonical_name': 'Phone X', 'quantity': 10, 'product_id': self.exact_product.pk, 'match_type': 'exact'},
            {'canonical_name': 'Phone X maybe', 'product_id': self.near_product.pk, 'match_type': 'near'},
        ]
        MessageClassification.objects.create(
            message=self.message, products=products, is_inquiry=True, inquiry_type='buy',
        )
        self.inquiry = Inquiry.objects.create(
            company=self.company, account=self.account, contact=self.source_contact,
            inquiry_type='buy', products=products, summary='Buying Phone X', dedup_key='phone-x',
            source_type='direct', first_seen_at=self.message.message_time,
        )
        InquiryMessage.objects.create(inquiry=self.inquiry, message=self.message)
        self.rule = InquiryForwardingRule.objects.create(
            company=self.company, inquiry_type='buy', name='WTB', is_active=True,
            created_by=self.user,
        )
        self.target = InquiryForwardingTarget.objects.create(
            rule=self.rule, target_type='contact', contact=self.destination,
        )

    def _contact(self, number, name):
        return WhatsAppContact.objects.create(
            account=self.account, wa_contact_id=f'{number}@s.whatsapp.net',
            phone_number=number, display_name=name, is_existing_chat=True,
        )

    @patch('apps.whatsapp_bridge.outbound.message_service.enqueue_task')
    @patch('apps.whatsapp_bridge.outbound.policy.capacity_snapshot')
    def test_queues_deterministic_message_with_exact_stock_only(self, capacity, enqueue):
        capacity.return_value = {'reachout': {'is_active': False}, 'cap': {}}
        enqueue.return_value = SimpleNamespace(pk=501)

        result = process_inquiry_forwarding(self.inquiry.pk, self.message.pk)

        self.assertEqual(result['status'], InquiryForwardingRun.STATUS_COMPLETE)
        outbound = OutboundMessage.objects.get()
        text = outbound.content_payload['text']
        self.assertIn('Original message:\nWTB Phone X 10 pcs', text)
        self.assertIn(f'Inquiry ID: #{self.inquiry.pk}', text)
        self.assertIn('Summary:\nBuying Phone X', text)
        self.assertIn('https://wa.me/971500000001', text)
        self.assertIn('Phone X Exact | Qty 4 | AED 900.00', text)
        self.assertNotIn('Phone X Near | Qty 8', text)
        enqueue.assert_called_once()

    @patch('apps.whatsapp_bridge.outbound.message_service.enqueue_task')
    @patch('apps.whatsapp_bridge.outbound.policy.capacity_snapshot')
    def test_selected_source_contact_is_automatically_skipped(self, capacity, enqueue):
        capacity.return_value = {'reachout': {'is_active': False}, 'cap': {}}
        enqueue.return_value = SimpleNamespace(pk=502)
        InquiryForwardingTarget.objects.create(
            rule=self.rule, target_type='contact', contact=self.source_contact,
        )

        result = process_inquiry_forwarding(self.inquiry.pk, self.message.pk)

        self.assertEqual(result['status'], InquiryForwardingRun.STATUS_PARTIAL)
        delivery = self.inquiry.forwarding_runs.get().deliveries.get(target__contact=self.source_contact)
        self.assertEqual(delivery.status, 'skipped')
        self.assertEqual(delivery.reason, 'source_contact_is_destination')
        self.assertEqual(OutboundMessage.objects.count(), 1)

    @patch('apps.whatsapp_bridge.outbound.message_service.create_outbound_message')
    def test_selected_source_group_is_automatically_skipped(self, create_outbound):
        group = WhatsAppGroup.objects.create(
            account=self.account, wa_group_id='120000000000@g.us', name='Source Group',
            account_is_participant=True, can_send=True,
        )
        group_chat = WhatsAppChat.objects.create(
            account=self.account, wa_chat_id=group.wa_group_id,
            chat_type=ChatType.GROUP, name=group.name,
        )
        group.chat = group_chat
        group.save(update_fields=['chat'])
        group_message = WhatsAppMessage.objects.create(
            account=self.account, chat=group_chat, contact=self.source_contact,
            provider_message_id='group-source', sender_number=self.source_contact.phone_number,
            direction='inbound', message_type='text', message_text='WTS Phone X',
            message_time=timezone.now(),
        )
        MessageClassification.objects.create(
            message=group_message, products=self.inquiry.products,
            is_inquiry=True, inquiry_type='sell',
        )
        inquiry = Inquiry.objects.create(
            company=self.company, account=self.account, contact=self.source_contact,
            inquiry_type='sell', products=self.inquiry.products, summary='Selling Phone X',
            dedup_key='sell-phone-x', source_type='group', first_seen_at=group_message.message_time,
        )
        InquiryMessage.objects.create(inquiry=inquiry, message=group_message)
        rule = InquiryForwardingRule.objects.create(
            company=self.company, inquiry_type='sell', name='WTS', is_active=True,
            created_by=self.user,
        )
        InquiryForwardingTarget.objects.create(rule=rule, target_type='group', group=group)

        result = process_inquiry_forwarding(inquiry.pk, group_message.pk)

        self.assertEqual(result['status'], InquiryForwardingRun.STATUS_FAILED)
        delivery = inquiry.forwarding_runs.get().deliveries.get()
        self.assertEqual(delivery.status, 'skipped')
        self.assertEqual(delivery.reason, 'source_group_is_destination')
        create_outbound.assert_not_called()

    @patch('apps.whatsapp_bridge.outbound.message_service.enqueue_task')
    @patch('apps.whatsapp_bridge.services.live_group_metadata.requests.post')
    @patch('apps.whatsapp_bridge.outbound.policy.capacity_snapshot')
    def test_stale_target_group_is_refreshed_before_forwarding(self, capacity, post, enqueue):
        capacity.return_value = {'reachout': {'is_active': False}, 'cap': {}}
        enqueue.return_value = SimpleNamespace(pk=504)
        self.account.group_sending_enabled = True
        self.account.save(update_fields=['group_sending_enabled'])
        group = WhatsAppGroup.objects.create(
            account=self.account, wa_group_id='120000000001@g.us', name='Forward Group',
            account_is_participant=True, can_send=True,
            metadata_refreshed_at=timezone.now() - timedelta(hours=1),
        )
        self.target.delete()
        InquiryForwardingTarget.objects.create(
            rule=self.rule, target_type='group', group=group,
        )
        post.return_value = SimpleNamespace(
            status_code=200,
            json=lambda: {
                'group_metadata': {
                    'group_id': group.wa_group_id,
                    'name': group.name,
                    'account_is_participant': True,
                    'account_participant_role': 'member',
                    'metadata_complete': True,
                    'participants': [],
                },
            },
        )

        result = process_inquiry_forwarding(self.inquiry.pk, self.message.pk)

        self.assertEqual(result['status'], InquiryForwardingRun.STATUS_COMPLETE)
        self.assertEqual(post.call_count, 1)
        self.assertIn('/destinations/preflight', post.call_args.args[0])
        group.refresh_from_db()
        self.assertGreater(group.metadata_refreshed_at, timezone.now() - timedelta(minutes=1))
        self.assertEqual(OutboundMessage.objects.get().status, OutboundMessage.STATUS_QUEUED)

    @patch('apps.trading.services.inquiry_forwarding_service._send_target')
    def test_source_contact_exclusion_skips_entire_rule(self, send_target):
        InquiryForwardingExclusion.objects.create(
            rule=self.rule, exclusion_type='contact', contact=self.source_contact,
        )

        result = process_inquiry_forwarding(self.inquiry.pk, self.message.pk)

        self.assertEqual(result['status'], InquiryForwardingRun.STATUS_SKIPPED)
        self.assertEqual(result['reason'], 'source_contact_excluded')
        send_target.assert_not_called()

    @patch('apps.queue_management.services.enqueue_task')
    def test_no_product_evidence_creates_no_forwarding_task(self, enqueue):
        self.inquiry.products = []
        self.inquiry.save(update_fields=['products'])

        tasks = enqueue_inquiry_forwarding([self.inquiry.pk], self.message.pk)

        self.assertEqual(tasks, [])
        enqueue.assert_not_called()

    @patch('apps.queue_management.services.enqueue_task')
    def test_v2_forwarding_is_not_enqueued_until_all_linked_passes_complete(self, enqueue):
        classification = self.message.classification
        classification.classification_version = 'v2'
        classification.save(update_fields=['classification_version'])
        self.inquiry.classification_version = 'v2'
        self.inquiry.product_match_status = Inquiry.CLASSIFICATION_MATCH_COMPLETE
        self.inquiry.save(update_fields=['classification_version', 'product_match_status'])
        AiParseV2Log.objects.create(
            message=self.message, account=self.account, chat=self.chat,
            classification=classification, inquiry_ids=[self.inquiry.pk],
            status=AiParseV2Log.STATUS_COMPLETE,
        )
        second_message = WhatsAppMessage.objects.create(
            account=self.account, chat=self.chat, contact=self.source_contact,
            provider_message_id='source-2', sender_number=self.source_contact.phone_number,
            direction='inbound', message_type='text', message_text='WTB Phone X 10 pcs',
            message_time=timezone.now(),
        )
        second_classification = MessageClassification.objects.create(
            message=second_message, products=self.inquiry.products,
            is_inquiry=True, inquiry_type='buy', classification_version='v2',
        )
        InquiryMessage.objects.create(inquiry=self.inquiry, message=second_message)
        second_log = AiParseV2Log.objects.create(
            message=second_message, account=self.account, chat=self.chat,
            classification=second_classification, inquiry_ids=[self.inquiry.pk],
            status=AiParseV2Log.STATUS_PASS2_STARTED,
        )

        self.assertEqual(enqueue_inquiry_forwarding([self.inquiry.pk], self.message.pk), [])
        enqueue.assert_not_called()

        second_log.status = AiParseV2Log.STATUS_COMPLETE
        second_log.save(update_fields=['status'])
        enqueue.return_value = SimpleNamespace(pk=503)

        self.assertEqual(len(enqueue_inquiry_forwarding([self.inquiry.pk], self.message.pk)), 1)
        enqueue.assert_called_once()

    def test_handler_defers_when_v2_inquiry_is_not_fully_formed(self):
        from apps.queue_management.services import TaskDeferred

        classification = self.message.classification
        classification.classification_version = 'v2'
        classification.save(update_fields=['classification_version'])
        self.inquiry.classification_version = 'v2'
        self.inquiry.product_match_status = Inquiry.CLASSIFICATION_MATCH_PENDING
        self.inquiry.save(update_fields=['classification_version', 'product_match_status'])
        AiParseV2Log.objects.create(
            message=self.message, account=self.account, chat=self.chat,
            classification=classification, inquiry_ids=[self.inquiry.pk],
            status=AiParseV2Log.STATUS_PASS2_STARTED,
        )

        with self.assertRaises(TaskDeferred):
            process_inquiry_forwarding(self.inquiry.pk, self.message.pk)

        self.assertFalse(InquiryForwardingRun.objects.exists())
        self.assertFalse(OutboundMessage.objects.exists())

    def test_non_inquiry_classification_fails_closed(self):
        classification = self.message.classification
        classification.is_inquiry = False
        classification.save(update_fields=['is_inquiry'])

        result = process_inquiry_forwarding(self.inquiry.pk, self.message.pk)

        self.assertEqual(result['status'], InquiryForwardingRun.STATUS_SKIPPED)
        self.assertEqual(result['reason'], 'classification_not_inquiry')

    def test_rule_api_replaces_company_scoped_targets_and_exclusions(self):
        self.client.force_login(self.user)

        response = self.client.patch(
            f'/api/inquiry-forwarding-rules/{self.rule.pk}/',
            {
                'name': 'Strict WTB forwarding',
                'targets': [{'type': 'contact', 'contact_id': self.destination.pk}],
                'exclusions': [{'type': 'contact', 'contact_id': self.source_contact.pk}],
            },
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['name'], 'Strict WTB forwarding')
        self.assertEqual(response.json()['targets'][0]['contact_id'], self.destination.pk)
        self.assertEqual(response.json()['exclusions'][0]['contact_id'], self.source_contact.pk)
