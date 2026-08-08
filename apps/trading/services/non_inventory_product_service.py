import logging

from django.db import transaction
from django.db.models import F

from apps.trading.services.inquiry_product_service import (
    normalize_product_name,
    _as_decimal,
    _as_int,
)

logger = logging.getLogger(__name__)

IDENTITY_ATTRIBUTE_KEYS = (
    'Series',
    'Model',
    'Storage',
    'Color',
    'Region',
    'SIM Type',
    'Network',
    'Condition',
    'Variant',
)


class NonInventoryResolutionError(Exception):
    """Raised when an unmatched inquiry line cannot be tracked safely."""


def _embed_non_inventory_product_after_commit(non_inventory_product_id: int) -> None:
    from apps.message_intelligence.services.embedding_service import embed_non_inventory_product

    try:
        embed_non_inventory_product(non_inventory_product_id)
    except Exception:
        logger.exception(
            'resolve_unmatched_inquiry_product | auto embedding failed | non_inventory_product_id=%s',
            non_inventory_product_id,
        )


def _clean(value) -> str:
    return str(value or '').strip()


def _normalized_attribute_value(attributes, key) -> str:
    if not isinstance(attributes, dict):
        return ''
    return normalize_product_name(attributes.get(key) or attributes.get(key.lower()) or '')


def build_non_inventory_normalized_key(*, brand: str, canonical_name: str, attributes: dict | None) -> str:
    """Build a stable deterministic identity key for a non-inventory product.

    The key intentionally combines normalized product name with known product-defining
    attributes. It is conservative: missing attributes do not get guessed.
    """
    parts = [
        normalize_product_name(brand),
        normalize_product_name(canonical_name),
    ]
    attrs = attributes if isinstance(attributes, dict) else {}
    for key in IDENTITY_ATTRIBUTE_KEYS:
        val = _normalized_attribute_value(attrs, key)
        if val:
            parts.append(f'{normalize_product_name(key)}={val}')
    return '|'.join(part for part in parts if part)


def _source_message_for_inquiry(inquiry):
    source_link = (
        inquiry.inquiry_messages
        .select_related('message', 'message__account', 'message__contact')
        .order_by('message__message_time')
        .first()
    )
    return source_link.message if source_link else None


def _line_payload_from_inquiry_product(inquiry_product):
    return {
        'canonical_name': inquiry_product.canonical_name,
        'raw_text': inquiry_product.original_text,
        'brand': '',
        'attributes': {},
        'quantity': inquiry_product.quantity,
        'price': inquiry_product.price,
        'currency': inquiry_product.currency,
        'source_product_index': inquiry_product.source_product_index,
    }


def resolve_unmatched_inquiry_product(
    *,
    inquiry,
    line: dict | None = None,
    inquiry_product=None,
    source_message=None,
    match_source=None,
    match_confidence: float | None = 1.0,
    match_reason: str = '',
):
    """Find/create a canonical non-inventory product and record one mention.

    This deterministic phase only uses normalized keys. It does not perform embeddings,
    AI matching, or automatic live inquiry integration.
    """
    from apps.trading.models import (
        NonInventoryProduct,
        NonInventoryProductMatchSource,
        NonInventoryProductMention,
    )

    if not inquiry or not inquiry.pk:
        raise NonInventoryResolutionError('inquiry is required for non-inventory resolution')
    if not inquiry.company_id:
        raise NonInventoryResolutionError(f'missing inquiry company | inquiry_id={inquiry.pk}')

    payload = dict(line or {})
    if inquiry_product:
        payload = {**_line_payload_from_inquiry_product(inquiry_product), **payload}

    canonical_name = _clean(payload.get('canonical_name') or payload.get('raw_text'))
    if not canonical_name:
        raise NonInventoryResolutionError(
            f'blank non-inventory canonical name | inquiry_id={inquiry.pk} '
            f'| inquiry_product_id={getattr(inquiry_product, "pk", None)}'
        )

    attributes = payload.get('attributes') if isinstance(payload.get('attributes'), dict) else {}
    brand = _clean(payload.get('brand'))
    normalized_name = normalize_product_name(canonical_name)
    normalized_key = build_non_inventory_normalized_key(
        brand=brand,
        canonical_name=canonical_name,
        attributes=attributes,
    )
    if not normalized_key:
        raise NonInventoryResolutionError(
            f'blank non-inventory normalized key | inquiry_id={inquiry.pk} | canonical_name={canonical_name!r}'
        )

    source_message = source_message or getattr(inquiry_product, 'source_message', None) or _source_message_for_inquiry(inquiry)
    contact = inquiry.contact or getattr(inquiry_product, 'contact', None) or getattr(source_message, 'contact', None)
    company_contact = (
        getattr(inquiry_product, 'company_contact', None)
        or getattr(contact, 'company_contact', None)
    )
    source_product_index = payload.get('source_product_index')
    if source_product_index is None:
        source_product_index = getattr(inquiry_product, 'source_product_index', None)
    source_product_index = _as_int(
        source_product_index,
        field_name='source_product_index',
        inquiry_id=inquiry.pk,
        message_id=getattr(source_message, 'pk', None),
        index=source_product_index or 0,
    )
    match_source = match_source or NonInventoryProductMatchSource.DETERMINISTIC

    with transaction.atomic():
        product, created = NonInventoryProduct.objects.select_for_update().get_or_create(
            company=inquiry.company,
            normalized_key=normalized_key,
            defaults={
                'canonical_name': canonical_name,
                'normalized_name': normalized_name,
                'brand': brand,
                'attributes': attributes,
                'first_seen_at': inquiry.first_seen_at,
                'last_seen_at': inquiry.first_seen_at,
            },
        )

        mention_lookup = {
            'company': inquiry.company,
            'inquiry': inquiry,
            'source_product_index': source_product_index,
        }
        if inquiry_product:
            mention_lookup = {
                'company': inquiry.company,
                'inquiry_product': inquiry_product,
            }

        mention_defaults = {
                'non_inventory_product': product,
                'source_message': source_message,
                'account': inquiry.account or getattr(inquiry_product, 'account', None) or getattr(source_message, 'account', None),
                'contact': contact,
                'company_contact': company_contact,
                'inquiry_type': inquiry.inquiry_type,
                'source_product_index': source_product_index,
                'raw_text': _clean(payload.get('raw_text') or payload.get('original_text') or canonical_name),
                'canonical_name_from_ai': canonical_name,
                'normalized_name_from_ai': normalized_name,
                'brand_from_ai': brand,
                'attributes_from_ai': attributes,
                'quantity': _as_int(
                    payload.get('quantity'),
                    field_name='quantity',
                    inquiry_id=inquiry.pk,
                    message_id=getattr(source_message, 'pk', None),
                    index=source_product_index or 0,
                ),
                'price': _as_decimal(
                    payload.get('price'),
                    field_name='price',
                    inquiry_id=inquiry.pk,
                    message_id=getattr(source_message, 'pk', None),
                    index=source_product_index or 0,
                ),
                'currency': _clean(payload.get('currency')),
                'match_source': match_source,
                'match_confidence': match_confidence,
                'match_reason': match_reason or 'Matched by deterministic non-inventory normalized key.',
                'message_time': getattr(source_message, 'message_time', None) or inquiry.first_seen_at,
        }
        if inquiry_product:
            mention_defaults['inquiry'] = inquiry
        mention, mention_created = NonInventoryProductMention.objects.get_or_create(
            **mention_lookup,
            defaults=mention_defaults,
        )

        if not mention_created and mention.non_inventory_product_id != product.pk:
            raise NonInventoryResolutionError(
                f'non-inventory mention already linked to different product | '
                f'inquiry_id={inquiry.pk} | inquiry_product_id={getattr(inquiry_product, "pk", None)} '
                f'| existing_non_inventory_product_id={mention.non_inventory_product_id} '
                f'| resolved_non_inventory_product_id={product.pk}'
            )

        if mention_created:
            counter_updates = {
                'mention_count': F('mention_count') + 1,
                'last_seen_at': max(product.last_seen_at, inquiry.first_seen_at),
            }
            if inquiry.inquiry_type == 'buy':
                counter_updates['buy_mention_count'] = F('buy_mention_count') + 1
            elif inquiry.inquiry_type == 'sell':
                counter_updates['sell_mention_count'] = F('sell_mention_count') + 1
            NonInventoryProduct.objects.filter(pk=product.pk).update(**counter_updates)
            product.refresh_from_db()

        if created or product.embedding_status != 'embedded':
            transaction.on_commit(lambda product_id=product.pk: _embed_non_inventory_product_after_commit(product_id))

    logger.info(
        'resolve_unmatched_inquiry_product | done | inquiry_id=%s | inquiry_product_id=%s '
        '| non_inventory_product_id=%s | mention_id=%s | product_created=%s | mention_created=%s',
        inquiry.pk,
        getattr(inquiry_product, 'pk', None),
        product.pk,
        mention.pk,
        created,
        mention_created,
    )
    return product, mention
