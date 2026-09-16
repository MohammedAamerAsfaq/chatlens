"""Durable task handlers for the WhatsApp ingestion pipeline."""
from apps.task_management.registry import task_handler, UnsupportedTaskPayload


def validate_history_batch(payload):
    if not isinstance(payload, dict) or payload.get('version') != 1:
        raise UnsupportedTaskPayload('Payload version 1 is required.')
    if not isinstance(payload.get('account_id'), int) or payload['account_id'] <= 0:
        raise UnsupportedTaskPayload('account_id must be a positive integer.')
    messages = payload.get('messages')
    if not isinstance(messages, list) or len(messages) > 100:
        raise UnsupportedTaskPayload('messages must be a list with at most 100 items.')
    if any(not isinstance(message, dict) for message in messages):
        raise UnsupportedTaskPayload('Every message must be an object.')
    if not isinstance(payload.get('batch_key'), str) or not payload['batch_key']:
        raise UnsupportedTaskPayload('batch_key is required.')


def validate_history_embedding_dispatch(payload):
    if not isinstance(payload, dict) or payload.get('version') != 1:
        raise UnsupportedTaskPayload('Payload version 1 is required.')
    message_ids = payload.get('message_ids')
    if not isinstance(message_ids, list) or len(message_ids) > 100:
        raise UnsupportedTaskPayload('message_ids must be a list with at most 100 items.')
    if any(not isinstance(value, int) or value <= 0 for value in message_ids):
        raise UnsupportedTaskPayload('message_ids must contain positive integers.')


def validate_live_message(payload):
    if not isinstance(payload, dict) or payload.get('version') != 1:
        raise UnsupportedTaskPayload('Payload version 1 is required.')
    if not isinstance(payload.get('account_id'), int) or payload['account_id'] <= 0:
        raise UnsupportedTaskPayload('account_id must be a positive integer.')
    message = payload.get('message')
    required = ('worker_session_id', 'provider_message_id', 'chat_id', 'direction', 'message_time')
    if not isinstance(message, dict) or any(not message.get(field) for field in required):
        raise UnsupportedTaskPayload('message is missing required live-ingestion fields.')
    if str(message['worker_session_id']) != str(payload['account_id']):
        raise UnsupportedTaskPayload('message worker_session_id must match account_id.')


@task_handler(
    key='whatsapp.persist_history_batch',
    default_queue='history_ingestion',
    payload_validator=validate_history_batch,
)
def persist_history_batch(payload, context):
    from django.db import connection, transaction

    from apps.queue_management.services import enqueue_task
    from apps.task_management.models import BackgroundTask
    from apps.whatsapp_bridge.services.ingestion_service import IngestionService

    with transaction.atomic():
        # Serialize batches per account while allowing separate accounts to run concurrently.
        with connection.cursor() as cursor:
            cursor.execute('SELECT pg_advisory_xact_lock(%s, %s)', [9017, payload['account_id']])
        result = IngestionService().ingest_batch(
            payload['account_id'],
            payload['messages'],
            is_latest=bool(payload.get('is_latest')),
            received=payload.get('received'),
            dispatch_downstream=False,
        )
        message_ids = result.pop('message_ids', [])
        post_task_id = None
        if message_ids:
            idempotency_key = f'history-embedding-dispatch:{context.task_id}'
            post_task = BackgroundTask.objects.filter(
                task_key='whatsapp.dispatch_history_embeddings',
                idempotency_key=idempotency_key,
            ).exclude(status__in=[BackgroundTask.STATUS_FAILED, BackgroundTask.STATUS_CANCELLED]).first()
            if post_task is None:
                post_task = enqueue_task(
                    task_key='whatsapp.dispatch_history_embeddings',
                    payload={
                        'version': 1,
                        'message_ids': message_ids,
                        'sync_log_id': result.get('sync_log_id'),
                    },
                    idempotency_key=idempotency_key,
                    correlation_id=context.correlation_id,
                )
            post_task_id = post_task.pk
    return {**result, 'history_embedding_task_id': post_task_id}


@task_handler(
    key='whatsapp.dispatch_history_embeddings',
    default_queue='history_embedding_dispatch',
    payload_validator=validate_history_embedding_dispatch,
)
def dispatch_history_embeddings(payload, context):
    from apps.queue_management.services import enqueue_task
    from apps.tenancy.services.access import company_for_message
    from apps.whatsapp_bridge.models import WhatsAppMessage

    messages = WhatsAppMessage.objects.filter(
        pk__in=payload['message_ids'],
        embedding__isnull=True,
    ).select_related('account__communication_account__company')
    enqueued = 0
    for message in messages:
        if not message.message_text:
            continue
        enqueue_task(
            task_key='whatsapp.embed_message',
            payload={'version': 1, 'object_id': message.pk},
            idempotency_key=f'embedding:message:{message.pk}',
            correlation_id=f'whatsapp-message:{message.pk}',
            company=company_for_message(message),
        )
        enqueued += 1
    return {'message_count': messages.count(), 'embedding_tasks_enqueued': enqueued}


@task_handler(
    key='whatsapp.persist_live_message',
    default_queue='live_ingestion',
    payload_validator=validate_live_message,
)
def persist_live_message(payload, context):
    from django.db import connection, transaction

    from apps.whatsapp_bridge.services.ingestion_service import (
        IngestionService, dispatch_queued_live_message,
    )

    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute('SELECT pg_advisory_xact_lock(%s, %s)', [9018, payload['account_id']])
        message = IngestionService().ingest_message(
            payload['message'],
            dispatch_downstream=False,
        )

    dispatch_queued_live_message(message.pk)
    return {'message_id': message.pk, 'downstream_dispatched': True}
