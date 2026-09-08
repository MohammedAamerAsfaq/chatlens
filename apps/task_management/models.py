from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from django.db.models import Q


class BackgroundTask(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_CLAIMED = 'claimed'
    STATUS_RUNNING = 'running'
    STATUS_RETRYING = 'retrying'
    STATUS_SUCCEEDED = 'succeeded'
    STATUS_FAILED = 'failed'
    STATUS_CANCELLED = 'cancelled'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'), (STATUS_CLAIMED, 'Claimed'),
        (STATUS_RUNNING, 'Running'), (STATUS_RETRYING, 'Retrying'),
        (STATUS_SUCCEEDED, 'Succeeded'), (STATUS_FAILED, 'Failed'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]
    ACTIVE_STATUSES = (STATUS_PENDING, STATUS_CLAIMED, STATUS_RUNNING, STATUS_RETRYING)

    task_key = models.CharField(max_length=150, db_index=True)
    handler_version = models.PositiveIntegerField(default=1)
    queue_name = models.CharField(max_length=100, db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)
    # Lower numbers execute first.
    priority = models.IntegerField(default=100, db_index=True)
    payload = models.JSONField(default=dict)
    result = models.JSONField(default=dict, blank=True)
    idempotency_key = models.CharField(max_length=255, blank=True, db_index=True)
    correlation_id = models.CharField(max_length=255, blank=True, db_index=True)
    attempts = models.PositiveIntegerField(default=0)
    max_attempts = models.PositiveIntegerField(default=3)
    available_at = models.DateTimeField(db_index=True)
    locked_at = models.DateTimeField(null=True, blank=True)
    locked_by = models.CharField(max_length=255, blank=True, db_index=True)
    heartbeat_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    last_traceback = models.TextField(blank=True)
    company = models.ForeignKey('tenancy.Company', null=True, blank=True, on_delete=models.SET_NULL, related_name='background_tasks')
    created_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='background_tasks_created')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'task_management_background_task'
        ordering = ['priority', 'available_at', 'created_at']
        indexes = [
            models.Index(fields=['queue_name', 'status', 'available_at']),
            models.Index(fields=['status', 'heartbeat_at']),
            models.Index(fields=['company', 'created_at']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['task_key', 'idempotency_key'],
                condition=Q(status__in=('pending', 'claimed', 'running', 'retrying')) & ~Q(idempotency_key=''),
                name='task_active_idempotency_unique',
            ),
        ]


class BackgroundTaskEvent(models.Model):
    EVENT_ENQUEUED = 'enqueued'
    EVENT_CLAIMED = 'claimed'
    EVENT_STARTED = 'started'
    EVENT_SUCCEEDED = 'succeeded'
    EVENT_FAILED = 'failed'
    EVENT_RETRY_SCHEDULED = 'retry_scheduled'
    EVENT_LOCK_RELEASED = 'lock_released'
    EVENT_CANCELLED = 'cancelled'
    EVENT_MANUALLY_RETRIED = 'manually_retried'
    EVENT_CHOICES = [(value, value.replace('_', ' ').title()) for value in (
        EVENT_ENQUEUED, EVENT_CLAIMED, EVENT_STARTED, EVENT_SUCCEEDED, EVENT_FAILED,
        EVENT_RETRY_SCHEDULED, EVENT_LOCK_RELEASED, EVENT_CANCELLED, EVENT_MANUALLY_RETRIED,
    )]

    task = models.ForeignKey(BackgroundTask, on_delete=models.CASCADE, related_name='events')
    event_type = models.CharField(max_length=50, choices=EVENT_CHOICES)
    worker_id = models.CharField(max_length=255, blank=True)
    attempt_number = models.PositiveIntegerField(default=0)
    message = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True)
    traceback = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'task_management_background_task_event'
        ordering = ['created_at', 'id']


class BackgroundTaskSchedule(models.Model):
    TYPE_INTERVAL = 'interval'
    TYPE_ONE_OFF = 'one_off'
    TYPE_CHOICES = [(TYPE_INTERVAL, 'Interval'), (TYPE_ONE_OFF, 'One Off')]

    name = models.CharField(max_length=255, unique=True)
    task_key = models.CharField(max_length=150)
    handler_version = models.PositiveIntegerField(default=1)
    queue_name = models.CharField(max_length=100)
    payload = models.JSONField(default=dict)
    schedule_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    interval_seconds = models.PositiveIntegerField(null=True, blank=True)
    run_at = models.DateTimeField(null=True, blank=True)
    cron_expression = models.CharField(max_length=100, blank=True)
    timezone = models.CharField(max_length=64, default=settings.TIME_ZONE)
    is_active = models.BooleanField(default=True, db_index=True)
    next_run_at = models.DateTimeField(null=True, blank=True, db_index=True)
    last_enqueued_at = models.DateTimeField(null=True, blank=True)
    last_run_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    max_concurrent_enqueues = models.PositiveIntegerField(default=1)
    dedupe_window_seconds = models.PositiveIntegerField(default=0)
    company = models.ForeignKey('tenancy.Company', null=True, blank=True, on_delete=models.SET_NULL, related_name='background_task_schedules')
    created_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='background_task_schedules_created')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'task_management_background_task_schedule'
        ordering = ['next_run_at', 'name']
        indexes = [models.Index(fields=['is_active', 'next_run_at'])]
