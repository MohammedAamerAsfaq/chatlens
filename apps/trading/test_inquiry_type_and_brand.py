from unittest.mock import patch

from django.test import TestCase

from apps.message_intelligence.models import ProductEmbedding
from apps.tenancy.models import Company
from apps.trading.models import Product, ProductAlias
from apps.trading.services.classification_service import (
    _find_v2_candidates,
    _parse_v2_extraction_response,
    leading_keyword_inquiry_type,
)
from apps.trading.services.v2_gatepass_service import _parse_decision

SHARTEL_WTS = (
    '*WTS*\n\n*iphone 17 pro max 256GB*\U0001f1ef\U0001f1f5\nSilver @ 110 PCS\n\n'
    ' \U0001f525*price*\U0001f525\n\n*Ready Stock FZ*'
)


def _pass1(inquiry_type, is_inquiry=True):
    return (
        '{"tags":["other"],"products":[],"is_inquiry":%s,"inquiry_type":"%s","summary":"s"}'
        % ('true' if is_inquiry else 'false', inquiry_type)
    )


class LeadingKeywordInquiryTypeTests(TestCase):
    """Buy/sell comes from the message's own opening keyword when it has one."""

    def test_leading_keywords(self):
        self.assertEqual(leading_keyword_inquiry_type(SHARTEL_WTS), 'sell')
        self.assertEqual(leading_keyword_inquiry_type('\U0001f525 WTS – iPhone 18 Pro Max'), 'sell')
        self.assertEqual(leading_keyword_inquiry_type('Selling 18 Pro 256'), 'sell')
        self.assertEqual(leading_keyword_inquiry_type('*WTB*\nGoogle Fitbit air'), 'buy')
        self.assertEqual(leading_keyword_inquiry_type('Buying S26 Ultra'), 'buy')

    def test_undecided_without_leading_keyword_or_when_mixed(self):
        self.assertEqual(leading_keyword_inquiry_type('Need 18 Pro Max 256 asap'), '')
        self.assertEqual(leading_keyword_inquiry_type('Anyone WTS 18 Pro?'), '')
        self.assertEqual(leading_keyword_inquiry_type('WTS 17 Pro\n\nWTB 18 Pro Max'), '')
        self.assertEqual(leading_keyword_inquiry_type('WTSALE 17 Pro'), '')

    def test_keyword_overrides_ai_and_records_both(self):
        parsed = _parse_v2_extraction_response(_pass1('buy'), SHARTEL_WTS)

        self.assertEqual(parsed['inquiry_type'], 'sell')
        self.assertEqual(parsed['raw']['inhouse_inquiry_type'], {'ai': 'buy', 'keyword': 'sell'})

    def test_agreeing_ai_is_not_marked_as_override(self):
        parsed = _parse_v2_extraction_response(_pass1('sell'), SHARTEL_WTS)

        self.assertEqual(parsed['inquiry_type'], 'sell')
        self.assertNotIn('inhouse_inquiry_type', parsed['raw'])

    def test_ai_decides_without_keyword_and_for_mixed_posts(self):
        self.assertEqual(_parse_v2_extraction_response(_pass1('buy'), 'Need 18 Pro Max')['inquiry_type'], 'buy')
        self.assertEqual(_parse_v2_extraction_response(_pass1('sell'), 'WTS 17 Pro\nWTB 18 Pro')['inquiry_type'], 'sell')

    def test_keyword_never_makes_a_non_inquiry_an_inquiry(self):
        parsed = _parse_v2_extraction_response(_pass1('', is_inquiry=False), 'WTS group rules: no spam')

        self.assertFalse(parsed['is_inquiry'])
        self.assertEqual(parsed['inquiry_type'], '')


class GatePassInquiryOnlyTests(TestCase):
    def test_gate_accepts_only_inquiry_or_not_inquiry(self):
        self.assertEqual(_parse_decision('{"decision":"inquiry"}'), 'inquiry')
        self.assertEqual(_parse_decision('{"decision":"not_inquiry"}'), 'not_inquiry')
        for decision in ('buy', 'sell'):
            with self.assertRaises(ValueError):
                _parse_decision('{"decision":"%s"}' % decision)


class BrandCandidateFilterTests(TestCase):
    """Extracted brand also matches a whole word in product name or alias."""

    def setUp(self):
        self.company = Company.objects.create(name='Brand Co', slug='brand-co')
        self.fitbit = self._product('Google', 'Google Fitbit Air Black')
        self.aliased = self._product('Google', 'Pixel Band')
        ProductAlias.objects.create(product=self.aliased, alias='Fitbit band')
        self.apple = self._product('Apple', 'iPhone 18 Pro Max 256GB Blue')
        self.lookalike = self._product('Google', 'Fitbitz Charger')

    def _product(self, brand, name):
        product = Product.objects.create(company=self.company, brand=brand, name=name, qty=5)
        ProductEmbedding.objects.create(product=product, embedding=[1.0] + [0.0] * 511, embedding_model='test')
        return product

    @patch('apps.ai_providers.manager.ai_manager.embed', return_value=[1.0] + [0.0] * 511)
    def test_brand_matches_name_or_alias_word(self, _embed):
        ids = {c['product_id'] for c in _find_v2_candidates('Fitbit Air', self.company, top_k=10, brand='Fitbit')}

        self.assertEqual(ids, {self.fitbit.pk, self.aliased.pk})

    @patch('apps.ai_providers.manager.ai_manager.embed', return_value=[1.0] + [0.0] * 511)
    def test_unstocked_brand_still_finds_nothing(self, _embed):
        self.assertEqual(_find_v2_candidates('Galaxy S26', self.company, top_k=10, brand='Samsung'), [])

    @patch('apps.ai_providers.manager.ai_manager.embed', return_value=[1.0] + [0.0] * 511)
    def test_brand_column_match_still_works(self, _embed):
        ids = {c['product_id'] for c in _find_v2_candidates('iPhone', self.company, top_k=10, brand='Apple')}

        self.assertEqual(ids, {self.apple.pk})
