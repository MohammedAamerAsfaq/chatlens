import json
import logging

logger = logging.getLogger(__name__)

# Valid tag values the AI may return
VALID_TAGS = {
    'wtb', 'wts', 'price_inquiry', 'stock_inquiry',
    'negotiation', 'deal_confirmation', 'greeting', 'joke', 'spam', 'other',
}

SYSTEM_PROMPT = """\
You are a B2B wholesale mobile trading classifier for a live trading desk.
Analyze the WhatsApp message below and classify it.

PRODUCT MASTER — match against these products and their aliases \
(case-insensitive, ignore extra spaces and punctuation):
{product_block}

Rules:
- is_inquiry must be true ONLY for genuine buy or sell business opportunities \
(not greetings, jokes, or casual messages).
- tags must contain at least one value.
- products must list every product mentioned in the message, normalised to the canonical name.
- dedup_key format: "{{buy|sell}}:{{product-slug}}:{{qty-bucket}}:{{contact_id}}" \
where qty-bucket is the quantity rounded to nearest 5 (use 0 if unknown). \
Leave empty string if is_inquiry is false.
- If multiple products: generate one dedup_key covering the primary product.

Respond ONLY with valid JSON — no markdown, no explanation — matching this schema exactly:
{{
  "tags": ["<tag>"],
  "products": [
    {{
      "product_id": <int or null if not in master>,
      "canonical_name": "<string>",
      "quantity": <int or null>,
      "price": <float or null>,
      "currency": "<string or null>"
    }}
  ],
  "is_inquiry": <bool>,
  "inquiry_type": "buy" | "sell" | "both" | null,
  "summary": "<one sentence>",
  "dedup_key": "<string>"
}}"""

USER_PROMPT = """\
Classify this message:

Sender contact ID: {contact_id}
Source: {source}
Time: {message_time}
Message text: "{message_text}\""""


def _build_prompts(message, product_block: str) -> tuple[str, str]:
    from apps.whatsapp_bridge.models import ChatType

    chat = message.chat
    if chat.chat_type == ChatType.GROUP:
        source = f'Group: {chat.name or chat.wa_chat_id}'
    else:
        source = 'Direct chat'

    contact_id = ''
    if message.contact:
        contact_id = message.contact.wa_contact_id
    elif message.sender_number:
        contact_id = message.sender_number

    system = SYSTEM_PROMPT.format(product_block=product_block)
    user   = USER_PROMPT.format(
        contact_id   = contact_id,
        source       = source,
        message_time = message.message_time.isoformat(),
        message_text = message.message_text.replace('"', "'"),
    )
    return system, user


def _parse_response(raw: str) -> dict:
    """Parse and validate the AI JSON response. Returns a sanitised dict."""
    # Strip markdown fences if the model includes them despite instructions
    text = raw.strip()
    if text.startswith('```'):
        text = text.split('\n', 1)[-1]
        text = text.rsplit('```', 1)[0]

    data = json.loads(text)

    tags = [t for t in (data.get('tags') or []) if t in VALID_TAGS]
    if not tags:
        tags = ['other']

    products = []
    for p in (data.get('products') or []):
        if not isinstance(p, dict):
            continue
        products.append({
            'product_id':    p.get('product_id'),
            'canonical_name': str(p.get('canonical_name') or ''),
            'quantity':      p.get('quantity'),
            'price':         p.get('price'),
            'currency':      p.get('currency'),
        })

    is_inquiry   = bool(data.get('is_inquiry', False))
    inquiry_type = data.get('inquiry_type') or ''
    if inquiry_type not in ('buy', 'sell', 'both'):
        inquiry_type = ''
    if not is_inquiry:
        inquiry_type = ''

    return {
        'tags':         tags,
        'products':     products,
        'is_inquiry':   is_inquiry,
        'inquiry_type': inquiry_type,
        'summary':      str(data.get('summary') or ''),
        'dedup_key':    str(data.get('dedup_key') or ''),
        'raw':          data,
    }


def classify_message(message) -> None:
    """
    Classify a single WhatsAppMessage and persist a MessageClassification record.
    Triggers inquiry creation/update when is_inquiry=True.
    Designed to run inside a background thread — never raises, always logs on failure.
    """
    from apps.ai_providers.manager import ai_manager
    from apps.trading.models import MessageClassification
    from apps.trading.services.product_cache import get_product_prompt_block
    from apps.trading.services.inquiry_service import process_inquiry

    msg_id = message.pk

    # Skip if already classified (idempotent — safe to call twice)
    if MessageClassification.objects.filter(message_id=msg_id).exists():
        return

    product_block = get_product_prompt_block()
    system_prompt, user_prompt = _build_prompts(message, product_block)

    try:
        raw_response = ai_manager.agent(
            [
                {'role': 'system',  'content': system_prompt},
                {'role': 'user',    'content': user_prompt},
            ],
            temperature=0,
        )
    except Exception:
        logger.exception('classify_message | agent call failed | message_id=%s', msg_id)
        return

    try:
        parsed = _parse_response(raw_response)
    except Exception:
        logger.exception(
            'classify_message | response parse failed | message_id=%s | raw=%r',
            msg_id, raw_response[:500],
        )
        return

    classification = MessageClassification.objects.create(
        message      = message,
        tags         = parsed['tags'],
        products     = parsed['products'],
        is_inquiry   = parsed['is_inquiry'],
        inquiry_type = parsed['inquiry_type'],
        ai_summary   = parsed['summary'],
        raw_response = parsed['raw'],
    )
    logger.info(
        'classify_message | done | message_id=%s | tags=%s | is_inquiry=%s',
        msg_id, parsed['tags'], parsed['is_inquiry'],
    )

    if parsed['is_inquiry'] and parsed['inquiry_type']:
        try:
            process_inquiry(message, classification)
        except Exception:
            logger.exception('classify_message | inquiry processing failed | message_id=%s', msg_id)
