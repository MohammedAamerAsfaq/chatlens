import socket
import threading
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import timedelta

from django.db import IntegrityError, close_old_connections, transaction
from django.utils import timezone

from apps.task_management.models import BackgroundTask, BackgroundTaskEvent, BackgroundTaskSchedule
from apps.task_management.registry import TaskRegistrationError, task_registry
from .models import BackgroundWorker, QueueDefinition


class QueueConfigurationError(RuntimeError):
    pass


task_deadline = ContextVar('task_deadline', default=None)


class TaskDeadlineExceeded(TimeoutError):
    pass


class WorkerSuperseded(RuntimeError):
    pass


def run_ai_call_with_deadline(callable_func):
    """Limit AI waiting without allowing a timed-out handler to apply late data."""
    deadline = task_deadline.get()
    if deadline is None:
        return callable_func()
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TaskDeadlineExceeded('Task AI deadline exceeded.')
    done, result = threading.Event(), {}

    def run():
        try:
            result['value'] = callable_func()
        except BaseException as exc:
            result['error'] = exc
        finally:
            done.set()

    threading.Thread(target=run, daemon=True, name='chatlens-ai-call').start()
    if not done.wait(remaining):
        raise TaskDeadlineExceeded('Task AI deadline exceeded.')
    if 'error' in result:
        raise result['error']
    return result['value']


def _ensure_task_handlers_registered():
    # Importing handlers performs explicit decorator registration once per process.
    from apps.task_management import handlers  # noqa: F401
    from apps.message_intelligence import embedding_task_handlers  # noqa: F401


def _event(task, event_type, *, worker_id='', message='', metadata=None, error='', traceback_text=''):
    return BackgroundTaskEvent.objects.create(
        task=task, event_type=event_type, worker_id=worker_id,
        attempt_number=task.attempts, message=message, metadata=metadata or {},
        error=error, traceback=traceback_text,
    )


def get_queue(queue_name, *, for_enqueue=False):
    try:
        queue = QueueDefinition.objects.get(name=queue_name)
    except QueueDefinition.DoesNotExist as exc:
        raise QueueConfigurationError(f'Unknown queue: {queue_name}') from exc
    if not queue.is_enabled:
        raise QueueConfigurationError(f'Queue is disabled: {queue_name}')
    if for_enqueue and queue.is_paused:
        raise QueueConfigurationError(f'Queue is paused: {queue_name}')
    return queue


def enqueue_task(*, task_key, payload, queue_name=None, priority=100, idempotency_key=None,
                 correlation_id=None, handler_version=1, available_at=None, max_attempts=None,
                 company=None, created_by=None):
    """Durably enqueue a task or raise an explicit configuration/validation error."""
    _ensure_task_handlers_registered()
    definition = task_registry.get(task_key, handler_version)
    definition.payload_validator(payload)
    if definition.idempotency_required and not idempotency_key:
        raise ValueError(f'idempotency_key is required for {task_key}')
    selected_queue = queue_name or definition.default_queue
    queue = get_queue(selected_queue, for_enqueue=True)
    now = timezone.now()

    with transaction.atomic():
        if idempotency_key:
            existing = (
                BackgroundTask.objects.select_for_update()
                .filter(task_key=task_key, idempotency_key=idempotency_key,
                        status__in=BackgroundTask.ACTIVE_STATUSES)
                .first()
            )
            if existing:
                return existing
        try:
            task = BackgroundTask.objects.create(
                task_key=task_key, handler_version=handler_version, queue_name=selected_queue,
                priority=priority, payload=payload, idempotency_key=idempotency_key or '',
                correlation_id=correlation_id or uuid.uuid4().hex,
                max_attempts=max_attempts or queue.default_max_attempts,
                available_at=available_at or now, company=company, created_by=created_by,
            )
        except IntegrityError:
            # The partial unique constraint is the cross-process idempotency backstop.
            if not idempotency_key:
                raise
            task = BackgroundTask.objects.get(
                task_key=task_key, idempotency_key=idempotency_key,
                status__in=BackgroundTask.ACTIVE_STATUSES,
            )
            return task
        _event(task, BackgroundTaskEvent.EVENT_ENQUEUED, message='Task durably enqueued.')
    return task


def claim_tasks(queue_name, worker_id, limit=1):
    queue = get_queue(queue_name)
    if queue.is_paused:
        return []
    now = timezone.now()
    with transaction.atomic():
        tasks = list(
            BackgroundTask.objects.select_for_update(skip_locked=True)
            .filter(queue_name=queue_name, status__in=[BackgroundTask.STATUS_PENDING, BackgroundTask.STATUS_RETRYING], available_at__lte=now)
            .order_by('priority', 'available_at', 'created_at')[:max(1, min(limit, queue.max_concurrency))]
        )
        for task in tasks:
            task.status = BackgroundTask.STATUS_CLAIMED
            task.locked_at = now
            task.locked_by = worker_id
            task.heartbeat_at = now
            task.attempts += 1
            task.save(update_fields=['status', 'locked_at', 'locked_by', 'heartbeat_at', 'attempts', 'updated_at'])
            _event(task, BackgroundTaskEvent.EVENT_CLAIMED, worker_id=worker_id, message='Task claimed by worker.')
    return tasks


def retry_delay_seconds(task, queue):
    return min(queue.retry_backoff_base_seconds * (2 ** max(0, task.attempts - 1)), queue.retry_backoff_max_seconds)


def release_stale_locks(queue_name=None):
    """Recover stale claims only when the handler explicitly declares retry safety."""
    _ensure_task_handlers_registered()
    released = failed = 0
    queues = QueueDefinition.objects.all()
    if queue_name:
        queues = queues.filter(name=queue_name)
    now = timezone.now()
    for queue in queues:
        cutoff = now - timedelta(seconds=queue.lock_timeout_seconds)
        with transaction.atomic():
            tasks = list(
                BackgroundTask.objects.select_for_update(skip_locked=True)
                .filter(queue_name=queue.name, status__in=[BackgroundTask.STATUS_CLAIMED, BackgroundTask.STATUS_RUNNING], heartbeat_at__lt=cutoff)
            )
            for task in tasks:
                try:
                    definition = task_registry.get(task.task_key, task.handler_version)
                except TaskRegistrationError as exc:
                    definition = None
                    reason = str(exc)
                else:
                    reason = 'Worker heartbeat expired while task was owned.'
                worker = BackgroundWorker.objects.filter(worker_id=task.locked_by).first()
                worker_stale = not worker or worker.last_heartbeat_at < cutoff
                safe_to_retry = bool(definition and definition.retry_safe and worker_stale and task.attempts < task.max_attempts)
                _event(task, BackgroundTaskEvent.EVENT_LOCK_RELEASED, worker_id=task.locked_by, message=reason, metadata={'worker_stale': worker_stale})
                if safe_to_retry:
                    delay = retry_delay_seconds(task, queue)
                    task.status = BackgroundTask.STATUS_RETRYING
                    task.available_at = now + timedelta(seconds=delay)
                    task.locked_at = None
                    task.locked_by = ''
                    task.heartbeat_at = None
                    task.last_error = reason
                    task.save(update_fields=['status', 'available_at', 'locked_at', 'locked_by', 'heartbeat_at', 'last_error', 'updated_at'])
                    _event(task, BackgroundTaskEvent.EVENT_RETRY_SCHEDULED, message='Stale lock released for retry.', metadata={'delay_seconds': delay})
                    released += 1
                else:
                    task.status = BackgroundTask.STATUS_FAILED
                    task.finished_at = now
                    task.last_error = f'{reason} Retry was unsafe or attempts were exhausted.'
                    task.save(update_fields=['status', 'finished_at', 'last_error', 'updated_at'])
                    _event(task, BackgroundTaskEvent.EVENT_FAILED, message='Stale task failed explicitly.', error=task.last_error)
                    failed += 1
    return {'released': released, 'failed': failed}


@dataclass(frozen=True)
class TaskExecutionContext:
    task_id: int
    worker_id: str
    correlation_id: str


class TaskExecutor:
    def __init__(self, worker_id):
        self.worker_id = worker_id

    def _heartbeat_task(self, task_id, stop_event, interval):
        while not stop_event.wait(interval):
            BackgroundTask.objects.filter(pk=task_id, locked_by=self.worker_id, status=BackgroundTask.STATUS_RUNNING).update(heartbeat_at=timezone.now())

    def execute(self, task_id):
        _ensure_task_handlers_registered()
        with transaction.atomic():
            task = BackgroundTask.objects.select_for_update().get(pk=task_id)
            if task.status != BackgroundTask.STATUS_CLAIMED or task.locked_by != self.worker_id:
                raise RuntimeError(f'Task {task_id} is not claimed by worker {self.worker_id}.')
            task.status = BackgroundTask.STATUS_RUNNING
            task.started_at = timezone.now()
            task.heartbeat_at = task.started_at
            task.save(update_fields=['status', 'started_at', 'heartbeat_at', 'updated_at'])
            _event(task, BackgroundTaskEvent.EVENT_STARTED, worker_id=self.worker_id, message='Task handler entered.')

        heartbeat_stop = threading.Event()
        queue = get_queue(task.queue_name)
        heartbeat_thread = threading.Thread(
            target=self._heartbeat_task,
            args=(task.pk, heartbeat_stop, max(1, queue.lock_timeout_seconds // 3)), daemon=True,
        )
        heartbeat_thread.start()
        deadline_token = task_deadline.set(time.monotonic() + queue.task_timeout_seconds)
        try:
            definition = task_registry.get(task.task_key, task.handler_version)
            definition.payload_validator(task.payload)
            result = definition.handler(task.payload, TaskExecutionContext(task.pk, self.worker_id, task.correlation_id))
            if result is None:
                result = {}
            if not isinstance(result, dict):
                raise ValueError('Task handler result must be a JSON object.')
        except Exception as exc:
            self._fail(task.pk, exc)
            return False
        finally:
            task_deadline.reset(deadline_token)
            heartbeat_stop.set()
            heartbeat_thread.join(timeout=1)

        with transaction.atomic():
            task = BackgroundTask.objects.select_for_update().get(pk=task_id)
            task.status = BackgroundTask.STATUS_SUCCEEDED
            task.result = result
            task.finished_at = timezone.now()
            task.heartbeat_at = task.finished_at
            task.save(update_fields=['status', 'result', 'finished_at', 'heartbeat_at', 'updated_at'])
            _event(task, BackgroundTaskEvent.EVENT_SUCCEEDED, worker_id=self.worker_id, message='Task completed.', metadata={'result': result})
        return True

    def _fail(self, task_id, exc):
        traceback_text = traceback.format_exc()
        with transaction.atomic():
            task = BackgroundTask.objects.select_for_update().get(pk=task_id)
            queue = get_queue(task.queue_name)
            definition = task_registry.get(task.task_key, task.handler_version)
            error = f'{type(exc).__name__}: {exc}'
            task.last_error = error
            task.last_traceback = traceback_text
            if definition.retry_safe and task.attempts < task.max_attempts:
                delay = retry_delay_seconds(task, queue)
                task.status = BackgroundTask.STATUS_RETRYING
                task.available_at = timezone.now() + timedelta(seconds=delay)
                task.locked_at = None
                task.locked_by = ''
                task.heartbeat_at = None
                task.save(update_fields=['status', 'available_at', 'locked_at', 'locked_by', 'heartbeat_at', 'last_error', 'last_traceback', 'updated_at'])
                _event(task, BackgroundTaskEvent.EVENT_RETRY_SCHEDULED, worker_id=self.worker_id, message='Handler failed; retry scheduled.', metadata={'delay_seconds': delay}, error=error, traceback_text=traceback_text)
            else:
                task.status = BackgroundTask.STATUS_FAILED
                task.finished_at = timezone.now()
                task.save(update_fields=['status', 'finished_at', 'last_error', 'last_traceback', 'updated_at'])
                _event(task, BackgroundTaskEvent.EVENT_FAILED, worker_id=self.worker_id, message='Handler failed permanently.', error=error, traceback_text=traceback_text)


class TaskWorker:
    def __init__(self, queue_names, worker_id=None, version='1', concurrency=None):
        self.queue_names = queue_names
        self.worker_id = worker_id or f'{socket.gethostname()}:{uuid.uuid4().hex}'
        self.version = version
        self.concurrency = concurrency
        self._worker = None
        self._executor = None
        self._futures = {}

    def start(self):
        configured_concurrency = sum(
            QueueDefinition.objects.filter(name__in=self.queue_names, is_enabled=True)
            .values_list('max_concurrency', flat=True)
        )
        self.concurrency = max(1, self.concurrency or configured_concurrency)
        self._executor = ThreadPoolExecutor(
            max_workers=self.concurrency,
            thread_name_prefix='chatlens-task',
        )
        now = timezone.now()
        # One worker owns a queue set at a time. Older registrations are retired
        # before this worker announces itself, so the operations monitor is not
        # left showing abandoned worker instances as running.
        for prior in BackgroundWorker.objects.filter(status=BackgroundWorker.STATUS_RUNNING).exclude(worker_id=self.worker_id):
            if set(prior.queue_names or ()) & set(self.queue_names):
                BackgroundWorker.objects.filter(pk=prior.pk).update(
                    status=BackgroundWorker.STATUS_STOPPED,
                    stopped_at=now,
                    last_heartbeat_at=now,
                )
        self._worker, _ = BackgroundWorker.objects.update_or_create(
            worker_id=self.worker_id,
            defaults={'hostname': socket.gethostname(), 'process_id': __import__('os').getpid(), 'queue_names': self.queue_names,
                      'status': BackgroundWorker.STATUS_RUNNING, 'version': self.version, 'started_at': now,
                      'metadata': {'concurrency': self.concurrency},
                      'last_heartbeat_at': now, 'stopped_at': None},
        )

    def heartbeat(self):
        updated = BackgroundWorker.objects.filter(
            worker_id=self.worker_id,
            status=BackgroundWorker.STATUS_RUNNING,
        ).update(last_heartbeat_at=timezone.now())
        if not updated:
            raise WorkerSuperseded(f'Worker {self.worker_id} was superseded by a newer worker.')

    def stop(self, wait=True):
        if self._executor is not None:
            self._executor.shutdown(wait=wait)
            self._executor = None
        BackgroundWorker.objects.filter(worker_id=self.worker_id).update(status=BackgroundWorker.STATUS_STOPPED, stopped_at=timezone.now(), last_heartbeat_at=timezone.now())

    def _reap_completed_futures(self):
        for future in list(self._futures):
            if future.done():
                # Re-raise unexpected executor errors in the worker process instead
                # of silently losing a task outside TaskExecutor's failure handling.
                future.result()
                del self._futures[future]

    def _active_for_queue(self, queue_name):
        return sum(1 for queue in self._futures.values() if queue == queue_name)

    def wait_for_tasks(self):
        for future in list(self._futures):
            future.result()
        self._reap_completed_futures()

    def _execute_in_thread(self, task_id):
        close_old_connections()
        try:
            return TaskExecutor(self.worker_id).execute(task_id)
        finally:
            close_old_connections()

    def run_once(self, limit=None, asynchronous=False):
        self.heartbeat()
        self._reap_completed_futures()
        total = 0
        executor = TaskExecutor(self.worker_id)
        for queue_name in self.queue_names:
            release_stale_locks(queue_name)
            queue = get_queue(queue_name)
            available = queue.max_concurrency - self._active_for_queue(queue_name)
            if asynchronous:
                available = min(available, self.concurrency - len(self._futures))
            if available <= 0:
                continue
            claim_limit = min(limit or queue.max_concurrency, available)
            tasks = claim_tasks(queue_name, self.worker_id, limit=claim_limit)
            for task in tasks:
                if asynchronous:
                    future = self._executor.submit(self._execute_in_thread, task.pk)
                    self._futures[future] = queue_name
                else:
                    executor.execute(task.pk)
                total += 1
        return total


def enqueue_due_schedules(worker_id='scheduler'):
    """The scheduler only produces tasks; it never executes business logic."""
    _ensure_task_handlers_registered()
    now = timezone.now()
    enqueued = skipped = 0
    with transaction.atomic():
        schedules = list(
            BackgroundTaskSchedule.objects.select_for_update(skip_locked=True)
            .filter(is_active=True, next_run_at__lte=now).order_by('next_run_at')
        )
        for schedule in schedules:
            if schedule.dedupe_window_seconds and schedule.last_enqueued_at and schedule.last_enqueued_at >= now - timedelta(seconds=schedule.dedupe_window_seconds):
                schedule.last_error = 'Schedule occurrence skipped by dedupe window.'
                _advance_schedule(schedule, now)
                schedule.save(update_fields=['last_error', 'next_run_at', 'is_active', 'updated_at'])
                skipped += 1
                continue
            active_count = BackgroundTask.objects.filter(
                task_key=schedule.task_key, queue_name=schedule.queue_name,
                status__in=BackgroundTask.ACTIVE_STATUSES,
                correlation_id__startswith=f'schedule:{schedule.pk}:',
            ).count()
            if active_count >= schedule.max_concurrent_enqueues:
                schedule.last_error = 'Schedule occurrence skipped by max concurrent enqueues.'
                _advance_schedule(schedule, now)
                schedule.save(update_fields=['last_error', 'next_run_at', 'is_active', 'updated_at'])
                skipped += 1
                continue
            slot = int(schedule.next_run_at.timestamp())
            enqueue_task(
                task_key=schedule.task_key, handler_version=schedule.handler_version,
                queue_name=schedule.queue_name, payload=schedule.payload,
                idempotency_key=f'schedule:{schedule.pk}:{slot}', correlation_id=f'schedule:{schedule.pk}:{slot}',
                company=schedule.company, created_by=schedule.created_by,
            )
            schedule.last_enqueued_at = now
            schedule.last_run_at = now
            schedule.last_error = ''
            _advance_schedule(schedule, now)
            schedule.save(update_fields=['last_enqueued_at', 'last_run_at', 'last_error', 'next_run_at', 'is_active', 'updated_at'])
            enqueued += 1
    return {'enqueued': enqueued, 'skipped': skipped, 'worker_id': worker_id}


def _advance_schedule(schedule, now):
    if schedule.schedule_type == BackgroundTaskSchedule.TYPE_ONE_OFF:
        schedule.is_active = False
        schedule.next_run_at = None
    elif schedule.schedule_type == BackgroundTaskSchedule.TYPE_INTERVAL:
        if not schedule.interval_seconds:
            raise ValueError(f'Interval schedule {schedule.pk} has no interval_seconds.')
        base = schedule.next_run_at or now
        schedule.next_run_at = base + timedelta(seconds=schedule.interval_seconds)
        while schedule.next_run_at <= now:
            schedule.next_run_at += timedelta(seconds=schedule.interval_seconds)
    else:
        raise ValueError(f'Unsupported schedule type: {schedule.schedule_type}')
