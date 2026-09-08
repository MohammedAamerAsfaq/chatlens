from django.contrib import admin

from .models import BackgroundTask, BackgroundTaskEvent, BackgroundTaskSchedule


class BackgroundTaskEventInline(admin.TabularInline):
    model = BackgroundTaskEvent
    extra = 0
    can_delete = False
    readonly_fields = [field.name for field in BackgroundTaskEvent._meta.fields]


@admin.register(BackgroundTask)
class BackgroundTaskAdmin(admin.ModelAdmin):
    list_display = ['id', 'task_key', 'queue_name', 'status', 'priority', 'attempts', 'max_attempts', 'created_at']
    list_filter = ['queue_name', 'status', 'company']
    search_fields = ['task_key', 'idempotency_key', 'correlation_id', 'locked_by']
    readonly_fields = [field.name for field in BackgroundTask._meta.fields]
    inlines = [BackgroundTaskEventInline]


@admin.register(BackgroundTaskSchedule)
class BackgroundTaskScheduleAdmin(admin.ModelAdmin):
    list_display = ['name', 'task_key', 'queue_name', 'schedule_type', 'is_active', 'next_run_at']
    list_filter = ['schedule_type', 'is_active', 'queue_name']
    search_fields = ['name', 'task_key']
