from django.db import models


class QueueDefinition(models.Model):
    name = models.CharField(max_length=100, unique=True)
    display_name = models.CharField(max_length=150)
    is_enabled = models.BooleanField(default=True)
    is_paused = models.BooleanField(default=False)
    max_concurrency = models.PositiveIntegerField(default=1)
    poll_interval_seconds = models.PositiveIntegerField(default=2)
    lock_timeout_seconds = models.PositiveIntegerField(default=300)
    default_max_attempts = models.PositiveIntegerField(default=3)
    retry_backoff_base_seconds = models.PositiveIntegerField(default=15)
    retry_backoff_max_seconds = models.PositiveIntegerField(default=900)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'queue_management_queue_definition'
        ordering = ['name']


class BackgroundWorker(models.Model):
    STATUS_STARTING = 'starting'
    STATUS_RUNNING = 'running'
    STATUS_STOPPING = 'stopping'
    STATUS_STOPPED = 'stopped'
    STATUS_UNHEALTHY = 'unhealthy'
    STATUS_CHOICES = [(value, value.title()) for value in (
        STATUS_STARTING, STATUS_RUNNING, STATUS_STOPPING, STATUS_STOPPED, STATUS_UNHEALTHY,
    )]

    worker_id = models.CharField(max_length=255, unique=True)
    hostname = models.CharField(max_length=255)
    process_id = models.PositiveIntegerField()
    queue_names = models.JSONField(default=list)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_STARTING)
    version = models.CharField(max_length=100, blank=True)
    started_at = models.DateTimeField()
    last_heartbeat_at = models.DateTimeField()
    stopped_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'queue_management_background_worker'
        ordering = ['-last_heartbeat_at']
