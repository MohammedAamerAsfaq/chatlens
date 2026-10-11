import time

from django.db import transaction
from django.utils import timezone

from apps.real_estate.models import RealEstateAgentCallLog, RealEstatePromptConfig
from apps.real_estate.services.agent_call import call_real_estate_agent
from apps.real_estate.services.opportunity_service import persist_opportunity
from apps.real_estate.services.extraction_projection import project_extraction
from apps.real_estate.services.prompts import configured_prompt, message_prompt
from apps.real_estate.services.response_parser import parse_extraction_response


def run_extraction(message, parse_log, company):
    system_prompt, prompt_config = configured_prompt(company, RealEstatePromptConfig.KEY_EXTRACTION)
    messages = [
        {'role': 'system', 'content': system_prompt},
        {'role': 'user', 'content': message_prompt(message)},
    ]
    parse_log.status = parse_log.STATUS_EXTRACT_RUNNING
    parse_log.extraction_request = {'messages': messages, 'temperature': 0}
    parse_log.error = ''
    parse_log.save(update_fields=['status', 'extraction_request', 'error', 'updated_at'])
    started = time.monotonic()
    try:
        response = call_real_estate_agent(
            purpose=RealEstateAgentCallLog.PURPOSE_EXTRACTION,
            messages=messages,
            company=company,
            prompt_config=prompt_config,
            wa_message_id=message.pk,
            temperature=0,
        )
        parsed = parse_extraction_response(response)
        with transaction.atomic():
            opportunity = persist_opportunity(message, company, parsed)
            project_extraction(opportunity, parsed)
        parse_log.opportunity = opportunity
        parse_log.extraction_response = response
        parse_log.extraction_result = parsed
        parse_log.status = parse_log.STATUS_COMPLETE
        return opportunity, parsed
    except Exception as exc:
        parse_log.status = parse_log.STATUS_ERROR
        parse_log.error = str(exc)
        raise
    finally:
        parse_log.extraction_duration_ms = int((time.monotonic() - started) * 1000)
        parse_log.total_duration_ms = _total_ms(parse_log)
        parse_log.save(update_fields=[
            'opportunity', 'extraction_response', 'extraction_result',
            'extraction_duration_ms', 'total_duration_ms', 'status', 'error', 'updated_at',
        ])


def _total_ms(parse_log):
    return max(0, int((timezone.now() - parse_log.created_at).total_seconds() * 1000))
