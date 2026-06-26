from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('whatsapp_bridge', '0002_add_media_url_to_message'),
    ]

    operations = [
        migrations.AddField(
            model_name='whatsappaccount',
            name='sync_history',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='whatsappaccount',
            name='history_days',
            field=models.IntegerField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name='whatsappaccount',
            name='idle_disconnect_minutes',
            field=models.IntegerField(default=0),
        ),
    ]
