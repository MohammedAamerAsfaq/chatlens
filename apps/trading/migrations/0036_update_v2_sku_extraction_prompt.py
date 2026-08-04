from django.db import migrations


PROMPT_KEY = 'inquiry_extraction_v2'

SKU_RULES = """\
- If a product line looks like a manufacturer SKU/model code rather than a normal product name
  (for example a short alphanumeric Apple code), set is_sku_like=true and put the exact sender code
  in sku_code. When you can identify the product name with high confidence, put that readable product
  name in canonical_name and keep the sender code in raw_text and sku_code. If you are not confident
  what the code means, keep canonical_name equal to the code and set inferred_product_name=null.
- inferred_product_name should contain the readable product name inferred from sku_code, or null when
  the product name cannot be inferred confidently.
"""

SKU_SCHEMA = """\
      "is_sku_like": <bool>,
      "sku_code": "<exact SKU/code string or null>",
      "inferred_product_name": "<readable product name inferred from SKU/code or null>",
"""


def append_sku_extraction_rules(apps, schema_editor):
    PromptConfig = apps.get_model('trading', 'PromptConfig')
    rule_marker = '- raw_text should be the closest original product line or phrase from the message.'
    schema_marker = '      "brand": "<brand string or null>",'

    for config in PromptConfig.objects.filter(key=PROMPT_KEY).iterator():
        body = config.body or ''
        changed = False

        if 'is_sku_like=true' not in body:
            if rule_marker in body:
                body = body.replace(rule_marker, f'{SKU_RULES}{rule_marker}', 1)
            else:
                body = f'{body.rstrip()}\n{SKU_RULES}'
            changed = True

        if '"is_sku_like"' not in body:
            if schema_marker in body:
                body = body.replace(schema_marker, f'{schema_marker}\n{SKU_SCHEMA.rstrip()}', 1)
            else:
                body = f'{body.rstrip()}\n{SKU_SCHEMA}'
            changed = True

        if changed:
            config.body = body
            config.save(update_fields=['body', 'updated_at'])


class Migration(migrations.Migration):
    dependencies = [
        ('trading', '0035_inquiryproduct_product_qty_at_match_and_more'),
    ]

    operations = [
        migrations.RunPython(append_sku_extraction_rules, migrations.RunPython.noop),
    ]
