from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('trading', '0050_automation_update_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='automationrule',
            name='zero_unmatched_qty',
            field=models.BooleanField(
                default=False,
                help_text='Treat Qty & Cost messages as complete snapshots and zero omitted products.',
            ),
        ),
        migrations.AddField(
            model_name='automatedpricecapture',
            name='zero_unmatched_qty',
            field=models.BooleanField(default=False),
        ),
    ]
