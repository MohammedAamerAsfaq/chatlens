from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.trading.models import SellingOffer
from apps.trading.serializers import product_display_name


def product(name, brand):
    return SimpleNamespace(name=name, brand=brand)


class ProductDisplayNameTests(SimpleTestCase):
    def test_name_that_already_starts_with_the_brand_is_not_prefixed_again(self):
        self.assertEqual(product_display_name(product('Apple iPhone 11 GX OLED LCD', 'apple')), 'Apple iPhone 11 GX OLED LCD')
        self.assertEqual(product_display_name(product('Motorola E13 LCD', 'motorola')), 'Motorola E13 LCD')

    def test_name_without_its_brand_gets_the_brand_in_front(self):
        self.assertEqual(product_display_name(product('17 Pro Max 256GB Blue', 'Apple')), 'Apple 17 Pro Max 256GB Blue')

    def test_brand_must_be_a_whole_word_at_the_start(self):
        self.assertEqual(product_display_name(product('LGX Charger', 'LG')), 'LG LGX Charger')

    def test_missing_brand_or_product(self):
        self.assertEqual(product_display_name(product('Cable', '')), 'Cable')
        self.assertEqual(product_display_name(None), '')

    def test_selling_campaigns_list_products_without_quantity_by_default(self):
        self.assertEqual(SellingOffer._meta.get_field('product_line_template').default, '- {product_name} - {price}')
