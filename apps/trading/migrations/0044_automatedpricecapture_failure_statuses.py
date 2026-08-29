from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('trading', '0043_v2matchtrainingsample'),
    ]

    operations = [
        migrations.AddField(
            model_name='automatedpricecapture',
            name='error',
            field=models.TextField(blank=True),
        ),
        migrations.AlterField(
            model_name='automatedpricecapture',
            name='status',
            field=models.CharField(
                choices=[
                    ('queued', 'Queued'),
                    ('applied', 'Applied'),
                    ('ignored', 'Ignored'),
                    ('test', 'Test match'),
                    ('parse_failed', 'Parse failed'),
                    ('no_priced_items', 'No priced items'),
                    ('apply_failed', 'Apply failed'),
                ],
                default='queued',
                max_length=20,
            ),
        ),
    ]
