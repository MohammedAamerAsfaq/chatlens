"""V2 GatePass execution and enforced short-circuit behavior."""
import json
import time

VALID_DECISIONS = {'buy', 'sell', 'not_inquiry'}


def _parse_decision(raw_response):
    if not isinstance(raw_response, str):
        raise ValueError('GatePass returned no text response.')
    text = raw_response.strip()
    if text.startswith('```'):
        text = text.split('\n', 1)[-1].rsplit('```', 1)[0]
    decision = json.loads(text).get('decision')
    if decision not in VALID_DECISIONS:
        raise ValueError('GatePass decision must be buy, sell, or not_inquiry.')
    return decision


def run_v2_gatepass(message, log, company):
    """Run and audit GatePass; return an enforced no-inquiry classification or None."""
    from apps.trading.models import AgentCallLog, MessageClassification, PromptConfig
    from apps.trading.models import INQUIRY_GATE_V2_DEFAULT
    from apps.trading.services.agent_logger import call_agent
    from apps.trading.services.trading_settings_service import get_v2_matching_settings

    mode = get_v2_matching_settings(company)['gatepass_mode']
    messages = [
        {'role': 'system', 'content': PromptConfig.get_body(
            PromptConfig.KEY_INQUIRY_GATE_V2, INQUIRY_GATE_V2_DEFAULT, company=company,
        )},
        {'role': 'user', 'content': message.message_text},
    ]
    log.gate_mode = mode
    log.gate_request = {'messages': messages, 'temperature': 0}
    started = time.perf_counter()
    try:
        raw_response = call_agent(
            AgentCallLog.PURPOSE_INQUIRY_GATE_V2, messages,
            wa_message_id=message.pk, classification_version='v2',
            agent_config=PromptConfig.get_agent_config(PromptConfig.KEY_INQUIRY_GATE_V2, company=company),
            prompt_key=PromptConfig.KEY_INQUIRY_GATE_V2, company=company, temperature=0,
        )
        decision = _parse_decision(raw_response)
        log.gate_response = raw_response
        log.gate_decision = decision
    except Exception as exc:
        # A gate failure must never suppress a potentially valid inquiry.
        log.gate_response = str(exc)
        log.gate_decision = 'error'
        decision = 'error'
    finally:
        log.gate_ai_ms = max(0, int((time.perf_counter() - started) * 1000))
        log.save(update_fields=[
            'gate_mode', 'gate_request', 'gate_response', 'gate_decision',
            'gate_ai_ms', 'updated_at',
        ])

    if mode != 'enforced' or decision != 'not_inquiry':
        return None
    return MessageClassification.objects.update_or_create(
        message=message,
        defaults={
            'tags': ['other'], 'products': [], 'is_inquiry': False,
            'inquiry_type': '', 'ai_summary': 'GatePass: not an inquiry.',
            'dedup_key': '', 'suggested_contact_category': '',
            'raw_response': {'v2_gatepass': {'decision': decision}},
            'classification_version': 'v2',
        },
    )[0]
