from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.clientpulse.models import (
    ClientProfile, ClientPulseSettings, ClientReminder, ClientReminderNotification,
)
from apps.clientpulse.services.reminder_service import (
    complete_reminder, scan_due_reminders,
)
from apps.task_management.models import BackgroundTask, BackgroundTaskSchedule
from apps.queue_management.services import TaskExecutor, claim_tasks
from apps.queue_management.models import BackgroundWorker
from apps.tenancy.models import Company, CompanyContact, CompanyMembership
from apps.tenancy.services.enrollment_service import CompanyEnrollmentService
from apps.whatsapp_bridge.models import OutboundMessage


class ClientReminderTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name='Reminder Co', slug='reminder-co')
        self.user = get_user_model().objects.create_user('reminder-owner')
        self.membership = CompanyMembership.objects.create(
            company=self.company, user=self.user, role=CompanyMembership.ROLE_SUPER_USER,
        )
        contact = CompanyContact.objects.create(company=self.company, display_name='Reminder Client')
        self.profile = ClientProfile.objects.create(
            company=self.company, contact=contact, owner=self.membership, created_by=self.user,
        )
        ClientPulseSettings.objects.create(company=self.company)
        self.client = APIClient(); self.client.force_authenticate(self.user)

    def _reminder(self, **overrides):
        values = {
            'company': self.company, 'profile': self.profile,
            'assigned_to': self.membership, 'title': 'Follow up',
            'due_at': timezone.now() - timedelta(minutes=1), 'created_by': self.user,
        }
        values.update(overrides)
        return ClientReminder.objects.create(**values)

    def test_api_creates_and_lists_durable_reminder(self):
        due_at = timezone.now() + timedelta(hours=2)
        response = self.client.post('/api/clientpulse/reminders/', {
            'profile_id': self.profile.pk, 'assigned_to_id': self.membership.pk,
            'title': 'Call customer', 'due_at': due_at.isoformat(), 'priority': 'high',
        }, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        listed = self.client.get('/api/clientpulse/reminders/').data
        self.assertEqual(listed['count'], 1)
        self.assertEqual(listed['results'][0]['title'], 'Call customer')

    def test_recurring_completion_is_idempotent(self):
        reminder = self._reminder(recurrence_type='daily')
        _, first_next = complete_reminder(reminder.pk, self.user)
        _, second_next = complete_reminder(reminder.pk, self.user)
        self.assertEqual(first_next.pk, second_next.pk)
        self.assertEqual(first_next.occurrence_number, 2)
        self.assertEqual(ClientReminder.objects.filter(series_key=reminder.series_key).count(), 2)

    def test_scan_enqueues_once_and_delivery_is_in_app_only(self):
        reminder = self._reminder()
        first = scan_due_reminders(self.company.pk)
        second = scan_due_reminders(self.company.pk)
        self.assertEqual(first['due'], 1)
        self.assertEqual(second['due'], 0)
        self.assertEqual(BackgroundTask.objects.filter(task_key='clientpulse.deliver_reminder').count(), 1)
        now = timezone.now()
        BackgroundWorker.objects.create(
            worker_id='reminder-test-worker', hostname='test', process_id=1,
            queue_names=['clientpulse'], status=BackgroundWorker.STATUS_RUNNING,
            started_at=now, last_heartbeat_at=now,
        )
        task = claim_tasks('clientpulse', 'reminder-test-worker', limit=1)[0]
        self.assertTrue(TaskExecutor('reminder-test-worker').execute(task.pk))
        self.assertTrue(ClientReminderNotification.objects.filter(reminder=reminder).exists())
        self.assertEqual(OutboundMessage.objects.count(), 0)

    def test_disabled_reminders_do_not_enqueue(self):
        settings = ClientPulseSettings.objects.get(company=self.company)
        settings.reminders_enabled = False; settings.save()
        self._reminder()
        result = scan_due_reminders(self.company.pk)
        self.assertTrue(result['disabled'])
        self.assertFalse(BackgroundTask.objects.filter(task_key='clientpulse.deliver_reminder').exists())

    def test_enrollment_creates_company_schedule(self):
        result = CompanyEnrollmentService().enroll_company(
            company_name='Scheduled Company', email='schedule@example.com',
            username='schedule-owner', password='secret-pass-123',
        )
        schedule = BackgroundTaskSchedule.objects.get(
            name=f'clientpulse-reminder-scan:{result.company_id}',
        )
        self.assertEqual(schedule.queue_name, 'clientpulse')
        self.assertEqual(schedule.payload['company_id'], result.company_id)
