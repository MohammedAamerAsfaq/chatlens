"""Durable-queue transport for classification work."""
from apps.queue_management.runtime_settings import get_task_runtime_settings


def uses_classification_queue() -> bool:
    """Return whether classification must run outside the ingestion process."""
    return get_task_runtime_settings().classification_mode == 'db_queue'


def enqueue_classification(message) -> bool:
    """Queue the current classification flow when durable mode is enabled."""
    if not uses_classification_queue():
        return False

    from apps.queue_management.services import enqueue_task
    from apps.tenancy.services.access import company_for_message
    from apps.trading.services.classification_service import (
        CLASSIFICATION_V2, effective_classification_version,
    )

    is_v2 = effective_classification_version(message.account) == CLASSIFICATION_V2
    enqueue_task(
        task_key='trading.classify_message_v2_pass1' if is_v2 else 'trading.classify_message',
        payload={'version': 1, 'message_id': message.pk},
        idempotency_key=(
            f'classification-v2-pass1:{message.pk}' if is_v2
            else f'classification:{message.pk}'
        ),
        correlation_id=f'whatsapp-message:{message.pk}',
        company=company_for_message(message),
    )
    return True
