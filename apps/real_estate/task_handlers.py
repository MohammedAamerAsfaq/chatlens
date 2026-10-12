from django.utils import timezone

from apps.task_management.models import BackgroundTask
from apps.task_management.registry import UnsupportedTaskPayload, task_handler


def validate_message_payload(payload):
    if not isinstance(payload, dict) or payload.get('version') != 1:
        raise UnsupportedTaskPayload('Payload version 1 is required.')
    for key in ('company_id', 'message_id'):
        if not isinstance(payload.get(key), int) or payload[key] <= 0:
            raise UnsupportedTaskPayload(f'{key} must be a positive integer.')


def validate_embedding_payload(payload):
    if not isinstance(payload, dict) or payload.get('version') != 1:
        raise UnsupportedTaskPayload('Payload version 1 is required.')
    for key in ('company_id', 'object_id'):
        if not isinstance(payload.get(key), int) or payload[key] <= 0:
            raise UnsupportedTaskPayload(f'{key} must be a positive integer.')


def _embed(kind, payload, context):
    from apps.real_estate.services.embedding_service import embed_real_estate

    task_company_id = BackgroundTask.objects.values_list('company_id', flat=True).get(pk=context.task_id)
    if task_company_id != payload['company_id']:
        raise ValueError('Task company does not match embedding payload company.')
    stored = embed_real_estate(kind, payload['object_id'], payload['company_id'])
    return {'kind': kind, 'object_id': payload['object_id'], 'embedded': stored}


def _load_context(payload, context):
    from apps.real_estate.models import RealEstateParseLog
    from apps.tenancy.models import Company
    from apps.tenancy.services.access import company_for_message
    from apps.whatsapp_bridge.models import WhatsAppMessage

    task_company_id = BackgroundTask.objects.values_list('company_id', flat=True).get(pk=context.task_id)
    if task_company_id != payload['company_id']:
        raise ValueError('Task company does not match payload company.')
    company = Company.objects.get(pk=payload['company_id'])
    if company.industry_type != Company.INDUSTRY_REAL_ESTATE:
        raise ValueError('Task company is not configured for Real Estate.')
    message = WhatsAppMessage.objects.select_related(
        'account__communication_account', 'chat', 'contact',
    ).get(pk=payload['message_id'])
    if company_for_message(message) != company:
        raise ValueError('Message belongs to another company.')
    parse_log = RealEstateParseLog.objects.get(message=message, company=company)
    return company, message, parse_log


def _current_skip_reason(message, parse_log):
    from apps.whatsapp_bridge.services.ingestion_service import _classify_skip_reason

    reason = _classify_skip_reason(message)
    if reason:
        parse_log.status = parse_log.STATUS_SKIPPED
        parse_log.skip_reason = reason
        parse_log.save(update_fields=['status', 'skip_reason', 'updated_at'])
    return reason


@task_handler(
    key='real_estate.gate_message', default_queue='real_estate_gate',
    payload_validator=validate_message_payload, retry_safe=True,
)
def gate_message(payload, context):
    from apps.real_estate.models import RealEstateSettings
    from apps.real_estate.services.classification_dispatch import enqueue_extraction
    from apps.real_estate.services.gate_service import record_gate_failure, run_gate
    from apps.real_estate.services.opportunity_service import persist_gate_rejection

    company, message, parse_log = _load_context(payload, context)
    reason = _current_skip_reason(message, parse_log)
    if reason:
        return {'message_id': message.pk, 'gate_complete': False, 'skip_reason': reason}
    settings, _ = RealEstateSettings.objects.get_or_create(company=company)
    parse_log.gate_mode = settings.gate_mode
    parse_log.save(update_fields=['gate_mode', 'updated_at'])
    decision = 'disabled'
    if settings.gate_mode != RealEstateSettings.GATE_DISABLED:
        try:
            decision = run_gate(message, parse_log, company)
        except Exception as exc:
            record_gate_failure(parse_log, exc)
            decision = 'needs_review'
    if settings.gate_mode == RealEstateSettings.GATE_ENFORCED and decision == 'not_real_estate':
        opportunity = persist_gate_rejection(message, company)
        parse_log.opportunity = opportunity
        parse_log.status = parse_log.STATUS_COMPLETE
        parse_log.total_duration_ms = max(
            0, int((timezone.now() - parse_log.created_at).total_seconds() * 1000),
        )
        parse_log.save(update_fields=['opportunity', 'status', 'total_duration_ms', 'updated_at'])
        return {'message_id': message.pk, 'gate_complete': True, 'stopped': True, 'decision': decision}
    task = enqueue_extraction(message, company, parse_log)
    return {
        'message_id': message.pk, 'gate_complete': True, 'stopped': False,
        'decision': decision, 'extraction_task_id': task.pk,
    }


@task_handler(
    key='real_estate.extract_message', default_queue='real_estate_extract',
    payload_validator=validate_message_payload, retry_safe=True,
)
def extract_message(payload, context):
    from apps.real_estate.services.extraction_service import run_extraction

    company, message, parse_log = _load_context(payload, context)
    reason = _current_skip_reason(message, parse_log)
    if reason:
        return {'message_id': message.pk, 'extraction_complete': False, 'skip_reason': reason}
    opportunity, parsed = run_extraction(message, parse_log, company)
    return {
        'message_id': message.pk,
        'opportunity_id': opportunity.pk,
        'decision': parsed['decision'],
        'extraction_complete': True,
    }


@task_handler(
    key='real_estate.embed_property', default_queue='real_estate_embeddings',
    payload_validator=validate_embedding_payload, retry_safe=True,
)
def embed_property(payload, context):
    return _embed('property', payload, context)


@task_handler(
    key='real_estate.embed_listing', default_queue='real_estate_embeddings',
    payload_validator=validate_embedding_payload, retry_safe=True,
)
def embed_listing(payload, context):
    return _embed('listing', payload, context)


@task_handler(
    key='real_estate.embed_requirement', default_queue='real_estate_embeddings',
    payload_validator=validate_embedding_payload, retry_safe=True,
)
def embed_requirement(payload, context):
    return _embed('requirement', payload, context)


@task_handler(
    key='real_estate.embed_candidate', default_queue='real_estate_embeddings',
    payload_validator=validate_embedding_payload, retry_safe=True,
)
def embed_candidate(payload, context):
    return _embed('candidate', payload, context)
