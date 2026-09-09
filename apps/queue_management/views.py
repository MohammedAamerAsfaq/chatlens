from django.db.models import Count, Min, Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response

from apps.task_management.models import BackgroundTask, BackgroundTaskSchedule
from .models import BackgroundWorker, QueueDefinition
from .runtime_settings import get_task_runtime_settings


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


@api_view(['GET', 'PATCH'])
@permission_classes([IsAdminUser])
def queue_settings(request):
    def data():
        runtime = get_task_runtime_settings()
        return {'queues': [
            {
                'name': queue.name, 'display_name': queue.display_name,
                'max_concurrency': queue.max_concurrency,
                'task_timeout_seconds': queue.task_timeout_seconds,
            }
            for queue in QueueDefinition.objects.all()
        ], 'runtime': {
            'automation_mode': runtime.automation_mode, 'embedding_mode': runtime.embedding_mode,
            'classification_mode': runtime.classification_mode, 'recovery_mode': runtime.recovery_mode,
            'worker_heartbeat_seconds': runtime.worker_heartbeat_seconds,
            'scheduler_interval_seconds': runtime.scheduler_interval_seconds,
        }}

    if request.method == 'GET':
        return Response(data())

    updates = request.data.get('queues')
    if not isinstance(updates, list):
        return Response({'detail': 'queues must be a list.'}, status=400)
    for item in updates:
        try:
            queue = QueueDefinition.objects.get(name=item['name'])
            concurrency = int(item['max_concurrency'])
            timeout_seconds = int(item['task_timeout_seconds'])
        except (KeyError, TypeError, ValueError, QueueDefinition.DoesNotExist):
            return Response({'detail': 'Each queue needs a valid name, concurrency, and timeout.'}, status=400)
        if not 1 <= concurrency <= 64 or not 30 <= timeout_seconds <= 7200:
            return Response({'detail': 'Concurrency must be 1-64 and timeout must be 30-7200 seconds.'}, status=400)
        queue.max_concurrency = concurrency
        queue.task_timeout_seconds = timeout_seconds
        queue.save(update_fields=['max_concurrency', 'task_timeout_seconds', 'updated_at'])
    runtime_data = request.data.get('runtime')
    if runtime_data is not None:
        runtime = get_task_runtime_settings()
        for field in ('automation_mode', 'embedding_mode', 'classification_mode', 'recovery_mode'):
            value = runtime_data.get(field)
            if value not in {'thread', 'db_queue'}:
                return Response({'detail': f'{field} must be thread or db_queue.'}, status=400)
            setattr(runtime, field, value)
        for field in ('worker_heartbeat_seconds', 'scheduler_interval_seconds'):
            value = int(runtime_data.get(field, 0))
            if not 1 <= value <= 300:
                return Response({'detail': f'{field} must be 1-300 seconds.'}, status=400)
            setattr(runtime, field, value)
        runtime.save()
    return Response(data())


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
