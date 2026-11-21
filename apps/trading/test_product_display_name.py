from types import SimpleNamespace

from django.test import SimpleTestCase, TestCase

from apps.trading.models import Product, SellingOffer
from apps.trading.models.product import name_without_brand, normalize_brand
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


class ProductNamingTests(TestCase):
    def test_brand_gets_a_capital_first_letter_and_keeps_the_rest(self):
        self.assertEqual(normalize_brand(' samsung '), 'Samsung')
        self.assertEqual(normalize_brand('OnePlus'), 'OnePlus')
        self.assertEqual(normalize_brand(''), '')

    def test_name_drops_a_leading_brand(self):
        self.assertEqual(name_without_brand('Samsung A15 LCD', 'samsung'), 'A15 LCD')
        self.assertEqual(name_without_brand('APPLE iPhone 11 GX OLED LCD', 'Apple'), 'iPhone 11 GX OLED LCD')
        self.assertEqual(name_without_brand('LGX Charger', 'LG'), 'LGX Charger')
        self.assertEqual(name_without_brand('Whoop', 'Whoop'), 'Whoop')
        self.assertEqual(name_without_brand('Cable', ''), 'Cable')

    def test_saving_a_product_applies_both_rules(self):
        saved = Product.objects.create(name='tecno Spark 10 LCD', brand='tecno')
        saved.refresh_from_db()
        self.assertEqual((saved.brand, saved.name), ('Tecno', 'Spark 10 LCD'))
        self.assertEqual(product_display_name(saved), 'Tecno Spark 10 LCD')
