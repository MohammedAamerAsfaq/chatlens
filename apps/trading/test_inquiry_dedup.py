from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from apps.tenancy.models import CommunicationAccount, Company, ConnectionProvider
from apps.trading.models import AiParsingLog, Inquiry, MessageClassification
from apps.trading.services.inquiry_service import link_duplicate_broadcast, process_inquiry
from apps.whatsapp_bridge.models import ChatType, WhatsAppAccount, WhatsAppChat, WhatsAppContact, WhatsAppMessage
from apps.whatsapp_bridge.services.message_fingerprint import message_dedup_key, message_text_fingerprint

BURGUNDY = '*WTB* 18 Pro max 256gb Burgundy *50pc* Hk Non Active'
BLUE = '*WTB* 18 Pro max 256gb Blue *15pc* Hk Non Active'


class InquiryExactDedupTests(TestCase):
    """Inquiry merging uses only the in-house dedup_key (sender + exact text), 60-min window."""

    def setUp(self):
        user = User.objects.create_user(username='dedup-owner')
        company = Company.objects.create(name='Dedup Co', slug='dedup-co')
        provider = ConnectionProvider.objects.create(
            key='dedup-wa', name='WhatsApp', channel=ConnectionProvider.CHANNEL_WHATSAPP,
        )
        communication = CommunicationAccount.objects.create(
            company=company, provider=provider,
            channel=ConnectionProvider.CHANNEL_WHATSAPP, name='Sales',
        )
        self.account = WhatsAppAccount.objects.create(owner=user, communication_account=communication)
        self.contact = WhatsAppContact.objects.create(
            account=self.account, wa_contact_id='971564173988@s.whatsapp.net', phone_number='971564173988',
        )
        self.group_a = WhatsAppChat.objects.create(
            account=self.account, wa_chat_id='120363000000000010@g.us', chat_type=ChatType.GROUP,
        )
        self.group_b = WhatsAppChat.objects.create(
            account=self.account, wa_chat_id='120363000000000011@g.us', chat_type=ChatType.GROUP,
        )
        self.start = timezone.now()
        self._seq = 0

    def _message(self, text, minutes=0, chat=None):
        self._seq += 1
        fingerprint = message_text_fingerprint(text)
        return WhatsAppMessage.objects.create(
            account=self.account, chat=chat or self.group_a, contact=self.contact,
            provider_message_id=f'DEDUP_{self._seq}', sender_number=self.contact.phone_number,
            direction='inbound', message_type='text', message_text=text,
            content_fingerprint=fingerprint,
            dedup_key=message_dedup_key('inbound', self.contact.wa_contact_id, fingerprint),
            message_time=self.start + timedelta(minutes=minutes),
        )

    def _classify(self, message):
        classification = MessageClassification.objects.create(
            message=message, tags=['wtb'], products=[{'canonical_name': message.message_text}],
            is_inquiry=True, inquiry_type='buy', ai_summary=message.message_text,
            dedup_key=message.dedup_key,
        )
        return process_inquiry(message, classification)[0]

    def test_one_word_difference_creates_separate_inquiries(self):
        burgundy = self._classify(self._message(BURGUNDY))
        blue = self._classify(self._message(BLUE, minutes=20))

        self.assertNotEqual(burgundy.pk, blue.pk)
        self.assertEqual(burgundy.products[0]['canonical_name'], BURGUNDY)

    def test_exact_repost_within_window_merges_and_keeps_frequency(self):
        first = self._message(BURGUNDY)
        repost = self._message(BURGUNDY.replace('*', ''), minutes=30)

        inquiry = self._classify(first)
        merged = self._classify(repost)

        self.assertEqual(inquiry.pk, merged.pk)
        self.assertEqual(inquiry.dedup_key, first.dedup_key)
        self.assertEqual(
            set(inquiry.inquiry_messages.values_list('message_id', flat=True)), {first.pk, repost.pk},
        )

    def test_exact_repost_outside_window_creates_new_inquiry(self):
        first = self._classify(self._message(BURGUNDY))
        later = self._classify(self._message(BURGUNDY, minutes=61))

        self.assertNotEqual(first.pk, later.pk)

    def test_skipped_broadcast_after_inquiry_is_linked(self):
        original = self._message(BURGUNDY)
        inquiry = self._classify(original)
        copy = self._message(BURGUNDY, minutes=1, chat=self.group_b)

        self.assertEqual([i.pk for i in link_duplicate_broadcast(copy)], [inquiry.pk])
        self.assertTrue(inquiry.inquiry_messages.filter(message=copy).exists())

    def test_skipped_broadcast_before_inquiry_is_linked_on_create(self):
        original = self._message(BURGUNDY)
        copy = self._message(BURGUNDY, minutes=1, chat=self.group_b)
        AiParsingLog.objects.create(
            message=copy, account=self.account, chat=self.group_b,
            status='skipped', skip_reason='duplicate_broadcast',
        )
        self.assertEqual(link_duplicate_broadcast(copy), [])

        inquiry = self._classify(original)

        self.assertTrue(inquiry.inquiry_messages.filter(message=copy).exists())
        self.assertEqual(Inquiry.objects.count(), 1)

    def test_message_without_dedup_key_fails_loudly(self):
        message = self._message(BURGUNDY)
        message.dedup_key = ''
        classification = MessageClassification.objects.create(
            message=message, is_inquiry=True, inquiry_type='buy',
        )
        with self.assertRaises(ValueError):
            process_inquiry(message, classification)

    def test_dedup_key_is_inbound_sender_plus_fingerprint(self):
        fingerprint = message_text_fingerprint(BURGUNDY)
        self.assertEqual(
            message_dedup_key('inbound', self.contact.wa_contact_id, fingerprint),
            f'{self.contact.wa_contact_id}:{fingerprint}',
        )
        self.assertEqual(message_dedup_key('outbound', self.contact.wa_contact_id, fingerprint), '')
        self.assertEqual(message_dedup_key('inbound', self.contact.wa_contact_id, ''), '')
