from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('clientpulse', '0006_clientprofile_business_and_address')]

    operations = [
        migrations.AddField(
            model_name='clientpulsesettings',
            name='reminder_desktop_notifications_enabled',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='clientpulsesettings',
            name='reminder_poll_interval_seconds',
            field=models.PositiveSmallIntegerField(default=30),
        ),
        migrations.AddField(
            model_name='clientpulsesettings',
            name='reminder_popup_enabled',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='clientpulsesettings',
            name='reminder_sound',
            field=models.CharField(
                choices=[('chime', 'Chime'), ('bell', 'Bell'), ('soft', 'Soft')],
                default='chime', max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='clientpulsesettings',
            name='reminder_sound_enabled',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='clientpulsesettings',
            name='reminder_sound_volume',
            field=models.PositiveSmallIntegerField(default=70),
        ),
    ]
