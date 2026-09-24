import uuid
import json

from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.utils import timezone

from apps.queue_management.services import enqueue_task
from apps.whatsapp_bridge.models import OutboundMessage
from apps.whatsapp_bridge.services.destination_policy import classify_destination
from .events import record_event
from .policy import evaluate_outbound, new_chat_snapshot, settings_snapshot


@transaction.atomic
def create_outbound_message(*, account, destination_jid, text, requested_by, asset=None,
                            idempotency_key=None, confirm_new_chat=False):
    company = account.communication_account.company
    if asset and asset.company_id != company.pk:
        raise ValueError('asset_company_mismatch')
    key = str(idempotency_key or uuid.uuid4())[:255]
    existing = OutboundMessage.objects.filter(company=company, idempotency_key=key).first()
    if existing:
        return existing, False

    new_chat = new_chat_snapshot(account, destination_jid)
    if new_chat['state'] == 'likely_new' and not confirm_new_chat:
        raise ValueError('likely_new_chat_confirmation_required')

    correlation_id = f'whatsapp-outbound:{uuid.uuid4().hex}'
    content_type = 'image' if asset else 'text'
    content_payload = {'text': text}
    if asset:
        content_payload = {
            'asset_id': asset.pk,
            'caption': text,
            'mime_type': asset.mime_type,
            'size_bytes': asset.size_bytes,
            'sha256': asset.sha256,
        }
    message = OutboundMessage.objects.create(
        company=company,
        whatsapp_account=account,
        destination_jid=destination_jid,
        canonical_recipient_key=destination_jid.lower(),
        destination_type=classify_destination(destination_jid),
        content_type=content_type,
        content_payload=content_payload,
        asset=asset,
        idempotency_key=key,
        correlation_id=correlation_id,
        new_chat_state=new_chat['state'],
        new_chat_confidence=new_chat['confidence'],
        new_chat_reason=new_chat['reason'],
        settings_snapshot=settings_snapshot(account),
        requested_by=requested_by,
        eligible_at=timezone.now(),
    )
    record_event(message, 'requested', actor=f'user:{requested_by.pk}')
    permission = json.loads(json.dumps(evaluate_outbound(message), cls=DjangoJSONEncoder))
    message.permission_snapshot = permission
    message.destination_type = permission['destination_type']
    if not permission['allowed']:
        message.status = OutboundMessage.STATUS_BLOCKED
        message.status_reason = permission['reason']
        message.finished_at = timezone.now()
        message.save(update_fields=[
            'permission_snapshot', 'destination_type', 'status', 'status_reason',
            'finished_at', 'updated_at',
        ])
        record_event(message, 'preflight_blocked', actor=f'user:{requested_by.pk}', metadata=permission)
        return message, True
    message.save(update_fields=['permission_snapshot', 'destination_type', 'updated_at'])
    record_event(message, 'preflight_passed', actor=f'user:{requested_by.pk}', metadata=permission)
    task = enqueue_task(
        task_key='whatsapp.send_message',
        payload={'version': 1, 'outbound_message_id': message.pk},
        queue_name='outbound',
        idempotency_key=f'outbound:{message.pk}',
        correlation_id=correlation_id,
        company=company,
        created_by=requested_by,
    )
    record_event(message, 'queued', metadata={'task_id': task.pk})
    return message, True
