import logging

from django.db import transaction

from .models import WebhookSubscription

logger = logging.getLogger(__name__)

OUTBOUND_WEBHOOK_EVENT_TYPES = {
    'provider_accepted', 'delivered', 'read', 'failed', 'preflight_blocked', 'outcome_unknown',
}


def _dispatch(callback, description):
    def run():
        try:
            callback()
        except Exception:
            logger.exception('Could not enqueue webhook delivery for %s.', description)
    transaction.on_commit(run)


def _enqueue_for_subscriptions(*, company, external_event_type, event_payload, correlation_id):
    from apps.queue_management.services import enqueue_task

    subscriptions = WebhookSubscription.objects.filter(
        company=company, is_active=True, event_types__contains=[external_event_type],
    )
    for subscription in subscriptions:
        enqueue_task(
            task_key='apiconsumer.deliver_webhook',
            payload={
                'version': 1, 'subscription_id': subscription.pk,
                'event_type': external_event_type, 'event_payload': event_payload,
            },
            queue_name='apiconsumer_webhooks',
            idempotency_key=f'webhook:{subscription.pk}:{correlation_id}',
            correlation_id=correlation_id,
            company=company,
        )


def enqueue_outbound_status_webhooks(outbound_message_event):
    if outbound_message_event.event_type not in OUTBOUND_WEBHOOK_EVENT_TYPES:
        return
    message = outbound_message_event.message
    company = message.company
    payload = {
        'outbound_message_id': message.pk,
        'status': message.status,
        'destination_jid': message.destination_jid,
        'provider_message_id': message.provider_message_id,
        'event_type': outbound_message_event.event_type,
    }
    _dispatch(lambda: _enqueue_for_subscriptions(
        company=company,
        external_event_type=WebhookSubscription.EVENT_OUTBOUND_STATUS_CHANGED,
        event_payload=payload,
        correlation_id=message.correlation_id,
    ), f'outbound message {message.pk}')


def enqueue_inbound_message_webhooks(message):
    # Webhook dispatch must never break message persistence, so tolerate a message-like
    # object that doesn't carry the full account/company relation (e.g. a lightweight stub).
    try:
        company = (
            message.account.communication_account.company
            if message.account.communication_account_id else None
        )
    except AttributeError:
        return
    if not company:
        return
    payload = {
        'message_id': message.pk,
        'chat_id': message.chat_id,
        'direction': message.direction,
        'message_type': message.message_type,
        'message_text': message.message_text,
        'sender_number': message.sender_number,
    }
    _dispatch(lambda: _enqueue_for_subscriptions(
        company=company,
        external_event_type=WebhookSubscription.EVENT_MESSAGE_INBOUND_RECEIVED,
        event_payload=payload,
        correlation_id=f'inbound-webhook:{message.pk}',
    ), f'inbound message {message.pk}')
