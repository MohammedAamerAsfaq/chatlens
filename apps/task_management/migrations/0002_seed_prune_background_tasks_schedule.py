from datetime import timedelta

from django.db import migrations
from django.utils import timezone


def seed_schedule(apps, schema_editor):
    Schedule = apps.get_model('task_management', 'BackgroundTaskSchedule')
    Schedule.objects.get_or_create(
        name='maintenance-prune-background-tasks',
        defaults={
            'task_key': 'maintenance.prune_background_tasks', 'handler_version': 1,
            'queue_name': 'default', 'payload': {'version': 1},
            'schedule_type': 'interval', 'interval_seconds': 3600, 'timezone': 'UTC',
            'is_active': True, 'next_run_at': timezone.now() + timedelta(minutes=5),
            'dedupe_window_seconds': 300, 'max_concurrent_enqueues': 1,
            'company': None,
        },
    )


def unseed_schedule(apps, schema_editor):
    Schedule = apps.get_model('task_management', 'BackgroundTaskSchedule')
    Schedule.objects.filter(name='maintenance-prune-background-tasks').delete()


class Migration(migrations.Migration):
    dependencies = [
        ('task_management', '0001_initial'),
        ('queue_management', '0002_seed_initial_queues'),
    ]
    operations = [migrations.RunPython(seed_schedule, unseed_schedule)]
