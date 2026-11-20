# Selling campaigns list products without a quantity by default. Campaigns still on the
# old default line move to the new one; campaigns with their own line are left alone.

from django.db import migrations, models

OLD_LINE = '- {product_name} - Qty {qty} - {price}'
NEW_LINE = '- {product_name} - {price}'


def drop_qty(apps, schema_editor):
    apps.get_model('trading', 'SellingOffer').objects.filter(product_line_template=OLD_LINE).update(
        product_line_template=NEW_LINE,
    )


def restore_qty(apps, schema_editor):
    # Also restores the few campaigns that already used the new line before this migration.
    apps.get_model('trading', 'SellingOffer').objects.filter(product_line_template=NEW_LINE).update(
        product_line_template=OLD_LINE,
    )


class Migration(migrations.Migration):

    dependencies = [
        ('trading', '0071_campaign_product_lists'),
    ]

    operations = [
        migrations.AlterField(
            model_name='sellingoffer',
            name='product_line_template',
            field=models.TextField(default=NEW_LINE),
        ),
        migrations.RunPython(drop_qty, restore_qty),
    ]
