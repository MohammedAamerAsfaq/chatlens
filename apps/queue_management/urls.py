from django.urls import path
from .views import queue_overview, task_detail, task_list

urlpatterns = [
    path('task-queue/overview/', queue_overview, name='task-queue-overview'),
    path('task-queue/tasks/', task_list, name='task-queue-tasks'),
    path('task-queue/tasks/<int:task_id>/', task_detail, name='task-queue-task-detail'),
]
