"""Carry today's Color → emoji results into the new per-company setting.

Until now the frontend held a fixed table of colour names. This writes, for each
company, only the catalog Color values that table already gave an emoji to, so
every reply looks the same after deploy. From here on the setting is edited in
AI Instructions and the table is gone; values it never covered stay unmapped.
"""

import json

from django.db import migrations

# The retired frontend table, frozen here only to reproduce its past output.
_RETIRED_TABLE = {
    'red': '🔴', 'pink': '🔴', 'rose': '🔴', 'magenta': '🔴',
    'orange': '🟠',
    'yellow': '🟡', 'gold': '🟡', 'citrus': '🟡',
    'green': '🟢', 'mint': '🟢',
    'blue': '🔵', 'sky': '🔵', 'navy': '🔵',
    'purple': '🟣', 'violet': '🟣', 'indigo': '🟣', 'lavender': '🟣',
    'brown': '🟤', 'bronze': '🟤', 'copper': '🟤', 'rose gold': '🟤',
    'black': '⚫', 'graphite': '⚫', 'midnight': '⚫', 'space gray': '⚫', 'space grey': '⚫',
    'white': '⚪', 'silver': '⚪', 'starlight': '⚪', 'pearl': '⚪', 'ivory': '⚪', 'grey': '⚪', 'gray': '⚪',
}
KEY = 'trading_color_emoji'


def seed(apps, schema_editor):
    ProductAttribute = apps.get_model('trading', 'ProductAttribute')
    SystemSettings = apps.get_model('chatlens_core', 'SystemSettings')
    per_company = {}
    for company_id, value in (
        ProductAttribute.objects.filter(key='Color').values_list('product__company_id', 'value').distinct()
    ):
        emoji = _RETIRED_TABLE.get((value or '').strip().lower())
        if emoji and company_id is not None:
            per_company.setdefault(company_id, {})[value.strip()] = emoji
    for company_id, mapping in per_company.items():
        if SystemSettings.objects.filter(company_id=company_id, key=KEY).exists():
            continue
        SystemSettings.objects.create(
            company_id=company_id, key=KEY, value=json.dumps(mapping, ensure_ascii=False),
            description='Emoji used for each catalog Color attribute value in WhatsApp replies and selling offers.',
        )


def unseed(apps, schema_editor):
    apps.get_model('chatlens_core', 'SystemSettings').objects.filter(key=KEY).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('trading', '0067_inquiry_status_event'),
        ('chatlens_core', '0002_systemsettings_company'),
    ]

    operations = [migrations.RunPython(seed, unseed)]
