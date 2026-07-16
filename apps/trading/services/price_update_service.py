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


def parse_against_inventory(text: str, prompt_key: str, prompt_default: str) -> list:
    """Runs the two-list AI match (supplier list vs. our own inventory) and returns
    the parsed items. Raises on any failure — callers decide how to surface it."""
    from apps.trading.services.product_cache import get_full_product_prompt_block
    from apps.trading.services.agent_logger import call_agent
    from apps.trading.models import PromptConfig

    product_block = get_full_product_prompt_block()
    system_prompt = PromptConfig.get_body(prompt_key, prompt_default).replace('{product_block}', product_block)

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


def apply_items_to_inventory(items: list, fields: list) -> dict:
    """Writes parsed items back onto Product rows. `fields` is a list of
    (payload_key, product_attr) pairs to copy across when present, e.g.
    [('qty', 'qty'), ('cost_price', 'cost_price')] or [('sale_price', 'sale_price')].
    Returns {'updated': [ProductSerializer dicts], 'skipped': [name-or-id strings]}."""
    from apps.trading.models import Product
    from apps.trading.serializers import ProductSerializer
    from apps.trading.services.product_cache import invalidate as invalidate_product_cache

    updated, skipped = [], []

    for item in items:
        product_id = item.get('product_id')
        name = (item.get('canonical_name') or '').strip()

        product = None
        if product_id:
            product = Product.objects.filter(pk=product_id).first()
        if not product and name:
            product = Product.objects.filter(name__iexact=name, is_active=True).first()
        if not product:
            skipped.append(name or str(product_id))
            continue

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

    if updated:
        invalidate_product_cache()
    return {'updated': updated, 'skipped': skipped}
