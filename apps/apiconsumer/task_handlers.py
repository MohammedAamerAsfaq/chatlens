import hashlib
import hmac
import json

import requests
from django.core.serializers.json import DjangoJSONEncoder

from apps.task_management.models import BackgroundTask
from apps.task_management.registry import UnsupportedTaskPayload, task_handler

WEBHOOK_TIMEOUT_SECONDS = 5


def validate_webhook_delivery_payload(payload):
    if not isinstance(payload, dict) or payload.get('version') != 1:
        raise UnsupportedTaskPayload('Payload version 1 is required.')
    if not isinstance(payload.get('subscription_id'), int) or payload['subscription_id'] <= 0:
        raise UnsupportedTaskPayload('subscription_id must be a positive integer.')
    if not isinstance(payload.get('event_type'), str) or not payload['event_type']:
        raise UnsupportedTaskPayload('event_type is required.')
    if not isinstance(payload.get('event_payload'), dict):
        raise UnsupportedTaskPayload('event_payload must be an object.')


@task_handler(
    key='apiconsumer.deliver_webhook', default_queue='apiconsumer_webhooks',
    payload_validator=validate_webhook_delivery_payload, retry_safe=True,
)
def deliver_webhook(payload, context):
    from .models import WebhookDeliveryAttempt, WebhookSubscription

    subscription = WebhookSubscription.objects.filter(
        pk=payload['subscription_id'], is_active=True,
    ).first()
    if not subscription:
        return {'skipped': 'subscription_inactive_or_missing'}

    task = BackgroundTask.objects.get(pk=context.task_id)
    body = json.dumps(
        {'event': payload['event_type'], 'data': payload['event_payload']},
        cls=DjangoJSONEncoder,
    ).encode('utf-8')
    signature = hmac.new(subscription.secret.encode('utf-8'), body, hashlib.sha256).hexdigest()

    response_status = None
    response_snippet = ''
    succeeded = False
    try:
        response = requests.post(
            subscription.target_url,
            data=body,
            headers={
                'Content-Type': 'application/json',
                'X-ChatLens-Event': payload['event_type'],
                'X-ChatLens-Signature': signature,
            },
            timeout=WEBHOOK_TIMEOUT_SECONDS,
        )
        response_status = response.status_code
        response_snippet = response.text[:500]
        succeeded = 200 <= response.status_code < 300
    finally:
        WebhookDeliveryAttempt.objects.create(
            subscription=subscription, event_type=payload['event_type'],
            payload=payload['event_payload'], attempt_number=task.attempts,
            response_status=response_status, response_body_snippet=response_snippet,
            succeeded=succeeded,
        )

    if not succeeded:
        raise RuntimeError(f'Webhook delivery failed with status {response_status}.')
    return {'status': response_status}
