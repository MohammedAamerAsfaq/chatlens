def get_task_runtime_settings():
    from .models import TaskRuntimeSettings
    settings, _ = TaskRuntimeSettings.objects.get_or_create(pk=1)
    return settings
