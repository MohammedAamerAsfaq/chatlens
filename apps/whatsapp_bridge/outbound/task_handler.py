import json
import requests

from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.utils import timezone

from apps.queue_management.services import TaskDeferred
from apps.whatsapp_bridge.models import OutboundMessage
from .events import record_event
from .policy import evaluate_outbound, settings_snapshot
from .throttle import OutboundDeferred, release, reserve
from .transport import send_to_worker


def _finish(message, status, reason='', error='', response=None):
    message.status = status
    message.status_reason = reason
    message.last_error_code = reason if error else ''
    message.last_error = error
    message.provider_response = response or {}
    message.finished_at = timezone.now()
    message.save(update_fields=[
        'status', 'status_reason', 'last_error_code', 'last_error',
        'provider_response', 'finished_at', 'updated_at',
    ])


def _json_safe(value):
    return json.loads(json.dumps(value, cls=DjangoJSONEncoder))


def execute_outbound_message(outbound_message_id, context):
    with transaction.atomic():
        message = (
            OutboundMessage.objects.select_for_update()
            .select_related('whatsapp_account')
            .get(pk=outbound_message_id)
        )
        if message.status in OutboundMessage.TERMINAL_STATUSES:
            return {'outbound_message_id': message.pk, 'status': message.status, 'skipped': True}
        message.attempt_count += 1
        message.settings_snapshot = settings_snapshot(message.whatsapp_account)
        message.save(update_fields=['attempt_count', 'settings_snapshot', 'updated_at'])

    permission = _json_safe(evaluate_outbound(message))
    message.permission_snapshot = permission
    message.destination_type = permission['destination_type']
    if not permission['allowed']:
        _finish(message, OutboundMessage.STATUS_BLOCKED, permission['reason'])
        record_event(message, 'preflight_blocked', actor=context.worker_id, metadata=permission)
        return {'outbound_message_id': message.pk, 'status': message.status, 'reason': permission['reason']}
    message.save(update_fields=['permission_snapshot', 'destination_type', 'updated_at'])
    record_event(message, 'preflight_passed', actor=context.worker_id, metadata=permission)

    try:
        dispatch_started_at = reserve(message)
    except OutboundDeferred as exc:
        message.status = OutboundMessage.STATUS_DEFERRED
        message.status_reason = exc.reason
        message.eligible_at = exc.available_at
        message.save(update_fields=['status', 'status_reason', 'eligible_at', 'updated_at'])
        event_type = 'concurrency_deferred' if 'concurrency' in exc.reason else 'rate_limited'
        record_event(message, event_type, actor=context.worker_id, metadata={'available_at': exc.available_at.isoformat()})
        raise TaskDeferred(exc.available_at, exc.reason, {'outbound_message_id': message.pk})

    message.status = OutboundMessage.STATUS_SENDING
    message.status_reason = ''
    message.dispatch_started_at = dispatch_started_at
    message.save(update_fields=['status', 'status_reason', 'dispatch_started_at', 'updated_at'])
    record_event(message, 'dispatch_started', actor=context.worker_id)
    try:
        status_code, response = send_to_worker(message)
        if status_code == 200 and response.get('accepted'):
            message.status = OutboundMessage.STATUS_SENT
            message.provider_accepted_at = timezone.now()
            message.finished_at = message.provider_accepted_at
            message.provider_response = response
            message.save(update_fields=[
                'status', 'provider_accepted_at', 'finished_at', 'provider_response', 'updated_at',
            ])
            record_event(message, 'provider_accepted', actor=context.worker_id, metadata=response)
        elif response.get('retryable') and not response.get('dispatch_started'):
            message.status = OutboundMessage.STATUS_DEFERRED
            message.status_reason = response.get('code', 'session_disconnected')
            message.provider_response = response
            message.save(update_fields=['status', 'status_reason', 'provider_response', 'updated_at'])
            record_event(message, 'failed', actor=context.worker_id, detail='Safe pre-dispatch retry.', metadata=response)
            raise RuntimeError(message.status_reason)
        elif response.get('outcome_unknown') or response.get('dispatch_started'):
            _finish(
                message, OutboundMessage.STATUS_UNKNOWN, 'dispatch_outcome_unknown',
                response.get('error', ''), response,
            )
            record_event(message, 'outcome_unknown', actor=context.worker_id, metadata=response)
        else:
            reason = response.get('code', 'provider_rejected')
            _finish(message, OutboundMessage.STATUS_FAILED, reason, response.get('error', ''), response)
            record_event(message, 'failed', actor=context.worker_id, metadata=response)
    except requests.RequestException as exc:
        _finish(message, OutboundMessage.STATUS_UNKNOWN, 'dispatch_outcome_unknown', str(exc))
        record_event(message, 'outcome_unknown', actor=context.worker_id, detail=str(exc))
    finally:
        release(message)

    return {'outbound_message_id': message.pk, 'status': message.status}
