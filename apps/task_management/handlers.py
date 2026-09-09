"""Registered task handlers for non-embedding background domains."""
from .registry import (
    task_handler, validate_any_v1_payload, validate_recovery_payload,
    validate_automation_payload, validate_versioned_message_payload,
)


def _not_migrated(payload, context):
    raise RuntimeError('This task is registered but has not been migrated to durable execution yet.')


@task_handler(key='whatsapp.process_automation_rules', default_queue='automation', payload_validator=validate_automation_payload)
def process_automation_rules(payload, context):
    from apps.whatsapp_bridge.models import WhatsAppMessage
    from apps.trading.services.price_update_automation import check_automation_rules, process_automation_rule

    message = WhatsAppMessage.objects.select_related('account', 'chat', 'contact').get(pk=payload['message_id'])
    rule_id = payload.get('rule_id')
    if rule_id is None:
        # Compatibility for tasks already stored before the rule-aware payload.
        check_automation_rules(message)
        processed = True
    else:
        processed = process_automation_rule(message, rule_id)
    return {'message_id': message.pk, 'rule_id': rule_id, 'automation_processed': processed}


@task_handler(key='trading.classify_message_v1', default_queue='ai', payload_validator=validate_versioned_message_payload)
def classify_message_v1(payload, context):
    from apps.whatsapp_bridge.models import WhatsAppMessage
    from apps.trading.services.classification_service import classify_message
    message = WhatsAppMessage.objects.select_related('account', 'chat', 'contact').get(pk=payload['message_id'])
    classify_message(message)
    return {'message_id': message.pk, 'classified': True}


@task_handler(key='trading.classify_message', default_queue='ai', payload_validator=validate_versioned_message_payload)
def classify_message_task(payload, context):
    """Run the existing classification flow unchanged in a durable worker."""
    from apps.whatsapp_bridge.models import WhatsAppMessage
    from apps.trading.services.classification_service import classify_message

    message = WhatsAppMessage.objects.select_related('account', 'chat', 'contact').get(pk=payload['message_id'])
    classify_message(message)
    return {'message_id': message.pk, 'classified': True}


@task_handler(key='trading.classify_message_v2_pass1', default_queue='ai', payload_validator=validate_versioned_message_payload)
def classify_message_v2_pass1(payload, context):
    return _not_migrated(payload, context)


@task_handler(key='trading.classify_message_v2_pass2', default_queue='ai', payload_validator=validate_versioned_message_payload)
def classify_message_v2_pass2(payload, context):
    return _not_migrated(payload, context)


@task_handler(key='whatsapp.recover_unresolved_lid', default_queue='recovery', payload_validator=validate_recovery_payload)
def recover_unresolved_lid(payload, context):
    return _not_migrated(payload, context)


@task_handler(key='whatsapp.update_sync_log_metadata', default_queue='metadata', payload_validator=validate_any_v1_payload)
def update_sync_log_metadata(payload, context):
    return _not_migrated(payload, context)


@task_handler(key='whatsapp.replay_failed_metadata', default_queue='metadata', payload_validator=validate_any_v1_payload)
def replay_failed_metadata(payload, context):
    return _not_migrated(payload, context)


@task_handler(key='maintenance.reconcile_stale_v2_pass1', default_queue='default', payload_validator=validate_any_v1_payload)
def reconcile_stale_v2_pass1(payload, context):
    from apps.trading.services.classification_service import _reconcile_stale_pass1_logs
    return {'reconciled': _reconcile_stale_pass1_logs()}


@task_handler(key='reports.generate', default_queue='reports', payload_validator=validate_any_v1_payload, retry_safe=False)
def generate_report(payload, context):
    return _not_migrated(payload, context)
