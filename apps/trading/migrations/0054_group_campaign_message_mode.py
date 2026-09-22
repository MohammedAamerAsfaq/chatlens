from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('trading', '0053_group_campaign_audiences'),
    ]

    operations = [
        migrations.AddField(
            model_name='buyinginquiry',
            name='message_mode',
            field=models.CharField(
                choices=[('formatted', 'Preformatted Products'), ('direct', 'Direct Message')],
                default='formatted',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='buyinginquiry',
            name='direct_message',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='sellingoffer',
            name='message_mode',
            field=models.CharField(
                choices=[('formatted', 'Preformatted Products'), ('direct', 'Direct Message')],
                default='formatted',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='sellingoffer',
            name='direct_message',
            field=models.TextField(blank=True),
        ),
    ]
