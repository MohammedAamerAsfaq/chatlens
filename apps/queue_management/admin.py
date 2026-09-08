from django.contrib import admin

from .models import BackgroundWorker, QueueDefinition


@admin.register(QueueDefinition)
class QueueDefinitionAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_enabled', 'is_paused', 'max_concurrency', 'poll_interval_seconds', 'lock_timeout_seconds']
    list_editable = ['is_enabled', 'is_paused', 'max_concurrency', 'poll_interval_seconds', 'lock_timeout_seconds']


@admin.register(BackgroundWorker)
class BackgroundWorkerAdmin(admin.ModelAdmin):
    list_display = ['worker_id', 'status', 'hostname', 'process_id', 'queue_names', 'last_heartbeat_at']
    list_filter = ['status']
    search_fields = ['worker_id', 'hostname']
    readonly_fields = [field.name for field in BackgroundWorker._meta.fields]
