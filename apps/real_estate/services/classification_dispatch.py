from apps.real_estate.models import RealEstateParseLog


def dispatch_real_estate_classification(message, company, skip_reason=None):
    status = RealEstateParseLog.STATUS_SKIPPED if skip_reason else RealEstateParseLog.STATUS_GATE_PENDING
    parse_log, _ = RealEstateParseLog.objects.update_or_create(
        message=message,
        defaults={
            'company': company,
            'account': message.account,
            'chat': message.chat,
            'status': status,
            'skip_reason': skip_reason or '',
            'error': '',
        },
    )
    if skip_reason:
        return None

    from apps.queue_management.services import enqueue_task

    return enqueue_task(
        task_key='real_estate.gate_message',
        payload={'version': 1, 'company_id': company.pk, 'message_id': message.pk},
        idempotency_key=f'real-estate-gate:{message.pk}',
        correlation_id=f'whatsapp-message:{message.pk}',
        company=company,
    )


def enqueue_extraction(message, company, parse_log):
    from apps.queue_management.services import enqueue_task

    parse_log.status = RealEstateParseLog.STATUS_EXTRACT_PENDING
    parse_log.save(update_fields=['status', 'updated_at'])
    return enqueue_task(
        task_key='real_estate.extract_message',
        payload={'version': 1, 'company_id': company.pk, 'message_id': message.pk},
        idempotency_key=f'real-estate-extract:{message.pk}',
        correlation_id=f'whatsapp-message:{message.pk}',
        company=company,
    )

