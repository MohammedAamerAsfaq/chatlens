from datetime import timedelta
import threading
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.contrib.auth.models import User
from django.utils import timezone

from apps.task_management.models import BackgroundTask, BackgroundTaskEvent, BackgroundTaskSchedule
from apps.task_management.registry import TaskDefinition, task_registry, validate_any_v1_payload
from apps.queue_management.models import BackgroundWorker, QueueDefinition
from apps.queue_management.services import (
    TaskWorker, claim_tasks, enqueue_due_schedules, enqueue_task, release_stale_locks,
)


def _test_handler(payload, context):
    return {'value': payload['value'], 'task_id': context.task_id}


def _failing_handler(payload, context):
    raise RuntimeError('planned failure')


_blocking_started = threading.Event()
_blocking_release = threading.Event()


def _blocking_handler(payload, context):
    _blocking_started.set()
    _blocking_release.wait(timeout=5)
    return {'completed': True}


def _register_test_handler(key, handler, retry_safe=True):
    try:
        return task_registry.get(key)
    except Exception:
        task_registry.register(TaskDefinition(
            key=key, version=1, default_queue='default',
            payload_validator=validate_any_v1_payload,
            idempotency_required=True, retry_safe=retry_safe, handler=handler,
        ))
        return task_registry.get(key)


class DurableTaskQueueTests(TestCase):
    def setUp(self):
        _register_test_handler('tests.success', _test_handler)
        _register_test_handler('tests.failure', _failing_handler)
        _register_test_handler('tests.timeout', _blocking_handler)
        _register_test_handler('tests.unsafe', _test_handler, retry_safe=False)
        QueueDefinition.objects.filter(name='default').update(retry_backoff_base_seconds=1, retry_backoff_max_seconds=1)

    def test_duplicate_active_enqueue_returns_same_task(self):
        first = enqueue_task(task_key='tests.success', payload={'version': 1, 'value': 'x'}, idempotency_key='same')
        second = enqueue_task(task_key='tests.success', payload={'version': 1, 'value': 'x'}, idempotency_key='same')
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(BackgroundTask.objects.count(), 1)

    def test_claim_and_execute_records_lifecycle(self):
        task = enqueue_task(task_key='tests.success', payload={'version': 1, 'value': 'ok'}, idempotency_key='success')
        worker = TaskWorker(['default'], worker_id='test-worker')
        worker.start()
        self.assertEqual(worker.run_once(), 1)
        task.refresh_from_db()
        self.assertEqual(task.status, BackgroundTask.STATUS_SUCCEEDED)
        self.assertEqual(task.result['value'], 'ok')
        self.assertEqual(
            list(task.events.values_list('event_type', flat=True)),
            [BackgroundTaskEvent.EVENT_ENQUEUED, BackgroundTaskEvent.EVENT_CLAIMED, BackgroundTaskEvent.EVENT_STARTED, BackgroundTaskEvent.EVENT_SUCCEEDED],
        )

    def test_async_worker_starts_multiple_tasks_without_waiting_for_predecessor(self):
        QueueDefinition.objects.filter(name='default').update(max_concurrency=2)
        enqueue_task(task_key='tests.success', payload={'version': 1, 'value': 'first'}, idempotency_key='parallel-first')
        enqueue_task(task_key='tests.success', payload={'version': 1, 'value': 'second'}, idempotency_key='parallel-second')
        started = threading.Event()
        release = threading.Event()
        task_ids = []

        def slow_execute(*args):
            task_id = args[-1]
            task_ids.append(task_id)
            if len(task_ids) == 2:
                started.set()
            release.wait(timeout=2)
            return True

        worker = TaskWorker(['default'], worker_id='parallel-worker')
        worker.start()
        try:
            with patch('apps.queue_management.services.TaskExecutor.execute', side_effect=slow_execute):
                self.assertEqual(worker.run_once(asynchronous=True), 2)
                self.assertTrue(started.wait(timeout=1), 'second task did not start while first task was active')
                release.set()
                worker.wait_for_tasks()
        finally:
            release.set()
            worker.stop()
        self.assertEqual(len(task_ids), 2)

    def test_start_supersedes_prior_worker_for_same_queue(self):
        first = TaskWorker(['default'], worker_id='first-worker')
        first.start()
        second = TaskWorker(['default'], worker_id='second-worker')
        second.start()
        first._worker.refresh_from_db()
        self.assertEqual(first._worker.status, 'stopped')
        with self.assertRaises(Exception):
            first.run_once()
        second.stop()

    def test_start_discards_pending_live_backlog(self):
        task = enqueue_task(
            task_key='whatsapp.persist_live_message',
            payload={
                'version': 1,
                'account_id': 44,
                'message': {
                    'worker_session_id': 44,
                    'provider_message_id': 'old-live-message',
                    'chat_id': '120363000000000000@g.us',
                    'direction': 'inbound',
                    'message_time': (timezone.now() - timedelta(minutes=5)).isoformat(),
                },
            },
            idempotency_key='old-live-message',
        )

        worker = TaskWorker(['live_ingestion'], worker_id='fresh-live-worker')
        worker.start()
        worker.stop()

        task.refresh_from_db()
        self.assertEqual(task.status, BackgroundTask.STATUS_CANCELLED)
        self.assertEqual(
            task.events.last().event_type,
            BackgroundTaskEvent.EVENT_CANCELLED,
        )

    def test_handler_failure_schedules_retry_then_final_failure(self):
        task = enqueue_task(task_key='tests.failure', payload={'version': 1}, idempotency_key='failure', max_attempts=2)
        worker = TaskWorker(['default'], worker_id='failing-worker')
        worker.start()
        worker.run_once()
        task.refresh_from_db()
        self.assertEqual(task.status, BackgroundTask.STATUS_RETRYING)
        BackgroundTask.objects.filter(pk=task.pk).update(available_at=timezone.now())
        worker.run_once()
        task.refresh_from_db()
        self.assertEqual(task.status, BackgroundTask.STATUS_FAILED)
        self.assertEqual(task.attempts, 2)
        self.assertEqual(task.events.filter(event_type=BackgroundTaskEvent.EVENT_RETRY_SCHEDULED).count(), 1)

    def test_stale_retry_safe_lock_is_released(self):
        task = enqueue_task(task_key='tests.success', payload={'version': 1, 'value': 'x'}, idempotency_key='stale')
        TaskWorker(['default'], worker_id='dead-worker').start()
        claimed = claim_tasks('default', 'dead-worker')
        self.assertEqual(claimed[0].pk, task.pk)
        QueueDefinition.objects.filter(name='default').update(lock_timeout_seconds=1)
        BackgroundTask.objects.filter(pk=task.pk).update(heartbeat_at=timezone.now() - timedelta(seconds=10))
        BackgroundWorker.objects.filter(worker_id='dead-worker').update(
            last_heartbeat_at=timezone.now() - timedelta(seconds=10),
        )
        result = release_stale_locks('default')
        task.refresh_from_db()
        self.assertEqual(result['released'], 1)
        self.assertEqual(task.status, BackgroundTask.STATUS_RETRYING)

    def test_stale_non_retry_safe_lock_fails(self):
        task = enqueue_task(task_key='tests.unsafe', payload={'version': 1, 'value': 'x'}, idempotency_key='unsafe')
        TaskWorker(['default'], worker_id='dead-worker').start()
        claim_tasks('default', 'dead-worker')
        QueueDefinition.objects.filter(name='default').update(lock_timeout_seconds=1)
        BackgroundTask.objects.filter(pk=task.pk).update(heartbeat_at=timezone.now() - timedelta(seconds=10))
        BackgroundWorker.objects.filter(worker_id='dead-worker').update(
            last_heartbeat_at=timezone.now() - timedelta(seconds=10),
        )
        result = release_stale_locks('default')
        task.refresh_from_db()
        self.assertEqual(result['failed'], 1)
        self.assertEqual(task.status, BackgroundTask.STATUS_FAILED)

    def test_one_off_schedule_enqueues_once(self):
        schedule = BackgroundTaskSchedule.objects.create(
            name='test one-off', task_key='tests.success', queue_name='default',
            payload={'version': 1, 'value': 'scheduled'}, schedule_type=BackgroundTaskSchedule.TYPE_ONE_OFF,
            next_run_at=timezone.now() - timedelta(seconds=1),
        )
        result = enqueue_due_schedules()
        schedule.refresh_from_db()
        self.assertEqual(result['enqueued'], 1)
        self.assertFalse(schedule.is_active)
        self.assertIsNone(schedule.next_run_at)

    def test_interval_schedule_moves_to_next_occurrence(self):
        schedule = BackgroundTaskSchedule.objects.create(
            name='test interval', task_key='tests.success', queue_name='default',
            payload={'version': 1, 'value': 'scheduled'}, schedule_type=BackgroundTaskSchedule.TYPE_INTERVAL,
            interval_seconds=60, next_run_at=timezone.now() - timedelta(seconds=1),
        )
        enqueue_due_schedules()
        schedule.refresh_from_db()
        self.assertTrue(schedule.is_active)
        self.assertGreater(schedule.next_run_at, timezone.now())

    def test_task_api_returns_task_and_event_feedback(self):
        user = User.objects.create_user(username='queue-viewer', password='pw')
        from apps.tenancy.models import Company, CompanyMembership
        control = Company.objects.get(company_type=Company.TYPE_CONTROL)
        CompanyMembership.objects.create(
            company=control,
            user=user,
            role=CompanyMembership.ROLE_VIEWER,
        )
        task = enqueue_task(
            task_key='tests.success', payload={'version': 1, 'value': 'visible'},
            idempotency_key='visible', company=control,
        )
        self.client.force_login(user)
        response = self.client.get('/api/task-queue/tasks/', {'page': 1, 'page_size': 25})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['count'], 1)
        self.assertEqual(response.json()['page'], 1)
        self.assertEqual(response.json()['page_size'], 25)
        self.assertEqual(response.json()['total_pages'], 1)
        self.assertEqual(response.json()['results'][0]['correlation_id'], task.correlation_id)
        detail = self.client.get(f'/api/task-queue/tasks/{task.pk}/')
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()['events'][0]['event_type'], BackgroundTaskEvent.EVENT_ENQUEUED)

    def test_task_operations_are_strictly_scoped_to_active_company(self):
        from apps.tenancy.models import Company, CompanyMembership

        first = Company.objects.create(name='Queue Tenant One', slug='queue-tenant-one')
        second = Company.objects.create(name='Queue Tenant Two', slug='queue-tenant-two')
        user = User.objects.create_user(username='tenant-queue-viewer', password='pw')
        CompanyMembership.objects.create(
            company=first, user=user, role=CompanyMembership.ROLE_VIEWER,
        )
        own_task = enqueue_task(
            task_key='tests.success', payload={'version': 1, 'value': 'own'},
            idempotency_key='tenant-own', company=first,
        )
        other_task = enqueue_task(
            task_key='tests.success', payload={'version': 1, 'value': 'other'},
            idempotency_key='tenant-other', company=second,
        )
        global_task = enqueue_task(
            task_key='tests.success', payload={'version': 1, 'value': 'global'},
            idempotency_key='tenant-global',
        )
        BackgroundTaskSchedule.objects.create(
            name='tenant one schedule', task_key='tests.success', queue_name='default',
            payload={'version': 1}, schedule_type=BackgroundTaskSchedule.TYPE_INTERVAL,
            interval_seconds=60, next_run_at=timezone.now(), company=first,
        )
        BackgroundTaskSchedule.objects.create(
            name='tenant two schedule', task_key='tests.success', queue_name='default',
            payload={'version': 1}, schedule_type=BackgroundTaskSchedule.TYPE_INTERVAL,
            interval_seconds=60, next_run_at=timezone.now(), company=second,
        )
        BackgroundWorker.objects.create(
            worker_id='shared-worker', hostname='worker-host', process_id=123,
            queue_names=['default'], status=BackgroundWorker.STATUS_RUNNING,
            started_at=timezone.now(), last_heartbeat_at=timezone.now(),
        )

        self.client.force_login(user)
        response = self.client.get('/api/task-queue/tasks/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row['id'] for row in response.json()['results']], [own_task.pk])
        self.assertEqual(self.client.get(f'/api/task-queue/tasks/{other_task.pk}/').status_code, 404)
        self.assertEqual(self.client.get(f'/api/task-queue/tasks/{global_task.pk}/').status_code, 404)

        overview = self.client.get('/api/task-queue/overview/')
        self.assertEqual(overview.status_code, 200)
        self.assertFalse(overview.json()['infrastructure_visible'])
        self.assertEqual(overview.json()['workers'], [])
        self.assertEqual(
            [schedule['name'] for schedule in overview.json()['schedules']],
            ['tenant one schedule'],
        )

        superuser = User.objects.create_superuser(
            username='tenant-scoped-superuser', email='admin@example.com', password='pw',
        )
        self.client.force_login(superuser)
        session = self.client.session
        session['active_company_id'] = first.pk
        session.save()
        overview = self.client.get('/api/task-queue/overview/')
        self.assertFalse(overview.json()['infrastructure_visible'])
        self.assertEqual(overview.json()['workers'], [])
        self.assertEqual(self.client.get('/api/task-queue/settings/').status_code, 403)
