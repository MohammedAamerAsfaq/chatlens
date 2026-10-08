from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.clientpulse.models import (
    ClientProfile, ClientPulseSettings, ClientReminder, ClientReminderNotification,
)
from apps.clientpulse.services.reminder_service import (
    complete_reminder, scan_due_reminders, snooze_reminder,
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

    def test_completed_reminders_can_form_an_explicit_follow_up_thread(self):
        first = self._reminder(title='First action')
        complete_reminder(first.pk, self.user)
        second_response = self.client.post('/api/clientpulse/reminders/', {
            'profile_id': self.profile.pk,
            'linked_from_id': first.pk,
            'assigned_to_id': self.membership.pk,
            'title': 'Second action',
            'due_at': (timezone.now() + timedelta(days=1)).isoformat(),
        }, format='json')
        self.assertEqual(second_response.status_code, 201, second_response.data)
        second = ClientReminder.objects.get(pk=second_response.data['id'])
        self.assertEqual(second.linked_from, first)
        self.assertEqual(second.thread_key, first.thread_key)

        complete_reminder(second.pk, self.user)
        third_response = self.client.post('/api/clientpulse/reminders/', {
            'profile_id': self.profile.pk,
            'linked_from_id': second.pk,
            'title': 'Third action',
            'due_at': (timezone.now() + timedelta(days=2)).isoformat(),
        }, format='json')
        self.assertEqual(third_response.status_code, 201, third_response.data)

        thread = self.client.get(f'/api/clientpulse/reminders/{first.pk}/thread/')
        self.assertEqual(thread.status_code, 200, thread.data)
        self.assertEqual(
            [item['title'] for item in thread.data['results']],
            ['First action', 'Second action', 'Third action'],
        )
        self.assertIsNone(thread.data['results'][0]['linked_from'])
        self.assertEqual(thread.data['results'][2]['linked_from']['id'], second.pk)

        separate = self._reminder(title='Separate thread')
        self.assertNotEqual(separate.thread_key, first.thread_key)

    def test_follow_up_requires_a_completed_reminder_for_the_same_client(self):
        active = self._reminder(title='Not complete')
        payload = {
            'profile_id': self.profile.pk,
            'linked_from_id': active.pk,
            'title': 'Premature follow-up',
            'due_at': (timezone.now() + timedelta(days=1)).isoformat(),
        }
        response = self.client.post('/api/clientpulse/reminders/', payload, format='json')
        self.assertEqual(response.status_code, 409, response.data)

        complete_reminder(active.pk, self.user)
        other_contact = CompanyContact.objects.create(
            company=self.company, display_name='Other Reminder Client',
        )
        other_profile = ClientProfile.objects.create(
            company=self.company, contact=other_contact,
            owner=self.membership, created_by=self.user,
        )
        payload['profile_id'] = other_profile.pk
        response = self.client.post('/api/clientpulse/reminders/', payload, format='json')
        self.assertEqual(response.status_code, 400, response.data)

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

    def test_edit_reschedules_due_reminder_and_clears_notification(self):
        reminder = self._reminder(status='due')
        ClientReminderNotification.objects.create(
            company=self.company, reminder=reminder, recipient=self.membership,
        )
        new_due = timezone.now() + timedelta(days=1)
        response = self.client.patch(f'/api/clientpulse/reminders/{reminder.pk}/', {
            'title': 'Updated follow up', 'due_at': new_due.isoformat(),
            'priority': 'critical',
        }, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        reminder.refresh_from_db()
        self.assertEqual(reminder.title, 'Updated follow up')
        self.assertEqual(reminder.status, 'pending')
        self.assertEqual(reminder.priority, 'critical')
        self.assertFalse(ClientReminderNotification.objects.filter(reminder=reminder).exists())

    def test_notification_can_be_dismissed_without_completing_reminder(self):
        reminder = self._reminder(status='due')
        notification = ClientReminderNotification.objects.create(
            company=self.company, reminder=reminder, recipient=self.membership,
        )
        response = self.client.post(
            f'/api/clientpulse/notifications/{notification.pk}/dismiss/', format='json',
        )
        self.assertEqual(response.status_code, 200, response.data)
        notification.refresh_from_db(); reminder.refresh_from_db()
        self.assertIsNotNone(notification.read_at)
        self.assertIsNotNone(notification.dismissed_at)
        self.assertEqual(reminder.status, 'due')
        self.assertEqual(self.client.get('/api/clientpulse/notifications/').data, [])

    def test_snooze_hides_current_notification_until_next_delivery(self):
        reminder = self._reminder(status='due')
        notification = ClientReminderNotification.objects.create(
            company=self.company, reminder=reminder, recipient=self.membership,
        )
        snooze_reminder(reminder.pk, self.user, timezone.now() + timedelta(hours=1))
        notification.refresh_from_db()
        self.assertIsNotNone(notification.read_at)
        self.assertIsNotNone(notification.dismissed_at)
        self.assertEqual(self.client.get('/api/clientpulse/notifications/').data, [])

    def test_notification_preferences_are_available_to_reminder_viewers(self):
        settings = ClientPulseSettings.objects.get(company=self.company)
        settings.reminder_sound = 'bell'
        settings.reminder_poll_interval_seconds = 20
        settings.save()
        response = self.client.get('/api/clientpulse/notification-preferences/')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['reminder_sound'], 'bell')
        self.assertEqual(response.data['reminder_poll_interval_seconds'], 20)

    def test_completed_reminder_cannot_be_edited(self):
        reminder = self._reminder(status='completed', completed_at=timezone.now())
        response = self.client.patch(
            f'/api/clientpulse/reminders/{reminder.pk}/', {'title': 'Unsafe edit'}, format='json',
        )
        self.assertEqual(response.status_code, 400)
