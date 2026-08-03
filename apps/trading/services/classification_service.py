import json
import logging
import threading

logger = logging.getLogger(__name__)

# Valid tag values the AI may return
VALID_TAGS = {
    'wtb', 'wts', 'price_inquiry', 'stock_inquiry',
    'negotiation', 'deal_confirmation', 'greeting', 'joke', 'spam', 'other',
}

VALID_MATCH_TYPES = {'exact', 'near'}

USER_PROMPT = """\
Classify this message:

Sender contact ID: {contact_id}
Existing contact role tags: {contact_category}
Source: {source}
Time: {message_time}
Message text: "{message_text}\""""

VALID_CATEGORY_SUGGESTIONS = {'supplier', 'customer', 'both'}
CLASSIFICATION_V1 = 'v1'
CLASSIFICATION_V2 = 'v2'


def contact_role_category(contact) -> str:
    if not contact:
        return 'not set'
    roles = set(contact.role_tags.values_list('role', flat=True))
    if {'supplier', 'customer'}.issubset(roles):
        return 'both'
    if 'supplier' in roles:
        return 'supplier'
    if 'customer' in roles:
        return 'customer'
    return contact.category or 'not set'


def effective_classification_version(account) -> str:
    from apps.tenancy.models import Company

    override = getattr(account, 'classification_version_override', 'inherit') or 'inherit'
    if override in (CLASSIFICATION_V1, CLASSIFICATION_V2):
        return override

    communication_account = getattr(account, 'communication_account', None)
    company = (
        communication_account.company
        if communication_account and communication_account.company_id
        else None
    )
    version = getattr(company, 'default_classification_version', CLASSIFICATION_V1) if company else CLASSIFICATION_V1
    if version not in (CLASSIFICATION_V1, CLASSIFICATION_V2):
        return Company.CLASSIFICATION_V1
    return version


def _get_v1_prompt_body(company):
    from apps.trading.models import PromptConfig, INQUIRY_CLASSIFICATION_DEFAULT

    v1 = PromptConfig.objects.filter(
        company=company,
        key=PromptConfig.KEY_INQUIRY_CLASSIFICATION_V1,
    ).first()
    if v1:
        return v1.body
    return PromptConfig.get_body(
        PromptConfig.KEY_INQUIRY_CLASSIFICATION,
        INQUIRY_CLASSIFICATION_DEFAULT,
        company=company,
    )


def _build_prompts(message, product_block: str) -> tuple[str, str]:
    from apps.whatsapp_bridge.models import ChatType
    from apps.tenancy.services.access import company_for_message

    chat = message.chat
    company = company_for_message(message)
    if chat.chat_type == ChatType.GROUP:
        source = f'Group: {chat.name or chat.wa_chat_id}'
    else:
        source = 'Direct chat'

    contact_id = ''
    contact_category = 'not set'
    if message.contact:
        contact_id = message.contact.wa_contact_id
        contact_category = contact_role_category(message.contact)
    elif message.sender_number:
        contact_id = message.sender_number

    system_template = _get_v1_prompt_body(company)
    system = system_template.replace('{product_block}', product_block)
    user   = USER_PROMPT.format(
        contact_id       = contact_id,
        contact_category = contact_category,
        source           = source,
        message_time     = message.message_time.isoformat(),
        message_text     = message.message_text.replace('"', "'"),
    )
    return system, user


def _build_v2_extraction_prompts(message) -> tuple[str, str]:
    from apps.whatsapp_bridge.models import ChatType
    from apps.tenancy.services.access import company_for_message
    from apps.trading.models import PromptConfig, INQUIRY_EXTRACTION_V2_DEFAULT

    chat = message.chat
    if chat.chat_type == ChatType.GROUP:
        source = f'Group: {chat.name or chat.wa_chat_id}'
    else:
        source = 'Direct chat'

    contact_id = ''
    contact_category = 'not set'
    if message.contact:
        contact_id = message.contact.wa_contact_id
        contact_category = contact_role_category(message.contact)
    elif message.sender_number:
        contact_id = message.sender_number

    system = PromptConfig.get_body(
        PromptConfig.KEY_INQUIRY_EXTRACTION_V2,
        INQUIRY_EXTRACTION_V2_DEFAULT,
        company=company_for_message(message),
    )
    user = USER_PROMPT.format(
        contact_id=contact_id,
        contact_category=contact_category,
        source=source,
        message_time=message.message_time.isoformat(),
        message_text=message.message_text.replace('"', "'"),
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
    for index, p in enumerate(data.get('products') or []):
        if not isinstance(p, dict):
            raise ValueError(
                f'AI product entry must be an object | index={index} | type={type(p).__name__}'
            )
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


def _clean_json_response(raw: str):
    text = raw.strip()
    if text.startswith('```'):
        text = text.split('\n', 1)[-1]
        text = text.rsplit('```', 1)[0]
    return json.loads(text)


def _parse_v2_extraction_response(raw: str) -> dict:
    data = _clean_json_response(raw)

    tags = [t for t in (data.get('tags') or []) if t in VALID_TAGS]
    if not tags:
        tags = ['other']

    products = []
    for index, p in enumerate(data.get('products') or []):
        if not isinstance(p, dict):
            raise ValueError(
                f'AI V2 extraction product entry must be an object | index={index} | type={type(p).__name__}'
            )
        canonical_name = str(p.get('canonical_name') or '').strip()
        raw_text = str(p.get('raw_text') or '').strip()
        if not canonical_name and not raw_text:
            continue
        products.append({
            'product_id': None,
            'match_type': None,
            'canonical_name': canonical_name or raw_text,
            'raw_text': raw_text or canonical_name,
            'quantity': p.get('quantity'),
            'price': p.get('price'),
            'currency': p.get('currency'),
        })

    is_inquiry = bool(data.get('is_inquiry', False))
    inquiry_type = data.get('inquiry_type') or ''
    if inquiry_type not in ('buy', 'sell', 'both'):
        inquiry_type = ''
    if not is_inquiry:
        inquiry_type = ''
        products = []
    if is_inquiry and not inquiry_type:
        if 'wts' in tags:
            inquiry_type = 'sell'
        elif 'wtb' in tags:
            inquiry_type = 'buy'

    contact_category_suggestion = data.get('contact_category_suggestion') or ''
    if contact_category_suggestion not in VALID_CATEGORY_SUGGESTIONS:
        contact_category_suggestion = ''

    return {
        'tags': tags,
        'products': products,
        'is_inquiry': is_inquiry,
        'inquiry_type': inquiry_type,
        'summary': str(data.get('summary') or ''),
        'dedup_key': str(data.get('dedup_key') or ''),
        'contact_category_suggestion': contact_category_suggestion,
        'raw': data,
    }


def _candidate_payload(product, distance=None) -> dict:
    return {
        'product_id': product.pk,
        'name': product.name,
        'brand': product.brand,
        'category': product.category,
        'sku': product.sku,
        'qty': product.qty,
        'sale_price': float(product.sale_price) if product.sale_price is not None else None,
        'currency': product.currency,
        'aliases': [alias.alias for alias in product.alias_set.all()],
        'attributes': [
            {'key': attr.key, 'value': attr.value}
            for attr in product.attribute_set.all()
        ],
        'distance': distance,
    }


def _find_v2_candidates(query: str, company, top_k: int = 8) -> list[dict]:
    if not query or not company:
        return []

    try:
        from django.db import connection
        from pgvector import Vector
        from apps.ai_providers.manager import ai_manager
        from apps.trading.models import Product

        query_vec = ai_manager.embed(query)
        query_vec_text = Vector(query_vec).to_text()
        sql = """
            WITH scored AS (
                SELECT p.id AS product_id, (pe.embedding <=> %(qv)s::vector) AS distance
                FROM product_embedding pe
                JOIN trading_product p ON p.id = pe.product_id
                WHERE pe.embedding IS NOT NULL
                  AND p.is_active = TRUE
                  AND p.qty > 0
                  AND p.company_id = %(company_id)s

                UNION ALL

                SELECT pa.product_id AS product_id, (pae.embedding <=> %(qv)s::vector) AS distance
                FROM product_alias_embedding pae
                JOIN trading_product_alias pa ON pa.id = pae.alias_id
                JOIN trading_product p ON p.id = pa.product_id
                WHERE pae.embedding IS NOT NULL
                  AND p.is_active = TRUE
                  AND p.qty > 0
                  AND p.company_id = %(company_id)s
            )
            SELECT product_id, MIN(distance) AS best_distance
            FROM scored
            GROUP BY product_id
            ORDER BY best_distance ASC
            LIMIT %(top_k)s
        """
        with connection.cursor() as cursor:
            cursor.execute(sql, {'qv': query_vec_text, 'company_id': company.pk, 'top_k': top_k})
            rows = cursor.fetchall()

        if not rows:
            return []

        products = (
            Product.objects
            .filter(pk__in=[product_id for product_id, _ in rows], company=company, is_active=True, qty__gt=0)
            .prefetch_related('alias_set', 'attribute_set')
        )
        products_by_id = {product.pk: product for product in products}
        return [
            _candidate_payload(products_by_id[product_id], float(distance))
            for product_id, distance in rows
            if product_id in products_by_id
        ]
    except Exception:
        logger.exception('V2 candidate retrieval failed | company_id=%s | query=%r', company.pk if company else None, query)
        raise


def _build_v2_match_prompts(message, products: list[dict], candidates_by_index: dict[int, list[dict]]) -> tuple[str, str]:
    from apps.tenancy.services.access import company_for_message
    from apps.trading.models import PromptConfig, INQUIRY_MATCH_DECISION_V2_DEFAULT

    system = PromptConfig.get_body(
        PromptConfig.KEY_INQUIRY_MATCH_DECISION_V2,
        INQUIRY_MATCH_DECISION_V2_DEFAULT,
        company=company_for_message(message),
    )
    payload = {
        'original_message': message.message_text,
        'products': [
            {
                'line_index': index,
                'raw_text': product.get('raw_text') or '',
                'canonical_name': product.get('canonical_name') or '',
                'quantity': product.get('quantity'),
                'price': product.get('price'),
                'currency': product.get('currency'),
                'candidates': candidates_by_index.get(index, []),
            }
            for index, product in enumerate(products)
        ],
    }
    return system, json.dumps(payload, ensure_ascii=False, default=str)


def _parse_v2_match_response(raw: str, expected_indexes: set[int]) -> dict[int, dict]:
    data = _clean_json_response(raw)
    rows = data.get('results')
    if not isinstance(rows, list):
        raise ValueError('V2 match response must contain a results array')

    parsed = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('V2 match result entries must be objects')
        line_index = row.get('line_index')
        if not isinstance(line_index, int):
            raise ValueError('V2 match result line_index must be an integer')
        if line_index not in expected_indexes:
            raise ValueError(f'V2 match result has unexpected line_index={line_index}')
        match_type = row.get('match_type') if row.get('product_id') is not None else None
        if match_type not in VALID_MATCH_TYPES:
            match_type = None
        confidence = row.get('confidence')
        try:
            confidence = float(confidence)
        except (TypeError, ValueError):
            confidence = 0.0
        parsed[line_index] = {
            'product_id': row.get('product_id'),
            'match_type': match_type,
            'confidence': max(0.0, min(1.0, confidence)),
            'reason': str(row.get('reason') or ''),
            'rejected_candidate_ids': row.get('rejected_candidate_ids') or [],
        }

    missing = expected_indexes - set(parsed)
    if missing:
        raise ValueError(f'V2 match response missing line indexes: {sorted(missing)}')
    return parsed


def validate_category_suggestion(suggestion: str, contact) -> str:
    """
    Self-consistency guard: "both" already covers every direction a suggestion
    could nudge toward (supplier and customer), so per the prompt's own instructions
    it's a final state with nothing left to suggest. Confirmed in production data that
    the agent doesn't reliably follow this: 154 MessageClassification rows and 129
    Inquiry rows were found suggesting a change (including outright downgrades to
    "customer"/"supplier") away from a contact already marked "both". This never
    invents or changes *which* category to suggest — it only enforces the one rule the
    prompt already claims to follow, so a stray suggestion can't offer to undo an
    already-final categorization. Unlike the product-match guard this deliberately
    doesn't try to verify (removed — see git history — it was re-deciding a semantic
    judgment call, "does this canonical_name mean the same product as the catalog
    entry", using brittle string matching instead of trusting the model that already
    made that call correctly), this only checks a hard structural fact: is the
    existing category already "both". Nothing here requires language understanding.
    """
    if not suggestion or not contact:
        return suggestion
    roles = set(contact.role_tags.values_list('role', flat=True))
    if suggestion == 'both':
        if {'supplier', 'customer'}.issubset(roles):
            return ''
        if 'supplier' in roles:
            return 'customer'
        if 'customer' in roles:
            return 'supplier'
        return 'both'
    if suggestion in roles:
        return ''
    return suggestion


def classify_message(message) -> None:
    """
    Classify a single WhatsAppMessage and persist a MessageClassification record.
    Triggers inquiry creation/update when is_inquiry=True.
    Designed to run inside a background thread — never raises, always logs on failure.
    """
    from apps.trading.models import MessageClassification
    from apps.trading.services.product_cache import get_product_prompt_block
    from apps.trading.services.inquiry_service import process_inquiry
    from apps.tenancy.services.access import company_for_message

    msg_id = message.pk

    # Skip if already classified (idempotent — safe to call twice)
    if MessageClassification.objects.filter(message_id=msg_id).exists():
        return

    try:
        from apps.trading.services.agent_logger import call_agent
        from apps.trading.models import AgentCallLog

        version = effective_classification_version(message.account)
        if version == CLASSIFICATION_V2:
            classify_message_v2(message)
            return

        product_block = get_product_prompt_block(company=company_for_message(message))
        system_prompt, user_prompt = _build_prompts(message, product_block)

        raw_response = call_agent(
            AgentCallLog.PURPOSE_CLASSIFICATION,
            [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user',   'content': user_prompt},
            ],
            wa_message_id=msg_id,
            classification_version=CLASSIFICATION_V1,
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

    parsed['contact_category_suggestion'] = validate_category_suggestion(
        parsed['contact_category_suggestion'], message.contact,
    )

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
        classification_version = CLASSIFICATION_V1,
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
            raise


def classify_message_v2(message) -> None:
    """
    V2 two-pass path:
    1. AI extracts/classifies the inquiry without inventory matching.
    2. The inquiry is persisted immediately with product_match_status=pending.
    3. A background thread retrieves candidates and sends all product lines to AI in
       one batched match-decision request.
    """
    from apps.trading.models import AgentCallLog, AiParseV2Log, MessageClassification
    from apps.trading.services.agent_logger import call_agent
    from apps.trading.services.inquiry_service import process_inquiry

    system_prompt, user_prompt = _build_v2_extraction_prompts(message)
    log, _ = AiParseV2Log.objects.update_or_create(
        message=message,
        defaults={
            'account': message.account,
            'chat': message.chat,
            'status': AiParseV2Log.STATUS_PASS1_STARTED,
            'pass1_request': {
                'messages': [
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': user_prompt},
                ],
                'temperature': 0,
            },
            'error': '',
        },
    )
    try:
        raw_response = call_agent(
            AgentCallLog.PURPOSE_INQUIRY_EXTRACTION_V2,
            [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt},
            ],
            wa_message_id=message.pk,
            classification_version=CLASSIFICATION_V2,
            temperature=0,
        )
        log.pass1_response = raw_response
        parsed = _parse_v2_extraction_response(raw_response)
    except Exception as exc:
        log.status = AiParseV2Log.STATUS_ERROR
        log.error = str(exc)
        log.save(update_fields=['pass1_response', 'status', 'error', 'updated_at'])
        raise
    log.pass1_parsed = parsed['raw']
    log.status = AiParseV2Log.STATUS_PASS1_DONE
    log.save(update_fields=['pass1_response', 'pass1_parsed', 'status', 'updated_at'])
    parsed['contact_category_suggestion'] = validate_category_suggestion(
        parsed['contact_category_suggestion'], message.contact,
    )

    classification = MessageClassification.objects.create(
        message=message,
        tags=parsed['tags'],
        products=parsed['products'],
        is_inquiry=parsed['is_inquiry'],
        inquiry_type=parsed['inquiry_type'],
        ai_summary=parsed['summary'],
        dedup_key=parsed['dedup_key'],
        suggested_contact_category=parsed['contact_category_suggestion'],
        raw_response={'v2_pass1': parsed['raw']},
        classification_version=CLASSIFICATION_V2,
    )
    log.classification = classification
    log.save(update_fields=['classification', 'updated_at'])
    logger.info(
        'classify_message_v2 | pass1 done | message_id=%s | products=%s | is_inquiry=%s',
        message.pk,
        len(parsed['products']),
        parsed['is_inquiry'],
    )

    inquiry_ids = []
    if parsed['is_inquiry'] and parsed['inquiry_type']:
        inquiries = process_inquiry(message, classification) or []
        inquiry_ids = [inquiry.pk for inquiry in inquiries]

    if inquiry_ids:
        log.inquiry_ids = inquiry_ids
        log.save(update_fields=['inquiry_ids', 'updated_at'])
        _start_v2_match_thread(message.pk, classification.pk, inquiry_ids)


def _start_v2_match_thread(message_id: int, classification_id: int, inquiry_ids: list[int]) -> None:
    from django.db import connection as db_connection

    def _run():
        try:
            _run_v2_batched_match(message_id, classification_id, inquiry_ids)
        except Exception as exc:
            logger.exception(
                'classify_message_v2 | pass2 failed | message_id=%s | classification_id=%s',
                message_id,
                classification_id,
            )
            try:
                from apps.trading.models import AiParseV2Log, Inquiry
                Inquiry.objects.filter(pk__in=inquiry_ids).update(
                    product_match_status=Inquiry.CLASSIFICATION_MATCH_ERROR,
                    product_match_error=str(exc),
                )
                AiParseV2Log.objects.filter(message_id=message_id).update(
                    status=AiParseV2Log.STATUS_ERROR,
                    error=str(exc),
                )
            except Exception:
                logger.exception('classify_message_v2 | failed to mark pass2 error | inquiry_ids=%s', inquiry_ids)
        finally:
            db_connection.close()

    threading.Thread(target=_run, daemon=True).start()


def _run_v2_batched_match(message_id: int, classification_id: int, inquiry_ids: list[int]) -> None:
    from apps.trading.models import AgentCallLog, AiParseV2Log, Inquiry, MessageClassification
    from apps.trading.services.agent_logger import call_agent
    from apps.tenancy.services.access import company_for_message
    from apps.whatsapp_bridge.models import WhatsAppMessage

    message = WhatsAppMessage.objects.select_related('account', 'chat', 'contact').get(pk=message_id)
    classification = MessageClassification.objects.get(pk=classification_id)
    products = list(classification.products or [])

    if not products:
        Inquiry.objects.filter(pk__in=inquiry_ids).update(
            product_match_status=Inquiry.CLASSIFICATION_MATCH_COMPLETE,
            product_match_error='',
        )
        AiParseV2Log.objects.filter(message_id=message_id).update(
            status=AiParseV2Log.STATUS_COMPLETE,
            pass2_request={'skipped': True, 'reason': 'no extracted products'},
            pass2_response='',
            pass2_parsed={'results': []},
            error='',
        )
        return

    company = company_for_message(message)
    candidates_by_index = {
        index: _find_v2_candidates(
            product.get('canonical_name') or product.get('raw_text') or '',
            company,
        )
        for index, product in enumerate(products)
    }

    system_prompt, user_prompt = _build_v2_match_prompts(message, products, candidates_by_index)
    AiParseV2Log.objects.filter(message_id=message_id).update(
        status=AiParseV2Log.STATUS_PASS2_STARTED,
        pass2_request={
            'messages': [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt},
            ],
            'temperature': 0,
        },
        error='',
    )
    raw_response = call_agent(
        AgentCallLog.PURPOSE_INQUIRY_MATCH_V2,
        [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_prompt},
        ],
        wa_message_id=message_id,
        classification_version=CLASSIFICATION_V2,
        temperature=0,
    )
    match_results = _parse_v2_match_response(raw_response, set(range(len(products))))

    updated_products = []
    for index, product in enumerate(products):
        result = match_results[index]
        candidate_ids = {candidate['product_id'] for candidate in candidates_by_index.get(index, [])}
        product_id = result['product_id']
        if product_id is not None and product_id not in candidate_ids:
            raise ValueError(
                f'V2 match selected product_id={product_id} outside candidates for line_index={index}'
            )
        updated = {
            **product,
            'product_id': product_id,
            'match_type': result['match_type'] if product_id is not None else None,
            'match_reason': result['reason'],
            'match_confidence': result['confidence'],
            'candidate_products': candidates_by_index.get(index, []),
            'v2_line_index': index,
        }
        updated_products.append(updated)

    raw_existing = classification.raw_response or {}
    if not isinstance(raw_existing, dict):
        raw_existing = {'v1_legacy_raw': raw_existing}
    raw_existing['v2_pass2'] = {
        'raw': _clean_json_response(raw_response),
        'candidates_by_index': candidates_by_index,
    }
    classification.products = updated_products
    classification.raw_response = raw_existing
    classification.save(update_fields=['products', 'raw_response'])

    Inquiry.objects.filter(pk__in=inquiry_ids).update(
        products=updated_products,
        product_match_status=Inquiry.CLASSIFICATION_MATCH_COMPLETE,
        product_match_error='',
    )
    AiParseV2Log.objects.filter(message_id=message_id).update(
        status=AiParseV2Log.STATUS_COMPLETE,
        pass2_response=raw_response,
        pass2_parsed={
            'raw': _clean_json_response(raw_response),
            'match_results': match_results,
            'updated_products': updated_products,
        },
        error='',
    )
    logger.info(
        'classify_message_v2 | pass2 done | message_id=%s | products=%s | inquiries=%s',
        message_id,
        len(updated_products),
        inquiry_ids,
    )
