from datetime import timedelta

from dateutil.relativedelta import relativedelta
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.clientpulse.models import (
    ClientActivity, ClientPulseSettings, ClientReminder, ClientReminderNotification,
)
from apps.queue_management.services import enqueue_task


def _next_due_at(reminder):
    if reminder.recurrence_type == 'daily':
        return reminder.due_at + timedelta(days=1)
    if reminder.recurrence_type == 'weekly':
        return reminder.due_at + timedelta(weeks=1)
    if reminder.recurrence_type == 'monthly':
        return reminder.due_at + relativedelta(months=1)
    if reminder.recurrence_type == 'custom':
        return reminder.due_at + timedelta(days=int(reminder.recurrence_rule['interval_days']))
    return None


def _activity(reminder, actor, title, metadata=None):
    return ClientActivity.objects.create(
        company=reminder.company, profile=reminder.profile,
        activity_type='reminder', occurred_at=timezone.now(), title=title,
        metadata={'reminder_id': reminder.pk, **(metadata or {})}, created_by=actor,
    )


@transaction.atomic
def complete_reminder(reminder_id, actor):
    reminder = ClientReminder.objects.select_for_update().get(pk=reminder_id)
    if reminder.status == 'completed':
        return reminder, getattr(reminder, 'generated_occurrence', None)
    if reminder.status == 'cancelled':
        raise ValueError('A cancelled reminder cannot be completed.')
    now = timezone.now()
    next_due = _next_due_at(reminder)
    next_reminder = None
    if next_due:
        next_reminder, _ = ClientReminder.objects.get_or_create(
            previous_occurrence=reminder,
            defaults={
                'company': reminder.company, 'profile': reminder.profile,
                'assigned_to': reminder.assigned_to, 'title': reminder.title,
                'description': reminder.description, 'due_at': next_due,
                'timezone': reminder.timezone, 'priority': reminder.priority,
                'recurrence_type': reminder.recurrence_type,
                'recurrence_rule': reminder.recurrence_rule,
                'series_key': reminder.series_key,
                'occurrence_number': reminder.occurrence_number + 1,
                'created_by': actor,
            },
        )
    reminder.status = 'completed'
    reminder.completed_at = now
    reminder.completed_by = actor
    reminder.next_occurrence_at = next_due
    reminder.save(update_fields=[
        'status', 'completed_at', 'completed_by', 'next_occurrence_at', 'updated_at',
    ])
    ClientReminderNotification.objects.filter(reminder=reminder, read_at__isnull=True).update(read_at=now)
    _activity(reminder, actor, 'Reminder completed', {
        'next_reminder_id': next_reminder.pk if next_reminder else None,
    })
    return reminder, next_reminder


@transaction.atomic
def snooze_reminder(reminder_id, actor, snoozed_until):
    reminder = ClientReminder.objects.select_for_update().get(pk=reminder_id)
    if reminder.status in {'completed', 'cancelled'}:
        raise ValueError('Completed or cancelled reminders cannot be snoozed.')
    if snoozed_until <= timezone.now():
        raise ValueError('Snooze time must be in the future.')
    reminder.status = 'snoozed'
    reminder.snoozed_until = snoozed_until
    reminder.save(update_fields=['status', 'snoozed_until', 'updated_at'])
    _activity(reminder, actor, 'Reminder snoozed', {'snoozed_until': snoozed_until.isoformat()})
    return reminder


def scan_due_reminders(company_id):
    settings = ClientPulseSettings.objects.filter(company_id=company_id).first()
    if settings and not settings.reminders_enabled:
        return {'due': 0, 'disabled': True}
    now = timezone.now()
    with transaction.atomic():
        reminders = list(ClientReminder.objects.select_for_update(skip_locked=True).filter(
            Q(status='pending', due_at__lte=now)
            | Q(status='snoozed', snoozed_until__lte=now),
            company_id=company_id,
        ))
        for reminder in reminders:
            reminder.status = 'due'
            reminder.save(update_fields=['status', 'updated_at'])
            effective_due = reminder.snoozed_until or reminder.due_at
            enqueue_task(
                task_key='clientpulse.deliver_reminder', queue_name='clientpulse',
                payload={'version': 1, 'company_id': company_id, 'reminder_id': reminder.pk},
                idempotency_key=f'clientpulse:reminder:{reminder.pk}:{int(effective_due.timestamp())}',
                correlation_id=f'clientpulse-reminder:{reminder.pk}', company=reminder.company,
                created_by=reminder.created_by,
            )
    return {'due': len(reminders), 'disabled': False}


@transaction.atomic
def deliver_reminder(reminder_id, company_id):
    reminder = ClientReminder.objects.select_for_update().get(
        pk=reminder_id, company_id=company_id,
    )
    if reminder.status != 'due':
        return {'delivered': False, 'status': reminder.status}
    notification, _ = ClientReminderNotification.objects.update_or_create(
        reminder=reminder,
        defaults={
            'company': reminder.company, 'recipient': reminder.assigned_to,
            'read_at': None, 'dismissed_at': None,
        },
    )
    ClientReminderNotification.objects.filter(pk=notification.pk).update(delivered_at=timezone.now())
    ClientActivity.objects.get_or_create(
        company=reminder.company, profile=reminder.profile,
        source_model='client_reminder_due', source_id=str(reminder.pk),
        defaults={
            'activity_type': 'reminder', 'occurred_at': timezone.now(),
            'title': 'Reminder is due', 'summary': reminder.title,
            'metadata': {'reminder_id': reminder.pk},
        },
    )
    return {'delivered': True, 'reminder_id': reminder.pk, 'notification_id': notification.pk}
