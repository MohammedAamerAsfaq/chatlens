from django.conf import settings
from django.db import connections
from django.db.migrations.executor import MigrationExecutor
from django.db.models import Count, Min
from django.db.utils import DEFAULT_DB_ALIAS
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET

from apps.task_management.models import BackgroundTask, BackgroundTaskSchedule
from apps.tenancy.models import Company
from apps.whatsapp_bridge.models import WhatsAppAccount
from apps.whatsapp_bridge.views import _verify_internal_token
from .models import BackgroundWorker, QueueDefinition

# Matches the threshold behind the "Worker unknown" badge in apps/api/views.py.
HEARTBEAT_STALE_SECONDS = 90
RECENT_FAILURES_LIMIT = 20
ERROR_TRUNCATE_CHARS = 1000


def _is_stale(last_heartbeat_at, now):
    if not last_heartbeat_at:
        return True
    return (now - last_heartbeat_at).total_seconds() > HEARTBEAT_STALE_SECONDS


def _pending_migrations():
    executor = MigrationExecutor(connections[DEFAULT_DB_ALIAS])
    plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
    return [f'{migration.app_label}.{migration.name}' for migration, _backwards in plan]


def _companies():
    return [{
        'id': company.pk,
        'name': company.name,
        'slug': company.slug,
        'company_type': company.company_type,
        'is_active': company.is_active,
        'validity_status': company.validity_status,
    } for company in Company.objects.all()]


def _whatsapp_accounts(now):
    rows = WhatsAppAccount.objects.select_related('communication_account__company').values(
        'id', 'display_name', 'phone_number', 'session_status', 'connection_unhealthy',
        'connection_unhealthy_reason', 'last_connected_at', 'last_worker_heartbeat_at',
        'worker_session_id', 'outbound_sending_enabled',
        'communication_account__company_id', 'communication_account__company__name',
    )
    accounts = []
    for row in rows:
        accounts.append({
            'id': row['id'],
            'company_id': row['communication_account__company_id'],
            'company_name': row['communication_account__company__name'],
            'display_name': row['display_name'],
            'phone_number': row['phone_number'],
            'session_status': row['session_status'],
            'connection_unhealthy': row['connection_unhealthy'],
            'connection_unhealthy_reason': row['connection_unhealthy_reason'],
            'last_connected_at': row['last_connected_at'],
            'last_worker_heartbeat_at': row['last_worker_heartbeat_at'],
            'heartbeat_stale': _is_stale(row['last_worker_heartbeat_at'], now),
            'worker_session_id': row['worker_session_id'],
            'outbound_sending_enabled': row['outbound_sending_enabled'],
        })
    return accounts


def _workers(now):
    workers = []
    for worker in BackgroundWorker.objects.values(
        'worker_id', 'status', 'hostname', 'process_id', 'queue_names',
        'started_at', 'last_heartbeat_at',
    ):
        workers.append({
            **worker,
            'heartbeat_stale': _is_stale(worker['last_heartbeat_at'], now),
        })
    return workers


def _queues(now):
    tasks = BackgroundTask.objects.all()
    queues = []
    for queue in QueueDefinition.objects.all():
        queue_tasks = tasks.filter(queue_name=queue.name)
        status_counts = {
            row['status']: row['count']
            for row in queue_tasks.values('status').annotate(count=Count('id'))
        }
        oldest = queue_tasks.filter(status=BackgroundTask.STATUS_PENDING).aggregate(value=Min('created_at'))['value']
        completed = list(
            queue_tasks.filter(
                status=BackgroundTask.STATUS_SUCCEEDED, started_at__isnull=False, finished_at__isnull=False,
            ).values_list('started_at', 'finished_at')[:500]
        )
        average_runtime_seconds = (
            sum((finished - started).total_seconds() for started, finished in completed) / len(completed)
            if completed else None
        )
        queues.append({
            'name': queue.name,
            'display_name': queue.display_name,
            'is_enabled': queue.is_enabled,
            'is_paused': queue.is_paused,
            'counts': status_counts,
            'oldest_pending_age_seconds': int((now - oldest).total_seconds()) if oldest else None,
            'average_runtime_seconds': average_runtime_seconds,
        })
    return queues


def _schedules():
    return list(BackgroundTaskSchedule.objects.values(
        'id', 'name', 'task_key', 'queue_name', 'is_active',
        'next_run_at', 'last_enqueued_at', 'last_run_at', 'last_error',
    ))


def _recent_failures():
    rows = BackgroundTask.objects.filter(
        status=BackgroundTask.STATUS_FAILED,
    ).select_related('company').order_by('-finished_at')[:RECENT_FAILURES_LIMIT]
    return [{
        'id': task.pk,
        'task_key': task.task_key,
        'queue_name': task.queue_name,
        'company_id': task.company_id,
        'company_name': task.company.name if task.company_id else '',
        'attempts': task.attempts,
        'max_attempts': task.max_attempts,
        'last_error': (task.last_error or '')[:ERROR_TRUNCATE_CHARS],
        'finished_at': task.finished_at,
    } for task in rows]


@require_GET
def internal_diagnostics(request):
    """Read-only operational snapshot for remote troubleshooting.

    Deliberately global (every company, every queue) rather than scoped to a session
    user's active company - this is an ops tool behind the same shared secret the
    WhatsApp worker already uses for its own callbacks, not a tenant-facing endpoint.
    """
    if not _verify_internal_token(request):
        return JsonResponse({'detail': 'Invalid internal token.'}, status=401)

    now = timezone.now()
    return JsonResponse({
        'server_time': now,
        'debug': settings.DEBUG,
        'pending_migrations': _pending_migrations(),
        'companies': _companies(),
        'whatsapp_accounts': _whatsapp_accounts(now),
        'workers': _workers(now),
        'queues': _queues(now),
        'schedules': _schedules(),
        'recent_failures': _recent_failures(),
    })
