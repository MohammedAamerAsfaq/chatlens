from django.urls import path
from .diagnostics_views import internal_diagnostics
from .diagnostics_messages_views import internal_diagnostics_messages, internal_diagnostics_trace
from .views import queue_overview, queue_settings, request_worker_stop, task_detail, task_list

urlpatterns = [
    path('task-queue/overview/', queue_overview, name='task-queue-overview'),
    path('task-queue/workers/<str:worker_id>/stop/', request_worker_stop, name='task-queue-worker-stop'),
    path('task-queue/settings/', queue_settings, name='task-queue-settings'),
    path('task-queue/tasks/', task_list, name='task-queue-tasks'),
    path('task-queue/tasks/<int:task_id>/', task_detail, name='task-queue-task-detail'),
    path('internal/diagnostics/', internal_diagnostics, name='internal-diagnostics'),
    path('internal/diagnostics/messages/', internal_diagnostics_messages, name='internal-diagnostics-messages'),
    path('internal/diagnostics/trace/', internal_diagnostics_trace, name='internal-diagnostics-trace'),
]
