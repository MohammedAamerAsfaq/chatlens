import json
import logging
import re

logger = logging.getLogger(__name__)

_WORD_RE = re.compile(r'[a-z0-9]+')

# Product-line/brand words that routinely appear in a catalog name but that a customer
# almost never types when requesting a product ("iPhone 17 Pro Max..." vs. the sender's
# own "17 pro max...") — harmless omissions, not a sign of a wrong match. Extend this if
# the catalog grows beyond Apple devices.
_COSMETIC_WORDS = {'iphone', 'ipad', 'apple'}
_STORAGE_UNIT_RE = re.compile(r'^(\d+)(gb|tb)$')


def _words(text: str) -> set:
    return set(_WORD_RE.findall((text or '').lower()))


def _normalize_attribute_words(words: set) -> set:
    """Collapse cosmetic-only differences before comparing two word sets for the same
    product: a bare storage number ("256") and its unit-suffixed form ("256gb") name the
    same attribute, and brand/product-line words are routinely omitted by customers
    without changing what they're asking for — neither should register as a mismatch.
    """
    out = set()
    for w in words:
        if w in _COSMETIC_WORDS:
            continue
        m = _STORAGE_UNIT_RE.match(w)
        out.add(m.group(1) if m else w)
    return out

# Valid tag values the AI may return
VALID_TAGS = {
    'wtb', 'wts', 'price_inquiry', 'stock_inquiry',
    'negotiation', 'deal_confirmation', 'greeting', 'joke', 'spam', 'other',
}

VALID_MATCH_TYPES = {'exact', 'near'}

USER_PROMPT = """\
Classify this message:

Sender contact ID: {contact_id}
Existing contact category: {contact_category}
Source: {source}
Time: {message_time}
Message text: "{message_text}\""""

VALID_CATEGORY_SUGGESTIONS = {'supplier', 'customer', 'both'}


def _build_prompts(message, product_block: str) -> tuple[str, str]:
    from apps.whatsapp_bridge.models import ChatType
    from apps.trading.models import PromptConfig, INQUIRY_CLASSIFICATION_DEFAULT

    chat = message.chat
    if chat.chat_type == ChatType.GROUP:
        source = f'Group: {chat.name or chat.wa_chat_id}'
    else:
        source = 'Direct chat'

    contact_id = ''
    contact_category = 'not set'
    if message.contact:
        contact_id = message.contact.wa_contact_id
        contact_category = message.contact.category or 'not set'
    elif message.sender_number:
        contact_id = message.sender_number

    system_template = PromptConfig.get_body(
        PromptConfig.KEY_INQUIRY_CLASSIFICATION,
        INQUIRY_CLASSIFICATION_DEFAULT,
    )
    system = system_template.replace('{product_block}', product_block)
    user   = USER_PROMPT.format(
        contact_id       = contact_id,
        contact_category = contact_category,
        source           = source,
        message_time     = message.message_time.isoformat(),
        message_text     = message.message_text.replace('"', "'"),
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
        match_type = p.get('match_type') if p.get('product_id') is not None else None
        if match_type not in VALID_MATCH_TYPES:
            match_type = None
        products.append({
            'product_id':    p.get('product_id'),
            'match_type':    match_type,
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
    # Derive from tags if AI left inquiry_type null despite is_inquiry=True
    if is_inquiry and not inquiry_type:
        if 'wts' in tags:
            inquiry_type = 'sell'
        elif 'wtb' in tags:
            inquiry_type = 'buy'

    contact_category_suggestion = data.get('contact_category_suggestion') or ''
    if contact_category_suggestion not in VALID_CATEGORY_SUGGESTIONS:
        contact_category_suggestion = ''

    return {
        'tags':         tags,
        'products':     products,
        'is_inquiry':   is_inquiry,
        'inquiry_type': inquiry_type,
        'summary':      str(data.get('summary') or ''),
        'dedup_key':    str(data.get('dedup_key') or ''),
        'contact_category_suggestion': contact_category_suggestion,
        'raw':          data,
    }


def _validate_exact_matches(products: list) -> list:
    """
    Self-consistency guard, not a re-match: the agent occasionally claims
    match_type="exact" for a product_id whose real catalog name contradicts what
    it wrote into canonical_name for the same product (e.g. canonical_name says
    "Blue" but the linked catalog entry is actually "Orange"). We never try to
    find a different/better product_id ourselves — that's the agent's job. We
    only check whether the agent's own two answers (product_id's real name vs.
    canonical_name) agree, and downgrade match_type to "near" when they don't,
    so a self-contradictory "exact" never reaches the UI as a confident match.
    """
    exact_ids = {
        p['product_id'] for p in products
        if p['match_type'] == 'exact' and p['product_id'] is not None
    }
    if not exact_ids:
        return products

    try:
        from apps.trading.models import Product
        names = dict(Product.objects.filter(id__in=exact_ids).values_list('id', 'name'))
    except Exception:
        logger.exception('_validate_exact_matches | catalog lookup failed')
        return products

    for p in products:
        if p['match_type'] != 'exact' or p['product_id'] not in names:
            continue
        real_words = _normalize_attribute_words(_words(names[p['product_id']]))
        claimed_words = _normalize_attribute_words(_words(p['canonical_name']))
        if not real_words <= claimed_words:
            logger.warning(
                'classify_message | exact match self-contradiction | product_id=%s | '
                'catalog_name=%r | canonical_name=%r | missing_words=%s',
                p['product_id'], names[p['product_id']], p['canonical_name'],
                real_words - claimed_words,
            )
            p['match_type'] = 'near'
    return products


def classify_message(message) -> None:
    """
    Classify a single WhatsAppMessage and persist a MessageClassification record.
    Triggers inquiry creation/update when is_inquiry=True.
    Designed to run inside a background thread — never raises, always logs on failure.
    """
    from apps.trading.models import MessageClassification
    from apps.trading.services.product_cache import get_product_prompt_block
    from apps.trading.services.inquiry_service import process_inquiry

    msg_id = message.pk

    # Skip if already classified (idempotent — safe to call twice)
    if MessageClassification.objects.filter(message_id=msg_id).exists():
        return

    try:
        from apps.trading.services.agent_logger import call_agent
        from apps.trading.models import AgentCallLog

        product_block = get_product_prompt_block()
        system_prompt, user_prompt = _build_prompts(message, product_block)

        raw_response = call_agent(
            AgentCallLog.PURPOSE_CLASSIFICATION,
            [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user',   'content': user_prompt},
            ],
            wa_message_id=msg_id,
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

    parsed['products'] = _validate_exact_matches(parsed['products'])

    classification = MessageClassification.objects.create(
        message      = message,
        tags         = parsed['tags'],
        products     = parsed['products'],
        is_inquiry   = parsed['is_inquiry'],
        inquiry_type = parsed['inquiry_type'],
        ai_summary   = parsed['summary'],
        dedup_key    = parsed['dedup_key'],
        suggested_contact_category = parsed['contact_category_suggestion'],
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
