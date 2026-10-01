from datetime import timedelta

from django.utils import timezone

from apps.task_management.models import BackgroundTaskSchedule


def ensure_company_reminder_schedule(company):
    return BackgroundTaskSchedule.objects.update_or_create(
        name=f'clientpulse-reminder-scan:{company.pk}',
        defaults={
            'task_key': 'clientpulse.scan_due_reminders', 'handler_version': 1,
            'queue_name': 'clientpulse', 'payload': {'version': 1, 'company_id': company.pk},
            'schedule_type': BackgroundTaskSchedule.TYPE_INTERVAL,
            'interval_seconds': 60, 'timezone': 'UTC', 'is_active': True,
            'next_run_at': timezone.now() + timedelta(seconds=60),
            'dedupe_window_seconds': 30,
            'max_concurrent_enqueues': 1, 'company': company,
        },
    )
