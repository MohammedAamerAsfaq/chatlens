import json
from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from apps.tenancy.models import CommunicationAccount, Company, ConnectionProvider
from apps.trading.models import AiParsingLog, Inquiry, MessageClassification
from apps.trading.services.classification_service import (
    _parse_v2_match_response,
    _rank_v2_candidates,
    _resolve_region_unspecified,
)
from apps.trading.services.inquiry_service import process_inquiry
from apps.whatsapp_bridge.models import ChatType, WhatsAppAccount, WhatsAppChat, WhatsAppContact, WhatsAppMessage
from apps.whatsapp_bridge.services.ingestion_service import _automation_skip_reason, _is_duplicate_group_broadcast
from apps.whatsapp_bridge.services.message_fingerprint import message_dedup_key, message_text_fingerprint

TEXT = 'Wtb\n18 pro max 256gb\nBurgandy\nNon active\n1 sim'
SENDER = '971505794076@s.whatsapp.net'
GROUP_JID = '120363000000000020@g.us'


class CompanyWideDedupTests(TestCase):
    """Two WhatsApp numbers of one company in the same group: only the first copy is classified."""

    def setUp(self):
        self.provider = ConnectionProvider.objects.create(
            key='cw-wa', name='WhatsApp', channel=ConnectionProvider.CHANNEL_WHATSAPP,
        )
        self.company = Company.objects.create(name='Expert', slug='expert')
        self.first_account = self._account(self.company, 'Expert Devices')
        self.second_account = self._account(self.company, 'Aamer Ashfaq')
        self.now = timezone.now()
        self._seq = 0

    def _account(self, company, name):
        owner = User.objects.create_user(username=f'owner-{name}')
        communication = CommunicationAccount.objects.create(
            company=company, provider=self.provider,
            channel=ConnectionProvider.CHANNEL_WHATSAPP, name=name,
        )
        return WhatsAppAccount.objects.create(
            owner=owner, communication_account=communication, ai_parsing_enabled=True,
        )

    def _copy(self, account, seconds=0, text=TEXT):
        self._seq += 1
        contact, _ = WhatsAppContact.objects.get_or_create(
            account=account, wa_contact_id=SENDER, defaults={'phone_number': SENDER.split('@')[0]},
        )
        chat, _ = WhatsAppChat.objects.get_or_create(
            account=account, wa_chat_id=GROUP_JID, defaults={'chat_type': ChatType.GROUP},
        )
        fingerprint = message_text_fingerprint(text)
        return WhatsAppMessage.objects.create(
            account=account, chat=chat, contact=contact,
            provider_message_id=f'CW_{self._seq}', sender_number=contact.phone_number,
            direction='inbound', message_type='text', message_text=text,
            content_fingerprint=fingerprint,
            dedup_key=message_dedup_key('inbound', SENDER, fingerprint),
            message_time=self.now + timedelta(seconds=seconds),
        )

    def test_copy_on_second_company_number_is_skipped(self):
        first = self._copy(self.first_account)
        second = self._copy(self.second_account)

        self.assertFalse(_is_duplicate_group_broadcast(first))
        self.assertTrue(_is_duplicate_group_broadcast(second))

    def test_other_company_is_not_a_duplicate(self):
        other = self._account(Company.objects.create(name='Other', slug='other'), 'Other number')
        self._copy(self.first_account)

        self.assertFalse(_is_duplicate_group_broadcast(self._copy(other)))

    def test_automation_stays_per_account(self):
        self._copy(self.first_account)
        second = self._copy(self.second_account)

        self.assertIsNone(_automation_skip_reason(second))

    def test_inquiry_merges_and_links_copy_across_company_numbers(self):
        first = self._copy(self.first_account)
        second = self._copy(self.second_account)
        AiParsingLog.objects.create(
            message=second, account=self.second_account, chat=second.chat,
            status='skipped', skip_reason='duplicate_broadcast',
        )
        classification = MessageClassification.objects.create(
            message=first, is_inquiry=True, inquiry_type='buy', ai_summary='s', dedup_key=first.dedup_key,
        )

        inquiry = process_inquiry(first, classification)[0]

        self.assertEqual(Inquiry.objects.count(), 1)
        self.assertEqual(
            set(inquiry.inquiry_messages.values_list('message_id', flat=True)), {first.pk, second.pk},
        )

    def test_queued_recheck_links_late_detected_copy(self):
        from apps.task_management.handlers import _queued_classification_skip_reason

        first = self._copy(self.first_account)
        classification = MessageClassification.objects.create(
            message=first, is_inquiry=True, inquiry_type='buy', ai_summary='s', dedup_key=first.dedup_key,
        )
        inquiry = process_inquiry(first, classification)[0]
        second = self._copy(self.second_account)
        AiParsingLog.objects.create(message=second, account=self.second_account, chat=second.chat, status='sent')

        self.assertEqual(_queued_classification_skip_reason(second), 'duplicate_broadcast')
        self.assertTrue(inquiry.inquiry_messages.filter(message=second).exists())
        self.assertEqual(AiParsingLog.objects.get(message=second).skip_reason, 'duplicate_broadcast')


def _candidate(product_id, name, qty, distance=0.3):
    return {
        'product_id': product_id, 'name': name, 'qty': qty, 'in_stock': qty > 0,
        'distance': distance, 'attributes': [],
    }


REGION_CANDIDATES = [
    _candidate(87, 'iPhone 18 Pro Max 256GB Burgundy Japan', 0),
    _candidate(91, 'iPhone 18 Pro Max 256GB Burgundy Hong Kong', 7),
    _candidate(95, 'iPhone 18 Pro Max 256GB Burgundy Singapore', 0),
]


def _region_result(ids):
    return {
        'product_id': None, 'match_type': None, 'confidence': 0.2,
        'reason': 'Region not specified.', 'rejected_candidate_ids': ids,
        'region_unspecified_candidate_ids': ids,
    }


class RegionUnspecifiedTests(TestCase):
    """AI names the candidates differing only by region; code suggests the single in-stock one."""

    def test_single_in_stock_variant_becomes_near_match(self):
        result = _resolve_region_unspecified(0, _region_result([87, 91, 95]), REGION_CANDIDATES)

        self.assertEqual(result['product_id'], 91)
        self.assertEqual(result['match_type'], 'near')
        self.assertIn('only in-stock regional variant', result['reason'])

    def test_no_or_several_in_stock_variants_stay_unmatched(self):
        none_in_stock = [{**c, 'qty': 0, 'in_stock': False} for c in REGION_CANDIDATES]
        all_in_stock = [{**c, 'qty': 3, 'in_stock': True} for c in REGION_CANDIDATES]

        for candidates in (none_in_stock, all_in_stock):
            result = _resolve_region_unspecified(0, _region_result([87, 91, 95]), candidates)
            self.assertIsNone(result['product_id'])
            self.assertIn('no single suggestion', result['reason'])

    def test_ids_outside_candidates_fail_loudly(self):
        with self.assertRaises(ValueError):
            _resolve_region_unspecified(0, _region_result([87, 999]), REGION_CANDIDATES)

    def test_parser_defaults_and_validates_region_ids(self):
        row = {'line_index': 0, 'product_id': None, 'match_type': None, 'confidence': 0, 'reason': 'r'}
        parsed = _parse_v2_match_response(json.dumps({'results': [row]}), {0})
        self.assertEqual(parsed[0]['region_unspecified_candidate_ids'], [])

        bad = {**row, 'region_unspecified_candidate_ids': ['91']}
        with self.assertRaises(ValueError):
            _parse_v2_match_response(json.dumps({'results': [bad]}), {0})

    def test_in_stock_variant_wins_a_near_tie_but_not_an_attribute_match(self):
        tied = [
            _candidate(87, 'Burgundy Japan', 0, distance=0.300),
            _candidate(95, 'Burgundy Singapore', 0, distance=0.301),
            _candidate(91, 'Burgundy Hong Kong', 7, distance=0.310),
        ]
        self.assertEqual(_rank_v2_candidates(tied, {}, 1)[0]['product_id'], 91)

        with_region = [
            {**_candidate(87, 'Burgundy Japan', 0), 'attributes': [{'key': 'Region', 'value': 'Japan'}]},
            {**_candidate(91, 'Burgundy Hong Kong', 7), 'attributes': [{'key': 'Region', 'value': 'Hong Kong'}]},
        ]
        self.assertEqual(_rank_v2_candidates(with_region, {'Region': 'Japan'}, 1)[0]['product_id'], 87)


def _inventory(product_id, name, model, region, qty=0):
    return {
        **_candidate(product_id, name, qty, distance=0.2),
        'attributes': [
            {'key': 'Series', 'value': 'iPhone 18'}, {'key': 'Model', 'value': model},
            {'key': 'Storage', 'value': '256'}, {'key': 'Region', 'value': region},
            {'key': 'Color', 'value': 'Burgundy'},
        ],
    }


class AttributeScoringTests(TestCase):
    """Tier words and region shorthand must rank the right variant first."""

    PRO = _inventory(75, 'iPhone 18 Pro 256GB Burgundy Hong Kong', 'Pro', 'Hong Kong')
    PRO_MAX = _inventory(91, 'iPhone 18 Pro Max 256GB Burgundy Hong Kong', 'Pro Max', 'Hong Kong')
    PRO_MAX_JP = _inventory(87, 'iPhone 18 Pro Max 256GB Burgundy Japan', 'Pro Max', 'Japan')

    def test_pro_max_request_never_ranks_pro_first(self):
        attributes = {'Model': '18 Pro Max', 'Storage': '256', 'Color': 'Burgundy'}
        ranked = _rank_v2_candidates([self.PRO, self.PRO_MAX], attributes, 2, 'iPhone 18 Pro Max 256GB Burgundy')

        self.assertEqual(ranked[0]['product_id'], 91)
        self.assertIn('Model: mismatch (18 Pro Max != Pro)', ranked[1]['attribute_match_notes'])

    def test_pro_request_ranks_pro_first(self):
        attributes = {'Series': '18', 'Model': 'Pro', 'Storage': '256'}
        ranked = _rank_v2_candidates([self.PRO_MAX, self.PRO], attributes, 2, 'iPhone 18 Pro 256GB Burgundy')

        self.assertEqual(ranked[0]['product_id'], 75)

    def test_region_shorthand_matches_inventory_wording(self):
        ranked = _rank_v2_candidates(
            [self.PRO_MAX_JP, self.PRO_MAX], {'Model': 'Pro Max', 'Region': 'HK'}, 2, '18 pro max 256 burgundy',
        )

        self.assertEqual(ranked[0]['product_id'], 91)
        self.assertIn('Region: match', ranked[0]['attribute_match_notes'])
        self.assertIn('Region: mismatch (HK != Japan)', ranked[1]['attribute_match_notes'])

    def test_sim_wording_variants_match_one_sim_attribute(self):
        one_sim = {
            **self.PRO_MAX,
            'attributes': self.PRO_MAX['attributes'] + [{'key': 'SIM Type', 'value': '1 SIM'}],
        }
        for wording in ('1sim', '1 sim', 'Single SIM', '1 Physical Sim'):
            with self.subTest(wording=wording):
                ranked = _rank_v2_candidates([one_sim], {'SIM Type': wording}, 1, '')
                self.assertIn('SIM Type: match', ranked[0]['attribute_match_notes'])

        ranked = _rank_v2_candidates([one_sim], {'SIM Type': 'eSIM'}, 1, '')
        self.assertIn('SIM Type: mismatch (eSIM != 1 SIM)', ranked[0]['attribute_match_notes'])
        ranked = _rank_v2_candidates([one_sim], {'SIM Type': 'Dual SIM'}, 1, '')
        self.assertIn('SIM Type: mismatch (Dual SIM != 1 SIM)', ranked[0]['attribute_match_notes'])
