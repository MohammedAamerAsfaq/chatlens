import json
import logging

from apps.trading.models import AgentCallLog, MATCH_VERIFICATION_DEFAULT, PromptConfig
from apps.trading.services.agent_logger import call_agent

logger = logging.getLogger(__name__)

VALID_VERDICTS = {'exact', 'near', 'incorrect', 'unknown'}
VALID_ACTIONS = {'keep', 'mark_near', 'remove_match', 'manual_review'}


def _clean_json_response(raw: str) -> str:
    text = (raw or '').strip()
    if text.startswith('```'):
        text = text.split('\n', 1)[-1]
        text = text.rsplit('```', 1)[0]
    return text.strip()


def _decimal_or_none(value):
    return str(value) if value is not None else None


def _message_payload(inquiry):
    links = (
        inquiry.inquiry_messages
        .select_related('message', 'message__chat')
        .order_by('message__message_time')
    )
    return [
        {
            'message_id': link.message_id,
            'time': link.message.message_time.isoformat() if link.message.message_time else None,
            'chat': link.message.chat.name or link.message.chat.wa_chat_id if link.message.chat_id else '',
            'text': link.message.message_text,
        }
        for link in links
    ]


def _build_payload(inquiry, line: dict, product) -> dict:
    return {
        'inquiry': {
            'id': inquiry.pk,
            'type': inquiry.inquiry_type,
            'summary': inquiry.summary,
            'status': inquiry.status,
        },
        'original_messages': _message_payload(inquiry),
        'parsed_product_line': {
            'canonical_name': line.get('canonical_name') or '',
            'quantity': line.get('quantity'),
            'price': line.get('price'),
            'currency': line.get('currency'),
            'product_id': line.get('product_id'),
            'match_type': line.get('match_type'),
        },
        'stock_suggestion': {
            'product_id': product.pk,
            'brand': product.brand,
            'name': product.name,
            'category': product.category,
            'sku': product.sku,
            'qty': product.qty,
            'cost_price': _decimal_or_none(product.cost_price),
            'sale_price': _decimal_or_none(product.sale_price),
            'currency': product.currency,
        },
    }


def _parse_verdict(raw: str) -> dict:
    data = json.loads(_clean_json_response(raw))
    verdict = data.get('verdict') if data.get('verdict') in VALID_VERDICTS else 'unknown'
    action = data.get('recommended_action') if data.get('recommended_action') in VALID_ACTIONS else 'manual_review'
    differences = data.get('detected_differences') or []
    if not isinstance(differences, list):
        differences = [str(differences)]

    return {
        'verdict': verdict,
        'is_acceptable': bool(data.get('is_acceptable')) if verdict != 'unknown' else False,
        'reason': str(data.get('reason') or ''),
        'detected_differences': [str(item) for item in differences if str(item).strip()],
        'recommended_action': action,
        'raw': data,
    }


def verify_inquiry_match(inquiry, line: dict, product) -> dict:
    """Ask the configured agent to manually audit one stock suggestion.

    This intentionally does not mutate the inquiry. The result is a human review aid only.
    """
    payload = _build_payload(inquiry, line, product)
    system_prompt = PromptConfig.get_body(
        PromptConfig.KEY_MATCH_VERIFICATION,
        MATCH_VERIFICATION_DEFAULT,
        company=inquiry.company,
    )
    user_prompt = (
        'Verify this inquiry stock suggestion. Return only the required JSON.\n\n'
        + json.dumps(payload, ensure_ascii=False, default=str)
    )
    first_message = (payload['original_messages'] or [{}])[0].get('message_id')

    try:
        raw_response = call_agent(
            AgentCallLog.PURPOSE_MATCH_VERIFICATION,
            [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt},
            ],
            wa_message_id=first_message,
            temperature=0,
        )
        parsed = _parse_verdict(raw_response)
    except Exception:
        logger.exception(
            'verify_inquiry_match | failed | inquiry_id=%s | product_id=%s',
            inquiry.pk,
            product.pk,
        )
        raise

    return {
        **parsed,
        'input': payload,
    }
