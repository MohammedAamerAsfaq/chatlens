from django.db.models import Q

from apps.ai_providers.models import (
    AIProviderRequestLog,
    KiwiRouterReservation,
    KiwiRoutingDecision,
)
from apps.real_estate.models import (
    CandidateEmbedding,
    ListingEmbedding,
    PropertyEmbedding,
    RealEstateAgentCallLog,
    RealEstateParseLog,
    RequirementEmbedding,
)
from apps.task_management.models import BackgroundTask
from apps.tenancy.models import Company
from apps.trading.models import AgentCallLog, AiParseV2Log


AI_QUEUES = (
    'ai', 'embeddings', 'v2_pass1', 'v2_pass2', 'real_estate_gate',
    'real_estate_extract', 'real_estate_match', 'real_estate_embeddings',
)
SENSITIVE_KEYS = ('api_key', 'apikey', 'authorization', 'password', 'secret', 'token')


def sanitize_data(value):
    if isinstance(value, dict):
        return {
            key: '[redacted]' if any(part in str(key).lower() for part in SENSITIVE_KEYS)
            else sanitize_data(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [sanitize_data(item) for item in value]
    return value


def _parse_queryset(company):
    if company.industry_type == Company.INDUSTRY_REAL_ESTATE:
        return RealEstateParseLog.objects.filter(company=company).select_related('account', 'message')
    return AiParseV2Log.objects.filter(
        account__communication_account__company=company,
    ).select_related('account', 'message')


def _call_queryset(company):
    model = RealEstateAgentCallLog if company.industry_type == Company.INDUSTRY_REAL_ESTATE else AgentCallLog
    return model.objects.filter(company=company)


def section_queryset(company, section):
    if section == 'parsing':
        return _parse_queryset(company)
    if section == 'calls':
        return _call_queryset(company)
    if section == 'routing':
        return KiwiRoutingDecision.objects.filter(
            Q(router__company=company) | Q(provider_config__company=company),
        ).select_related('router', 'provider_config').distinct()
    if section == 'reservations':
        return KiwiRouterReservation.objects.filter(
            member__router__company=company,
        ).select_related('member__router', 'member__provider_config')
    if section == 'limits':
        return AIProviderRequestLog.objects.filter(config__company=company).select_related('config')
    if section == 'tasks':
        return BackgroundTask.objects.filter(company=company).filter(
            Q(queue_name__in=AI_QUEUES) |
            Q(queue_name__startswith='real_estate_') |
            Q(task_key__icontains='classif') |
            Q(task_key__icontains='embed'),
        )
    raise ValueError('Unknown AI operations section.')


def filter_section_queryset(queryset, section, status_value='', search=''):
    if status_value:
        if section == 'calls':
            queryset = queryset.filter(success=status_value == 'succeeded')
        elif section == 'routing':
            queryset = queryset.filter(decision=status_value)
        elif section != 'limits':
            queryset = queryset.filter(status=status_value)
    if not search:
        return queryset
    lookups = {
        'parsing': (
            Q(error__icontains=search) | Q(gate_decision__icontains=search) |
            Q(skip_reason__icontains=search) | Q(message_id__icontains=search)
        ),
        'calls': (
            Q(purpose__icontains=search) | Q(provider__icontains=search) |
            Q(model__icontains=search) | Q(error__icontains=search) |
            Q(wa_message_id__icontains=search)
        ),
        'routing': (
            Q(workflow_key__icontains=search) | Q(correlation_id__icontains=search) |
            Q(reason__icontains=search) | Q(router__name__icontains=search) |
            Q(provider_config__display_name__icontains=search)
        ),
        'reservations': (
            Q(correlation_id__icontains=search) | Q(task_id__icontains=search) |
            Q(member__router__name__icontains=search) |
            Q(member__provider_config__display_name__icontains=search)
        ),
        'limits': (
            Q(config__display_name__icontains=search) |
            Q(config__provider__icontains=search) | Q(config__model__icontains=search)
        ),
        'tasks': (
            Q(task_key__icontains=search) | Q(queue_name__icontains=search) |
            Q(correlation_id__icontains=search) | Q(last_error__icontains=search)
        ),
    }
    return queryset.filter(lookups[section])


def embedding_rows(company):
    models = (
        ('property', PropertyEmbedding, 'property'),
        ('listing', ListingEmbedding, 'listing'),
        ('requirement', RequirementEmbedding, 'requirement'),
        ('candidate', CandidateEmbedding, 'candidate'),
    )
    rows = []
    for kind, model, target_field in models:
        queryset = model.objects.filter(company=company).select_related(target_field)
        for record in queryset:
            target = getattr(record, target_field)
            rows.append({
                'id': f'{kind}:{record.pk}', 'title': f'{kind.title()} #{target.pk}',
                'category': kind, 'status': record.status, 'occurred_at': record.updated_at,
                'summary': getattr(target, 'title', '') or str(target),
                'metrics': {'model': record.embedding_model or '-'},
                'detail': {'metadata': record.metadata, 'error': record.error},
            })
    return sorted(rows, key=lambda row: row['occurred_at'], reverse=True)


def serialize_row(section, row):
    if section == 'parsing':
        is_real_estate = isinstance(row, RealEstateParseLog)
        detail = {
            'gate_mode': row.gate_mode, 'gate_decision': row.gate_decision,
            'gate_request': row.gate_request, 'gate_response': row.gate_response,
            'extraction_request': getattr(row, 'extraction_request', None) or getattr(row, 'pass2_request', None),
            'extraction_response': getattr(row, 'extraction_response', None) or getattr(row, 'pass2_response', None),
            'result': getattr(row, 'extraction_result', None) or getattr(row, 'pass2_parsed', None),
            'error': row.error,
        }
        return {
            'id': row.pk, 'title': f'Message #{row.message_id}', 'category': 'real estate' if is_real_estate else 'trading v2',
            'status': row.status, 'occurred_at': row.created_at,
            'summary': row.skip_reason if is_real_estate and row.skip_reason else (row.gate_decision or 'AI parsing lifecycle'),
            'metrics': {
                'account': row.account.display_name, 'duration_ms': getattr(row, 'total_duration_ms', None) or getattr(row, 'total_ms', None),
            }, 'detail': detail,
        }
    if section == 'calls':
        return {
            'id': row.pk, 'title': row.purpose.replace('_', ' ').title(), 'category': row.provider or 'provider',
            'status': 'succeeded' if row.success else 'failed', 'occurred_at': row.created_at,
            'summary': row.model or 'No model recorded',
            'metrics': {'input_tokens': row.input_tokens, 'output_tokens': row.output_tokens, 'duration_ms': row.duration_ms},
            'detail': {'messages': row.messages, 'response': row.response, 'error': row.error, 'message_id': row.wa_message_id},
        }
    if section == 'routing':
        return {
            'id': row.pk, 'title': row.workflow_key, 'category': row.strategy, 'status': row.decision,
            'occurred_at': row.created_at, 'summary': row.reason or 'Provider selected by routing policy.',
            'metrics': {'router': row.router.name if row.router else '-', 'provider': row.provider_config.display_name if row.provider_config else '-'},
            'detail': {'correlation_id': row.correlation_id, 'task_id': row.task_id, 'estimated_input_tokens': row.estimated_input_tokens, 'estimated_output_tokens': row.estimated_output_tokens},
        }
    if section == 'reservations':
        return {
            'id': row.pk, 'title': row.member.router.name, 'category': row.member.provider_config.display_name,
            'status': row.status, 'occurred_at': row.reserved_at, 'summary': row.correlation_id,
            'metrics': {'expires_at': row.expires_at, 'released_at': row.released_at},
            'detail': {'task_id': row.task_id, 'estimated_input_tokens': row.estimated_input_tokens, 'estimated_output_tokens': row.estimated_output_tokens},
        }
    if section == 'limits':
        return {
            'id': row.pk, 'title': row.config.display_name, 'category': row.config.provider,
            'status': 'recorded', 'occurred_at': row.created_at, 'summary': row.config.model,
            'metrics': {'tokens': row.tokens, 'capability': row.config.capability}, 'detail': {},
        }
    return {
        'id': row.pk, 'title': row.task_key, 'category': row.queue_name, 'status': row.status,
        'occurred_at': row.created_at, 'summary': row.last_error or row.correlation_id or 'Durable AI task',
        'metrics': {'attempts': row.attempts, 'duration_ms': _task_duration_ms(row)},
        'detail': {'correlation_id': row.correlation_id, 'payload': row.payload, 'result': row.result, 'error': row.last_error},
    }


def _task_duration_ms(task):
    if not task.started_at:
        return None
    end = task.finished_at or task.updated_at
    return max(0, int((end - task.started_at).total_seconds() * 1000))
