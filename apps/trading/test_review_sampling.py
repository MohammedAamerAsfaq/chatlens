from django.test import SimpleTestCase
from apps.trading.services.trading_review_sampling import ReviewGroups, balanced_groups


class ReviewGroupingTests(SimpleTestCase):
    def test_grouping_preserves_numbers_and_short_messages(self):
        groups = ReviewGroups()
        first = groups.add('WTB iPhone 17 256GB blue 10 pcs confirmed order', 1)
        self.assertEqual(first, groups.add('wtb IPHONE 17 256GB blue 10 pcs confirmed order!', 2))
        self.assertNotEqual(first, groups.add('WTB iPhone 17 256GB blue 20 pcs confirmed order', 3))
        self.assertNotEqual(first, groups.add('WTB iPhone 17 256GB red 10 pcs confirmed order', 8))
        self.assertNotEqual(groups.add('WTB', 4), groups.add('WTS', 5))
        self.assertEqual(groups.add(' OK  ', 6), groups.add('ok', 7))

    def test_balanced_selection_covers_each_available_pool(self):
        groups = [{'pool': pool, 'id': str(i)} for pool, i in [('buy', 1), ('buy', 2), ('sell', 3), ('non_inquiry', 4), ('uncertain', 5)]]
        result = balanced_groups(groups, 4)
        self.assertEqual({g['pool'] for g in result}, {'buy', 'sell', 'non_inquiry', 'uncertain'})
from apps.trading.management.commands.export_trading_reviews import group_split


class ReviewSplitTests(SimpleTestCase):
    def test_group_split_is_deterministic(self):
        groups = ReviewGroups()
        a = groups.add('Same message', 1)
        b = groups.add('same   message', 2)
        self.assertEqual(group_split(groups.groups[a]['id']), group_split(groups.groups[b]['id']))
