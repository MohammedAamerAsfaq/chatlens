from django.utils import timezone

from apps.task_management.models import BackgroundTask
from apps.task_management.registry import UnsupportedTaskPayload, task_handler


def validate_geography_sync_payload(payload):
    if not isinstance(payload, dict) or payload.get('version') != 1:
        raise UnsupportedTaskPayload('Payload version 1 is required.')
    if not isinstance(payload.get('connection_id'), int) or payload['connection_id'] <= 0:
        raise UnsupportedTaskPayload('connection_id must be a positive integer.')
    if not isinstance(payload.get('run_id'), str) or not payload['run_id']:
        raise UnsupportedTaskPayload('run_id is required.')
    code = payload.get('country_code')
    if not isinstance(code, str) or len(code) != 2:
        raise UnsupportedTaskPayload('country_code must be an ISO alpha-2 code.')


@task_handler(
    key='integrations.sync_geography', default_queue='integrations',
    payload_validator=validate_geography_sync_payload, retry_safe=True,
)
def sync_geography(payload, context):
    from apps.integrations.models import IntegrationConnection, IntegrationSyncRun
    from apps.integrations.services.geography_sync import sync_country

    task = BackgroundTask.objects.get(pk=context.task_id)
    run = IntegrationSyncRun.objects.select_related('connection').get(pk=payload['run_id'])
    if run.background_task_id != task.pk or run.connection_id != payload['connection_id']:
        raise ValueError('Integration sync run does not match the executing task.')
    connection = run.connection
    if connection.provider != IntegrationConnection.PROVIDER_GEONAMES or not connection.is_enabled:
        raise ValueError('GeoNames connection is not enabled.')
    run.status = IntegrationSyncRun.STATUS_RUNNING
    run.started_at = timezone.now()
    run.save(update_fields=['status', 'started_at'])
    try:
        counters = sync_country(connection, payload['country_code'])
    except Exception as exc:
        now = timezone.now()
        run.status = IntegrationSyncRun.STATUS_FAILED
        run.error = str(exc)
        run.finished_at = now
        run.save(update_fields=['status', 'error', 'finished_at'])
        connection.status = IntegrationConnection.STATUS_ERROR
        connection.last_error = str(exc)
        connection.last_checked_at = now
        connection.save(update_fields=['status', 'last_error', 'last_checked_at', 'updated_at'])
        raise
    now = timezone.now()
    run.status = IntegrationSyncRun.STATUS_SUCCEEDED
    run.counters = counters
    run.finished_at = now
    run.save(update_fields=['status', 'counters', 'finished_at'])
    connection.status = IntegrationConnection.STATUS_READY
    connection.last_error = ''
    connection.last_checked_at = now
    connection.last_successful_sync_at = now
    connection.save(update_fields=[
        'status', 'last_error', 'last_checked_at', 'last_successful_sync_at', 'updated_at',
    ])
    return counters
