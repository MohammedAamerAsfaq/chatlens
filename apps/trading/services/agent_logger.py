import time
import logging

logger = logging.getLogger(__name__)


def call_agent(purpose: str, messages: list, wa_message_id=None, **kwargs) -> str:
    """
    Call ai_manager.agent(), log the full request/response to AgentCallLog, and return the response.
    Raises on failure after logging the error.
    """
    from apps.ai_providers.manager import ai_manager
    from apps.trading.models import AgentCallLog

    agent_config = kwargs.pop('agent_config', None)
    prompt_key = kwargs.pop('prompt_key', '')
    company = kwargs.pop('company', None)
    kiwi_router = kwargs.pop('kiwi_router', None)
    if kiwi_router is None and prompt_key:
        from apps.trading.models import PromptConfig
        kiwi_router = PromptConfig.get_kiwi_router(prompt_key, company=company)
    provider = model = ''
    try:
        if kiwi_router:
            provider = 'kiwi_router'
            model = kiwi_router.name
        else:
            config = agent_config or ai_manager.active_config('agent')
            if config:
                provider = config.provider
                model = config.model
    except Exception:
        pass

    classification_version = kwargs.pop('classification_version', '') or ''
    input_tokens = sum(len(m.get('content', '')) for m in messages) // 4

    start   = time.monotonic()
    success = False
    response = ''
    error    = ''

    try:
        from apps.queue_management.services import run_ai_call_with_deadline, task_deadline
        deadline = task_deadline.get()
        if deadline is not None:
            # Pass the remaining durable-task budget to the HTTP provider rather
            # than timing out in a nested thread that continues executing.
            kwargs['request_timeout'] = max(1, int(deadline - time.monotonic()))
        if kiwi_router:
            from apps.ai_providers.kiwi_router_service import execute_agent
            correlation_id = (
                f'whatsapp-message:{wa_message_id}'
                if wa_message_id is not None
                else f'agent-call:{purpose}:{time.monotonic_ns()}'
            )
            response, member = run_ai_call_with_deadline(
                lambda: execute_agent(
                    kiwi_router.pk,
                    messages=messages,
                    workflow_key=prompt_key or purpose,
                    correlation_id=correlation_id,
                    **kwargs,
                )
            )
            provider = member.provider_config.provider
            model = member.provider_config.model
        else:
            response = run_ai_call_with_deadline(
                lambda: ai_manager.agent(messages, config=agent_config, **kwargs)
            )
        success  = True
        return response
    except Exception as exc:
        error = str(exc)
        raise
    finally:
        duration_ms   = int((time.monotonic() - start) * 1000)
        output_tokens = len(response) // 4
        try:
            AgentCallLog.objects.create(
                purpose       = purpose,
                provider      = provider,
                model         = model,
                messages      = messages,
                response      = response,
                input_tokens  = input_tokens,
                output_tokens = output_tokens,
                duration_ms   = duration_ms,
                success       = success,
                error         = error,
                classification_version = classification_version,
                wa_message_id = wa_message_id,
            )
        except Exception:
            logger.exception('agent_logger | failed to persist call log')
