"""Durable transport for normalized WhatsApp history batches."""
import hashlib
import json

from apps.task_management.models import BackgroundTask


def _fallback_batch_key(account_id, messages, is_latest, received):
    body = json.dumps(
        {
            'account_id': account_id,
            'messages': messages,
            'is_latest': bool(is_latest),
            'received': received,
        },
        sort_keys=True,
        separators=(',', ':'),
        default=str,
    )
    return hashlib.sha256(body.encode('utf-8')).hexdigest()


def enqueue_history_batch(account, data):
    from apps.queue_management.services import enqueue_task
    from apps.tenancy.services.access import company_for_whatsapp_account

    messages = data.get('messages', [])
    transport_key = str(data.get('transport_key') or '').strip()
    batch_key = transport_key or _fallback_batch_key(
        account.pk, messages, data.get('is_latest'), data.get('received'),
    )
    idempotency_key = f'whatsapp-history:{account.pk}:{batch_key}'[:255]
    existing = BackgroundTask.objects.filter(
        task_key='whatsapp.persist_history_batch',
        idempotency_key=idempotency_key,
    ).exclude(
        status__in=[BackgroundTask.STATUS_FAILED, BackgroundTask.STATUS_CANCELLED],
    ).order_by('-created_at').first()
    if existing:
        return existing, False

    task = enqueue_task(
        task_key='whatsapp.persist_history_batch',
        payload={
            'version': 1,
            'account_id': account.pk,
            'messages': messages,
            'is_latest': bool(data.get('is_latest')),
            'received': data.get('received', len(messages)),
            'batch_key': batch_key,
        },
        idempotency_key=idempotency_key,
        correlation_id=f'whatsapp-history:{account.pk}:{batch_key}'[:255],
        company=company_for_whatsapp_account(account),
    )
    return task, True
