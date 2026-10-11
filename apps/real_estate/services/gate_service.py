import logging
import time

from apps.real_estate.models import RealEstateAgentCallLog, RealEstatePromptConfig
from apps.real_estate.services.agent_call import call_real_estate_agent
from apps.real_estate.services.prompts import configured_prompt, message_prompt
from apps.real_estate.services.response_parser import parse_gate_response

logger = logging.getLogger(__name__)


def run_gate(message, parse_log, company):
    system_prompt, prompt_config = configured_prompt(company, RealEstatePromptConfig.KEY_GATE)
    messages = [
        {'role': 'system', 'content': system_prompt},
        {'role': 'user', 'content': message_prompt(message)},
    ]
    parse_log.status = parse_log.STATUS_GATE_RUNNING
    parse_log.gate_request = {'messages': messages, 'temperature': 0}
    parse_log.error = ''
    parse_log.save(update_fields=['status', 'gate_request', 'error', 'updated_at'])
    started = time.monotonic()
    try:
        response = call_real_estate_agent(
            purpose=RealEstateAgentCallLog.PURPOSE_GATE,
            messages=messages,
            company=company,
            prompt_config=prompt_config,
            wa_message_id=message.pk,
            temperature=0,
        )
        decision = parse_gate_response(response)
        parse_log.gate_response = response
        parse_log.gate_decision = decision
        return decision
    finally:
        parse_log.gate_duration_ms = int((time.monotonic() - started) * 1000)
        parse_log.save(update_fields=[
            'gate_response', 'gate_decision', 'gate_duration_ms', 'updated_at',
        ])


def record_gate_failure(parse_log, exc):
    logger.warning('Real Estate GatePass failed open: %s', exc, exc_info=True)
    parse_log.gate_decision = 'needs_review'
    parse_log.error = f'GatePass failed open: {exc}'
    parse_log.save(update_fields=['gate_decision', 'error', 'updated_at'])

