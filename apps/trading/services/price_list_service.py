import logging

from django.utils.timezone import now

logger = logging.getLogger(__name__)


def _build_product_block(company) -> str:
    from apps.trading.models import Product

    products = (
        Product.objects.filter(company=company, is_active=True, qty__gt=0, sale_price__isnull=False)
        .order_by('brand', 'category', 'name')
    )
    lines = []
    for p in products:
        brand_part = f'{p.brand} ' if p.brand else ''
        lines.append(
            f'{brand_part}{p.name} | category: {p.category or "—"} | qty: {p.qty} | '
            f'price: {p.currency or "USD"} {p.sale_price}'
        )
    return '\n'.join(lines) if lines else '(no in-stock priced products)'


def generate_price_list(company):
    """
    Call the agent to reformat the current in-stock, priced catalog per the
    'price_list_format' prompt, and persist the result as the singleton
    FormattedPriceList row. Raises on failure — callers decide how to surface it.
    """
    from apps.trading.models import PromptConfig, PRICE_LIST_FORMAT_DEFAULT, FormattedPriceList
    from apps.trading.services.agent_logger import call_agent

    product_block = _build_product_block(company)
    system_prompt = PromptConfig.get_body(
        PromptConfig.KEY_PRICE_LIST_FORMAT,
        PRICE_LIST_FORMAT_DEFAULT,
        company=company,
    )

    raw = call_agent(
        PromptConfig.KEY_PRICE_LIST_FORMAT,
        [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user',   'content': f'Format this price list:\n{product_block}'},
        ],
        temperature=0,
    )

    body = raw.strip()
    if body.startswith('```'):
        body = body.split('\n', 1)[-1].rsplit('```', 1)[0].strip()

    obj, _ = FormattedPriceList.objects.update_or_create(
        company=company,
        defaults={'body': body, 'generated_at': now()},
    )
    logger.info('generate_price_list | done | chars=%d', len(body))
    return obj
