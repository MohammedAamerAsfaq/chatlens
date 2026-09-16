"""Durable transport for one normalized live WhatsApp message."""
from apps.task_management.models import BackgroundTask


def enqueue_live_message(account, payload):
    from apps.queue_management.services import enqueue_task
    from apps.tenancy.services.access import company_for_whatsapp_account

    transport_key = str(payload.get('transport_key') or '').strip()
    provider_id = str(payload['provider_message_id'])
    message_key = transport_key or provider_id
    idempotency_key = f'whatsapp-live:{account.pk}:{message_key}'[:255]
    existing = BackgroundTask.objects.filter(
        task_key='whatsapp.persist_live_message',
        idempotency_key=idempotency_key,
    ).exclude(
        status__in=[BackgroundTask.STATUS_FAILED, BackgroundTask.STATUS_CANCELLED],
    ).order_by('-created_at').first()
    if existing:
        return existing, False

    task_payload = dict(payload)
    task_payload.pop('transport_key', None)
    task = enqueue_task(
        task_key='whatsapp.persist_live_message',
        payload={'version': 1, 'account_id': account.pk, 'message': task_payload},
        idempotency_key=idempotency_key,
        correlation_id=f'whatsapp-live:{account.pk}:{provider_id}'[:255],
        company=company_for_whatsapp_account(account),
    )
    return task, True
