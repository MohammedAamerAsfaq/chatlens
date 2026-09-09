from django.urls import path
from .views import queue_overview, queue_settings, task_detail, task_list

urlpatterns = [
    path('task-queue/overview/', queue_overview, name='task-queue-overview'),
    path('task-queue/settings/', queue_settings, name='task-queue-settings'),
    path('task-queue/tasks/', task_list, name='task-queue-tasks'),
    path('task-queue/tasks/<int:task_id>/', task_detail, name='task-queue-task-detail'),
]
