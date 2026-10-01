from datetime import timedelta

from django.db import migrations
from django.utils import timezone


def seed_schedules(apps, schema_editor):
    Company = apps.get_model('tenancy', 'Company')
    Schedule = apps.get_model('task_management', 'BackgroundTaskSchedule')
    for company_id in Company.objects.values_list('id', flat=True):
        Schedule.objects.get_or_create(
            name=f'clientpulse-reminder-scan:{company_id}',
            defaults={
                'task_key': 'clientpulse.scan_due_reminders', 'handler_version': 1,
                'queue_name': 'clientpulse', 'payload': {'version': 1, 'company_id': company_id},
                'schedule_type': 'interval', 'interval_seconds': 60, 'timezone': 'UTC',
                'is_active': True, 'next_run_at': timezone.now() + timedelta(seconds=60),
                'dedupe_window_seconds': 30, 'max_concurrent_enqueues': 1,
                'company_id': company_id,
            },
        )


class Migration(migrations.Migration):
    dependencies = [
        ('clientpulse', '0004_clientreminder_clientremindernotification_and_more'),
        ('queue_management', '0009_add_clientpulse_integrations_queues'),
        ('task_management', '0001_initial'),
    ]
    operations = [migrations.RunPython(seed_schedules, migrations.RunPython.noop)]
