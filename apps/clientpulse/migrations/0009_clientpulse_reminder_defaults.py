from datetime import time

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('clientpulse', '0008_clientreminder_threads')]

    operations = [
        migrations.AddField(
            model_name='clientpulsesettings',
            name='reminder_default_delay_days',
            field=models.PositiveSmallIntegerField(default=7),
        ),
        migrations.AddField(
            model_name='clientpulsesettings',
            name='reminder_default_time',
            field=models.TimeField(default=time(10, 0)),
        ),
    ]
