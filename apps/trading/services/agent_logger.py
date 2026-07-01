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

    provider = model = ''
    try:
        config = ai_manager.active_config('agent')
        if config:
            provider = config.provider
            model    = config.model
    except Exception:
        pass

    input_tokens = sum(len(m.get('content', '')) for m in messages) // 4

    start   = time.monotonic()
    success = False
    response = ''
    error    = ''

    try:
        response = ai_manager.agent(messages, **kwargs)
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
                wa_message_id = wa_message_id,
            )
        except Exception:
            logger.exception('agent_logger | failed to persist call log')
