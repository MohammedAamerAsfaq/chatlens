from django.db import migrations


PROMPT_KEY = 'inquiry_match_decision_v2'

STOCK_RULES = """\
- Candidate qty, in_stock, and stock_status describe availability only. Do not reject an otherwise
  exact product identity match because the candidate is out_of_stock or qty is 0 or less.
- Exact/near/null must be decided by product identity attributes, not by stock availability.
- If the selected candidate is out_of_stock, mention that availability clearly in reason.
"""


def append_stock_status_rules(apps, schema_editor):
    PromptConfig = apps.get_model('trading', 'PromptConfig')
    marker = '- Never change what the sender asked for.'
    for config in PromptConfig.objects.filter(key=PROMPT_KEY).iterator():
        body = config.body or ''
        if 'stock_status' in body:
            continue
        if marker in body:
            body = body.replace(marker, f'{STOCK_RULES}{marker}', 1)
        else:
            body = f'{body.rstrip()}\n{STOCK_RULES}'
        config.body = body
        config.save(update_fields=['body', 'updated_at'])


class Migration(migrations.Migration):
    dependencies = [
        ('trading', '0033_product_tracking'),
    ]

    operations = [
        migrations.RunPython(append_stock_status_rules, migrations.RunPython.noop),
    ]
