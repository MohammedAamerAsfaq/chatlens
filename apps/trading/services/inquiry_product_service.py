import logging
import re
import threading
from decimal import Decimal, InvalidOperation

logger = logging.getLogger(__name__)


class InquiryProductMaterializationError(Exception):
    """Raised when parsed inquiry products cannot be persisted."""


def normalize_product_name(value: str) -> str:
    text = (value or '').lower()
    text = re.sub(r'[^a-z0-9]+', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def _as_int(value, *, field_name, inquiry_id, message_id, index):
    if value in (None, ''):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        raise InquiryProductMaterializationError(
            f'invalid integer field {field_name!r} | inquiry_id={inquiry_id} '
            f'| message_id={message_id} | index={index} | value={value!r}'
        )


def _as_decimal(value, *, field_name, inquiry_id, message_id, index):
    if value in (None, ''):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise InquiryProductMaterializationError(
            f'invalid decimal field {field_name!r} | inquiry_id={inquiry_id} '
            f'| message_id={message_id} | index={index} | value={value!r}'
        )


def _resolve_product(company, product_id):
    if not product_id or not company:
        return None
    from apps.trading.models import Product

    return Product.objects.filter(pk=product_id, company=company).first()


def _embed_unmapped_inquiry_products_in_background(inquiry_product_ids: list[int]) -> None:
    if not inquiry_product_ids:
        return

    def _run():
        from django.db import connection
        try:
            from apps.message_intelligence.services.embedding_service import embed_inquiry_products_batch
            embed_inquiry_products_batch(inquiry_product_ids)
        except Exception:
            logger.exception(
                'inquiry_product_service | unmapped embedding failed | inquiry_product_ids=%s',
                inquiry_product_ids,
            )
        finally:
            connection.close()

    threading.Thread(target=_run, daemon=True).start()


def _status_for_line(product, match_type):
    from apps.trading.models import (
        InquiryProductDecisionStatus,
        InquiryProductMatchSource,
        InquiryProductMatchStatus,
    )

    if product and match_type == 'exact':
        in_stock = (product.qty or 0) > 0
        availability = 'in stock' if in_stock else 'out of stock'
        return {
            'decision_status': InquiryProductDecisionStatus.MAPPED,
            'match_status': InquiryProductMatchStatus.EXACT,
            'match_source': InquiryProductMatchSource.AI,
            'match_reason': f'AI returned an exact product_id match; inventory item is {availability}.',
        }
    if product and match_type == 'near':
        return {
            'decision_status': InquiryProductDecisionStatus.PENDING,
            'match_status': InquiryProductMatchStatus.NEAR,
            'match_source': InquiryProductMatchSource.AI,
            'match_reason': 'AI returned a near product_id match; user review is required.',
        }
    return {
        'decision_status': InquiryProductDecisionStatus.PENDING,
        'match_status': InquiryProductMatchStatus.UNMATCHED,
        'match_source': InquiryProductMatchSource.AI,
        'match_reason': 'AI did not return a usable inventory product match.',
    }


def _stock_snapshot(product):
    from apps.trading.models import InquiryProductStockStatus

    if not product:
        return {
            'product_qty_at_match': None,
            'product_stock_status_at_match': InquiryProductStockStatus.UNKNOWN,
        }

    qty = product.qty or 0
    return {
        'product_qty_at_match': qty,
        'product_stock_status_at_match': (
            InquiryProductStockStatus.IN_STOCK
            if qty > 0
            else InquiryProductStockStatus.OUT_OF_STOCK
        ),
    }


def create_inquiry_products_for_message(inquiry, message, products, *, exact_matches_only: bool = False) -> int:
    """Persist structured product mention rows for one inquiry/message pair.

    The legacy Inquiry.products JSON remains untouched. This service is additive and
    idempotent by lookup: if the same inquiry/message/index already exists, it updates
    the row instead of creating a duplicate. When exact_matches_only=True, only lines
    with a valid exact product_id match are persisted.
    """
    from apps.trading.models import InquiryProduct

    message_id = getattr(message, 'pk', None)

    if not inquiry.company_id:
        raise InquiryProductMaterializationError(
            f'missing inquiry company | inquiry_id={inquiry.pk} | message_id={message_id}'
        )

    if not isinstance(products, list):
        raise InquiryProductMaterializationError(
            f'products is not list | inquiry_id={inquiry.pk} | message_id={message_id} '
            f'| type={type(products).__name__}'
        )

    if not products:
        raise InquiryProductMaterializationError(
            f'products list is empty | inquiry_id={inquiry.pk} | message_id={message_id}'
        )

    created_or_updated = 0
    unmapped_embedding_ids = []
    contact = inquiry.contact or getattr(message, 'contact', None)
    company_contact = contact.company_contact if contact else None

    for index, line in enumerate(products):
        if not isinstance(line, dict):
            raise InquiryProductMaterializationError(
                f'product line is not dict | inquiry_id={inquiry.pk} '
                f'| message_id={message_id} | index={index} | type={type(line).__name__}'
            )

        product_id = line.get('product_id')
        match_type = line.get('match_type') or ''
        product = _resolve_product(inquiry.company, product_id)
        if exact_matches_only and (not product or match_type != 'exact'):
            continue

        canonical_name = str(line.get('canonical_name') or '').strip()
        if not canonical_name:
            raise InquiryProductMaterializationError(
                f'blank canonical_name | inquiry_id={inquiry.pk} '
                f'| message_id={message_id} | index={index} | line={line!r}'
            )

        status_values = _status_for_line(product, match_type)
        if product_id and not product:
            status_values['match_reason'] = (
                f'AI returned product_id={product_id}, but no product in this company matched it.'
            )
        stock_snapshot = _stock_snapshot(product)

        defaults = {
            'company': inquiry.company,
            'account': inquiry.account or getattr(message, 'account', None),
            'contact': contact,
            'company_contact': company_contact,
            'product': product,
            'inquiry_type': inquiry.inquiry_type,
            'canonical_name': canonical_name,
            'normalized_name': normalize_product_name(canonical_name),
            'original_text': '',
            'quantity': _as_int(
                line.get('quantity'),
                field_name='quantity',
                inquiry_id=inquiry.pk,
                message_id=message_id,
                index=index,
            ),
            'price': _as_decimal(
                line.get('price'),
                field_name='price',
                inquiry_id=inquiry.pk,
                message_id=message_id,
                index=index,
            ),
            'currency': str(line.get('currency') or ''),
            'match_type': match_type if match_type in ('exact', 'near') else '',
            **stock_snapshot,
            'embedding': None if product else None,
            'embedding_model': '',
            'embedding_metadata': {'source': 'inventory_product_embedding'} if product else None,
            'embedding_status': 'skipped' if product else 'pending',
            'embedding_error': '',
            'first_seen_at': inquiry.first_seen_at,
            **status_values,
        }

        row, _ = InquiryProduct.objects.update_or_create(
            inquiry=inquiry,
            source_message=message,
            source_product_index=index,
            defaults=defaults,
        )
        if not product:
            unmapped_embedding_ids.append(row.pk)
        created_or_updated += 1

    if created_or_updated:
        logger.info(
            'create_inquiry_products_for_message | done | inquiry_id=%s | message_id=%s | rows=%s',
            inquiry.pk,
            message_id,
            created_or_updated,
        )
    _embed_unmapped_inquiry_products_in_background(unmapped_embedding_ids)
    return created_or_updated


def create_manual_product_from_inquiry_line(inquiry, line_index: int, *, created_by=None, overrides=None):
    """Create an inventory Product and one InquiryProduct trace row from a single
    parsed Inquiry.products line. This is the manual path used by the inquiry UI.
    """
    from django.db import transaction
    from apps.trading.models import (
        InquiryProduct,
        InquiryProductDecisionStatus,
        InquiryProductMatchSource,
        InquiryProductMatchStatus,
        Product,
        ProductAttribute,
    )

    overrides = overrides or {}
    products = inquiry.products or []
    try:
        line_index = int(line_index)
        line = products[line_index]
    except (TypeError, ValueError, IndexError):
        raise InquiryProductMaterializationError(
            f'invalid product line index | inquiry_id={inquiry.pk} | index={line_index!r}'
        )
    if not isinstance(line, dict):
        raise InquiryProductMaterializationError(
            f'product line is not dict | inquiry_id={inquiry.pk} | index={line_index}'
        )

    existing_trace = InquiryProduct.objects.filter(
        inquiry=inquiry,
        source_product_index=line_index,
    ).first()
    if existing_trace:
        raise InquiryProductMaterializationError(
            f'inquiry product already exists | inquiry_id={inquiry.pk} '
            f'| index={line_index} | inquiry_product_id={existing_trace.pk}'
        )

    canonical_name = str(overrides.get('name') or line.get('canonical_name') or '').strip()
    if not canonical_name:
        raise InquiryProductMaterializationError(
            f'blank product name | inquiry_id={inquiry.pk} | index={line_index}'
        )
    if not inquiry.company_id:
        raise InquiryProductMaterializationError(
            f'missing inquiry company | inquiry_id={inquiry.pk} | index={line_index}'
        )

    source_link = (
        inquiry.inquiry_messages
        .select_related('message', 'message__account', 'message__contact')
        .order_by('message__message_time')
        .first()
    )
    source_message = source_link.message if source_link else None
    contact = inquiry.contact or getattr(source_message, 'contact', None)
    company_contact = contact.company_contact if contact else None

    with transaction.atomic():
        product = Product.objects.create(
            company=inquiry.company,
            name=canonical_name,
            brand=str(overrides.get('brand') or line.get('brand') or '').strip(),
            category=str(overrides.get('category') or '').strip(),
            sku=str(overrides.get('sku') or '').strip(),
            qty=0,
            currency=str(overrides.get('currency') or line.get('currency') or 'USD').strip() or 'USD',
        )

        line['product_id'] = product.pk
        line['match_type'] = 'exact'
        line['brand'] = product.brand
        line['manually_created_product'] = True
        attributes = line.get('attributes') or {}
        if isinstance(attributes, dict):
            for key, value in attributes.items():
                key = str(key or '').strip()
                value = str(value or '').strip()
                if key and value:
                    ProductAttribute.objects.update_or_create(
                        product=product,
                        key=key,
                        defaults={'value': value},
                    )
        inquiry.products = products
        inquiry.save(update_fields=['products', 'updated_at'])

        trace = InquiryProduct.objects.create(
            company=inquiry.company,
            inquiry=inquiry,
            source_message=source_message,
            account=inquiry.account or getattr(source_message, 'account', None),
            contact=contact,
            company_contact=company_contact,
            product=product,
            inquiry_type=inquiry.inquiry_type,
            source_product_index=line_index,
            canonical_name=canonical_name,
            normalized_name=normalize_product_name(canonical_name),
            original_text=str(line.get('canonical_name') or ''),
            quantity=_as_int(
                line.get('quantity'),
                field_name='quantity',
                inquiry_id=inquiry.pk,
                message_id=getattr(source_message, 'pk', None),
                index=line_index,
            ),
            price=_as_decimal(
                line.get('price'),
                field_name='price',
                inquiry_id=inquiry.pk,
                message_id=getattr(source_message, 'pk', None),
                index=line_index,
            ),
            currency=str(line.get('currency') or ''),
            decision_status=InquiryProductDecisionStatus.CREATED,
            match_status=InquiryProductMatchStatus.MANUAL_CONFIRMED,
            match_type='exact',
            match_source=InquiryProductMatchSource.MANUAL,
            match_reason=(
                f'Manually created inventory product from inquiry line by '
                f'{getattr(created_by, "username", "") or "user"}.'
            ),
            **_stock_snapshot(product),
            embedding_status='skipped',
            first_seen_at=inquiry.first_seen_at,
        )

    logger.info(
        'create_manual_product_from_inquiry_line | created | inquiry_id=%s | index=%s | product_id=%s | trace_id=%s',
        inquiry.pk,
        line_index,
        product.pk,
        trace.pk,
    )
    return product, trace


def create_manual_inquiry_product_from_matched_line(inquiry, line_index: int, *, created_by=None):
    """Persist a trace row for an inquiry line that is already mapped to inventory.

    This is the manual "Create Inquiry" path from stock suggestions. It does not create
    inventory. It only records that this inquiry line mentions the selected product.
    """
    from django.db import transaction
    from apps.trading.models import (
        InquiryProduct,
        InquiryProductDecisionStatus,
        InquiryProductMatchSource,
        InquiryProductMatchStatus,
    )

    products = inquiry.products or []
    try:
        line_index = int(line_index)
        line = products[line_index]
    except (TypeError, ValueError, IndexError):
        raise InquiryProductMaterializationError(
            f'invalid product line index | inquiry_id={inquiry.pk} | index={line_index!r}'
        )
    if not isinstance(line, dict):
        raise InquiryProductMaterializationError(
            f'product line is not dict | inquiry_id={inquiry.pk} | index={line_index}'
        )
    if not inquiry.company_id:
        raise InquiryProductMaterializationError(
            f'missing inquiry company | inquiry_id={inquiry.pk} | index={line_index}'
        )

    product = _resolve_product(inquiry.company, line.get('product_id'))
    if not product:
        raise InquiryProductMaterializationError(
            f'product line has no valid company inventory mapping | inquiry_id={inquiry.pk} '
            f'| index={line_index} | product_id={line.get("product_id")!r}'
        )

    source_link = (
        inquiry.inquiry_messages
        .select_related('message', 'message__account', 'message__contact')
        .order_by('message__message_time')
        .first()
    )
    source_message = source_link.message if source_link else None
    contact = inquiry.contact or getattr(source_message, 'contact', None)
    company_contact = contact.company_contact if contact else None
    canonical_name = str(line.get('canonical_name') or product.name or '').strip()
    if not canonical_name:
        raise InquiryProductMaterializationError(
            f'blank product name | inquiry_id={inquiry.pk} | index={line_index}'
        )

    with transaction.atomic():
        existing_trace = InquiryProduct.objects.filter(
            inquiry=inquiry,
            source_product_index=line_index,
        ).first()
        if existing_trace and existing_trace.product_id and existing_trace.product_id != product.pk:
            raise InquiryProductMaterializationError(
                f'inquiry product line already mapped to a different product | inquiry_id={inquiry.pk} '
                f'| index={line_index} | existing_product_id={existing_trace.product_id} '
                f'| requested_product_id={product.pk}'
            )

        line['product_id'] = product.pk
        line['match_type'] = 'exact'
        line['manually_created_inquiry_product'] = True
        inquiry.products = products
        inquiry.save(update_fields=['products', 'updated_at'])

        defaults = {
            'company': inquiry.company,
            'source_message': source_message,
            'account': inquiry.account or getattr(source_message, 'account', None),
            'contact': contact,
            'company_contact': company_contact,
            'product': product,
            'inquiry_type': inquiry.inquiry_type,
            'canonical_name': canonical_name,
            'normalized_name': normalize_product_name(canonical_name),
            'original_text': str(line.get('raw_text') or line.get('canonical_name') or ''),
            'quantity': _as_int(
                line.get('quantity'),
                field_name='quantity',
                inquiry_id=inquiry.pk,
                message_id=getattr(source_message, 'pk', None),
                index=line_index,
            ),
            'price': _as_decimal(
                line.get('price'),
                field_name='price',
                inquiry_id=inquiry.pk,
                message_id=getattr(source_message, 'pk', None),
                index=line_index,
            ),
            'currency': str(line.get('currency') or ''),
            'decision_status': InquiryProductDecisionStatus.MAPPED,
            'match_status': InquiryProductMatchStatus.MANUAL_CONFIRMED,
            'match_type': 'exact',
            'match_source': InquiryProductMatchSource.MANUAL,
            'match_reason': (
                f'Manually saved inquiry product from stock suggestion by '
                f'{getattr(created_by, "username", "") or "user"}.'
            ),
            **_stock_snapshot(product),
            'embedding_status': 'skipped',
            'first_seen_at': inquiry.first_seen_at,
        }
        if existing_trace:
            for field, value in defaults.items():
                setattr(existing_trace, field, value)
            existing_trace.save()
            trace = existing_trace
        else:
            trace = InquiryProduct.objects.create(
                inquiry=inquiry,
                source_product_index=line_index,
                **defaults,
            )

    logger.info(
        'create_manual_inquiry_product_from_matched_line | saved | inquiry_id=%s | index=%s | product_id=%s | trace_id=%s',
        inquiry.pk,
        line_index,
        product.pk,
        trace.pk,
    )
    return trace
