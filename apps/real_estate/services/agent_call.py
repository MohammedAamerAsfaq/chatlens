import logging
import time

from apps.real_estate.models import RealEstateAgentCallLog

logger = logging.getLogger(__name__)


def call_real_estate_agent(
    *, purpose, messages, company, prompt_config=None, wa_message_id=None,
    correlation_id=None, **kwargs,
):
    from apps.ai_providers.manager import ai_manager

    agent_config = prompt_config.agent_config if prompt_config else None
    kiwi_router = prompt_config.kiwi_router if prompt_config else None
    _validate_targets(company, agent_config, kiwi_router)
    provider, model = _target_identity(company, agent_config, kiwi_router, ai_manager)
    response = ''
    error = ''
    success = False
    started = time.monotonic()
    try:
        from apps.queue_management.services import run_ai_call_with_deadline, task_deadline

        deadline = task_deadline.get()
        if deadline is not None:
            kwargs['request_timeout'] = max(1, int(deadline - time.monotonic()))
        if kiwi_router:
            from apps.ai_providers.kiwi_router_service import execute_agent

            response, member = run_ai_call_with_deadline(lambda: execute_agent(
                kiwi_router.pk,
                company=company,
                messages=messages,
                workflow_key=f'real_estate.{purpose}',
                correlation_id=correlation_id or _message_correlation(wa_message_id, purpose),
                **kwargs,
            ))
            provider = member.provider_config.provider
            model = member.provider_config.model
        else:
            response = run_ai_call_with_deadline(lambda: ai_manager.agent(
                messages, config=agent_config, company=company, **kwargs,
            ))
        success = True
        return response
    except Exception as exc:
        error = str(exc)
        raise
    finally:
        _persist_call(
            company=company, purpose=purpose, provider=provider, model=model,
            messages=messages, response=response, success=success, error=error,
            duration_ms=int((time.monotonic() - started) * 1000),
            wa_message_id=wa_message_id,
        )


def _validate_targets(company, agent_config, kiwi_router):
    if agent_config and agent_config.company_id != company.pk:
        raise ValueError('The selected AI provider belongs to another company.')
    if kiwi_router and kiwi_router.company_id != company.pk:
        raise ValueError('The selected KiwiRouter belongs to another company.')


def _message_correlation(wa_message_id, purpose):
    if wa_message_id is not None:
        return f'whatsapp-message:{wa_message_id}'
    return f'real-estate:{purpose}'


def _target_identity(company, agent_config, kiwi_router, ai_manager):
    if kiwi_router:
        return 'kiwi_router', kiwi_router.name
    config = agent_config or ai_manager.active_config('agent', company=company)
    return (config.provider, config.model) if config else ('', '')


def _persist_call(**values):
    try:
        response = values['response'] or ''
        messages = values['messages']
        RealEstateAgentCallLog.objects.create(
            **values,
            input_tokens=sum(len(item.get('content', '')) for item in messages) // 4,
            output_tokens=len(response) // 4,
        )
    except Exception:
        logger.exception('real_estate agent call log could not be persisted')
