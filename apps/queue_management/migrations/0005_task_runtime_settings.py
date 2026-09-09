from django.db import migrations, models


def create_runtime_settings(apps, schema_editor):
    apps.get_model('queue_management', 'TaskRuntimeSettings').objects.get_or_create(pk=1)


class Migration(migrations.Migration):
    dependencies = [('queue_management', '0004_queue_task_timeout')]
    operations = [
        migrations.CreateModel(name='TaskRuntimeSettings', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('automation_mode', models.CharField(default='thread', max_length=20)),
            ('embedding_mode', models.CharField(default='thread', max_length=20)),
            ('classification_mode', models.CharField(default='thread', max_length=20)),
            ('recovery_mode', models.CharField(default='thread', max_length=20)),
            ('worker_heartbeat_seconds', models.PositiveIntegerField(default=15)),
            ('scheduler_interval_seconds', models.PositiveIntegerField(default=5)),
            ('updated_at', models.DateTimeField(auto_now=True)),
        ], options={'db_table': 'queue_management_task_runtime_settings'}),
        migrations.RunPython(create_runtime_settings, migrations.RunPython.noop),
    ]
