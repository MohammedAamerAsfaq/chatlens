from django.db.models import Count, Min, Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.task_management.models import BackgroundTask, BackgroundTaskSchedule
from .models import BackgroundWorker, QueueDefinition


def _visible_tasks(user):
    tasks = BackgroundTask.objects.select_related('company', 'created_by')
    if user.is_superuser:
        return tasks
    from apps.tenancy.services.access import default_company_for_user
    company = default_company_for_user(user)
    return tasks.filter(Q(company=company) | Q(company__isnull=True)) if company else tasks.filter(company__isnull=True)


def _task_data(task, include_events=False):
    data = {
        'id': task.pk, 'task_key': task.task_key, 'handler_version': task.handler_version,
        'queue_name': task.queue_name, 'status': task.status, 'priority': task.priority,
        'payload': task.payload, 'result': task.result, 'idempotency_key': task.idempotency_key,
        'correlation_id': task.correlation_id, 'attempts': task.attempts, 'max_attempts': task.max_attempts,
        'available_at': task.available_at, 'locked_at': task.locked_at, 'locked_by': task.locked_by,
        'heartbeat_at': task.heartbeat_at, 'started_at': task.started_at, 'finished_at': task.finished_at,
        'last_error': task.last_error, 'last_traceback': task.last_traceback,
        'company_id': task.company_id, 'company_name': task.company.name if task.company_id else '',
        'created_at': task.created_at, 'updated_at': task.updated_at,
    }
    if include_events:
        data['events'] = [{
            'id': event.pk, 'event_type': event.event_type, 'worker_id': event.worker_id,
            'attempt_number': event.attempt_number, 'message': event.message,
            'metadata': event.metadata, 'error': event.error, 'traceback': event.traceback,
            'created_at': event.created_at,
        } for event in task.events.all()]
    return data


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def queue_overview(request):
    now = timezone.now()
    visible_tasks = _visible_tasks(request.user)
    if request.user.is_superuser:
        visible_schedules = BackgroundTaskSchedule.objects.all()
    else:
        from apps.tenancy.services.access import default_company_for_user
        company = default_company_for_user(request.user)
        visible_schedules = BackgroundTaskSchedule.objects.filter(Q(company=company) | Q(company__isnull=True)) if company else BackgroundTaskSchedule.objects.filter(company__isnull=True)
    queues = []
    for queue in QueueDefinition.objects.all():
        tasks = visible_tasks.filter(queue_name=queue.name)
        status_counts = {row['status']: row['count'] for row in tasks.values('status').annotate(count=Count('id'))}
        oldest = tasks.filter(status=BackgroundTask.STATUS_PENDING).aggregate(value=Min('created_at'))['value']
        completed = list(tasks.filter(status=BackgroundTask.STATUS_SUCCEEDED, started_at__isnull=False, finished_at__isnull=False).values_list('started_at', 'finished_at')[:500])
        average_runtime_seconds = (
            sum((finished - started).total_seconds() for started, finished in completed) / len(completed)
            if completed else None
        )
        queues.append({
            'name': queue.name, 'display_name': queue.display_name, 'is_enabled': queue.is_enabled, 'is_paused': queue.is_paused,
            'counts': status_counts, 'oldest_pending_age_seconds': int((now - oldest).total_seconds()) if oldest else None,
            'average_runtime_seconds': average_runtime_seconds,
        })
    return Response({
        'queues': queues,
        'workers': list(BackgroundWorker.objects.values('worker_id', 'status', 'hostname', 'process_id', 'queue_names', 'started_at', 'last_heartbeat_at')),
        'schedules': list(visible_schedules.values('id', 'name', 'task_key', 'queue_name', 'is_active', 'next_run_at', 'last_enqueued_at', 'last_error')),
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def task_list(request):
    tasks = _visible_tasks(request.user)
    params = request.query_params
    if queue_name := params.get('queue'):
        tasks = tasks.filter(queue_name=queue_name)
    if status := params.get('status'):
        tasks = tasks.filter(status=status)
    if task_key := params.get('task_key'):
        tasks = tasks.filter(task_key__icontains=task_key)
    if worker_id := params.get('worker'):
        tasks = tasks.filter(locked_by__icontains=worker_id)
    if correlation_id := params.get('correlation_id'):
        tasks = tasks.filter(correlation_id__icontains=correlation_id)
    if date_from := parse_datetime(params.get('date_from', '')):
        tasks = tasks.filter(created_at__gte=date_from)
    if date_to := parse_datetime(params.get('date_to', '')):
        tasks = tasks.filter(created_at__lte=date_to)
    try:
        limit = max(1, min(int(params.get('limit', 100)), 500))
    except ValueError:
        limit = 100
    rows = list(tasks.order_by('-created_at')[:limit])
    return Response({'count': tasks.count(), 'results': [_task_data(task) for task in rows]})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def task_detail(request, task_id):
    task = _visible_tasks(request.user).prefetch_related('events').filter(pk=task_id).first()
    if task is None:
        return Response({'detail': 'Not found.'}, status=404)
    return Response(_task_data(task, include_events=True))
