from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('trading', '0051_automation_zero_unmatched_qty'),
    ]

    operations = [
        migrations.AddField(
            model_name='automationrule',
            name='regenerate_price_list',
            field=models.BooleanField(
                default=False,
                help_text='Regenerate the formatted WhatsApp price list after applying sale prices.',
            ),
        ),
        migrations.AddField(
            model_name='automatedpricecapture',
            name='regenerate_price_list',
            field=models.BooleanField(default=False),
        ),
    ]
