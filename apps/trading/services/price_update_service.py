"""
Shared core for the Product Price Update page's two AI matching processes
(qty/cost, sale price) — used by both the manual paste-a-list flow
(apps.trading.views.ProductPriceUpdateViewSet) and the automated price-list
detection pipeline (apps.trading.services.price_update_automation), so the two
entry points never drift into two different matching/apply implementations.
"""
import json
import logging

logger = logging.getLogger(__name__)


def parse_against_inventory(text: str, prompt_key: str, prompt_default: str, company=None) -> list:
    """Runs the two-list AI match (supplier list vs. our own inventory) and returns
    the parsed items. Raises on any failure — callers decide how to surface it."""
    from apps.trading.services.product_cache import get_full_product_prompt_block
    from apps.trading.services.agent_logger import call_agent
    from apps.trading.models import PromptConfig

    product_block = get_full_product_prompt_block(company=company)
    system_prompt = PromptConfig.get_body(prompt_key, prompt_default, company=company).replace('{product_block}', product_block)

    raw = call_agent(
        prompt_key,
        [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user',   'content': text},
        ],
        temperature=0,
    )
    cleaned = raw.strip()
    if cleaned.startswith('```'):
        cleaned = cleaned.split('\n', 1)[-1].rsplit('```', 1)[0]
    items = json.loads(cleaned)
    if not isinstance(items, list):
        raise ValueError('AI did not return a list')
    return items


def _match_product(item: dict, company=None):
    """Resolve one parsed item to a Product: by product_id first, then by exact
    (case-insensitive) name among active products. Returns (product_or_None, name)."""
    from apps.trading.models import Product

    product_id = item.get('product_id')
    name = (item.get('canonical_name') or '').strip()

    product = None
    if product_id:
        product = Product.objects.filter(pk=product_id, company=company).first()
    if not product and name:
        product = Product.objects.filter(name__iexact=name, is_active=True, company=company).first()
    return product, name


def preview_zero_candidates(items: list, company=None) -> dict:
    """Dry-run companion to apply_items_to_inventory(zero_unmatched_qty=True) —
    resolves which active, currently-nonzero-qty products would be zeroed by this
    exact item list, without writing anything. Lets the UI show a confirmation
    count before an apply that would zero stock."""
    from apps.trading.models import Product

    matched_ids = {product.pk for item in items if (product := _match_product(item, company=company)[0])}
    missing = list(
        Product.objects.filter(is_active=True, company=company).exclude(pk__in=matched_ids).exclude(qty=0)
        .order_by('name').values('id', 'name', 'qty')
    )
    return {'count': len(missing), 'products': missing}


def apply_items_to_inventory(items: list, fields: list, zero_unmatched_qty: bool = False, company=None) -> dict:
    """Writes parsed items back onto Product rows. `fields` is a list of
    (payload_key, product_attr) pairs to copy across when present, e.g.
    [('qty', 'qty'), ('cost_price', 'cost_price')] or [('sale_price', 'sale_price')].

    `zero_unmatched_qty`: when True, every active product NOT among the matched
    items has its qty set to 0 — the qty/cost list is a supplier's current stock,
    so anything we hold that they didn't list is no longer available from them.
    Only meaningful for the qty/cost process; sale-price updates never zero stock.

    Returns {'updated': [...], 'skipped': [name-or-id strings], 'zeroed': [...]}."""
    from apps.trading.serializers import ProductSerializer
    from apps.trading.services.product_cache import invalidate as invalidate_product_cache

    updated, skipped = [], []
    matched_ids = set()

    for item in items:
        product, name = _match_product(item, company=company)
        if not product:
            skipped.append(name or str(item.get('product_id')))
            continue

        matched_ids.add(product.pk)
        update_fields = ['updated_at']
        for payload_key, product_attr in fields:
            value = item.get(payload_key)
            if value is not None:
                setattr(product, product_attr, value)
                update_fields.append(product_attr)
        currency = (item.get('currency') or '').strip()
        if currency:
            product.currency = currency
            update_fields.append('currency')

        product.save(update_fields=update_fields)
        updated.append(ProductSerializer(product).data)

    zeroed = []
    if zero_unmatched_qty:
        from apps.trading.models import Product
        missing = Product.objects.filter(is_active=True, company=company).exclude(pk__in=matched_ids).exclude(qty=0)
        for product in missing:
            product.qty = 0
            product.save(update_fields=['qty', 'updated_at'])
            zeroed.append(ProductSerializer(product).data)

    if updated or zeroed:
        invalidate_product_cache()
    return {'updated': updated, 'skipped': skipped, 'zeroed': zeroed}
