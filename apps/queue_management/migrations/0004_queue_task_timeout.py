from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('queue_management', '0003_set_automation_concurrency')]

    operations = [
        migrations.AddField(
            model_name='queuedefinition',
            name='task_timeout_seconds',
            field=models.PositiveIntegerField(default=300),
        ),
    ]
