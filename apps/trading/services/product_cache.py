import logging
import threading

logger = logging.getLogger(__name__)

_lock  = threading.Lock()
_cache = {}

def _company_cache_key(company) -> str:
    return str(company.pk) if company else 'none'


def get_product_prompt_block(company=None) -> str:
    """Return a compact product list string for AI prompt injection.

    Built from the active product catalogue and cached in-process.
    Call invalidate() after any product create/update/delete to force a rebuild
    on the next classification call.
    """
    cache_key = _company_cache_key(company)
    with _lock:
        if cache_key in _cache:
            return _cache[cache_key]

        from apps.trading.models import Product
        products_qs = Product.objects.filter(is_active=True, qty__gt=0)
        if company:
            products_qs = products_qs.filter(company=company)
        else:
            products_qs = products_qs.none()

        products = list(
            products_qs
            .prefetch_related('alias_set')
            .order_by('brand', 'name')
        )

        if not products:
            _cache[cache_key] = '(no products configured)'
            return _cache[cache_key]

        lines = []
        for p in products:
            brand_part = f'[{p.brand}] ' if p.brand else ''
            line = f'ID:{p.pk}  {brand_part}{p.name}'
            aliases = [a.alias for a in p.alias_set.all()]
            if aliases:
                line += f'  (also known as: {", ".join(aliases)})'
            lines.append(line)

        _cache[cache_key] = '\n'.join(lines)
        logger.debug('product_cache | rebuilt | products=%d', len(products))
        return _cache[cache_key]


def invalidate():
    """Invalidate the cached product block. Called when products change."""
    with _lock:
        _cache.clear()
    logger.debug('product_cache | invalidated')


def get_full_product_prompt_block(company=None) -> str:
    """Same shape as get_product_prompt_block() but WITHOUT the qty>0 filter — every
    active product regardless of current stock level. Used by the Product Price
    Update page's qty/cost and sale-price matching (ProductPriceUpdateViewSet),
    where excluding zero-stock items would be self-defeating: restocking a
    currently-zero-qty item (the whole point of a qty update) requires that item to
    be a visible match candidate in the first place. Confirmed this mattered in
    practice — a real product sitting at qty=0 came back "unmatched" from the AI
    purely because get_product_prompt_block()'s qty__gt=0 filter hid it, not because
    of any actual name-matching failure.

    Deliberately uncached (unlike get_product_prompt_block) — invoked on-demand when
    a human pastes a list, not on the live per-message classification hot path, so
    the caching tradeoff that's worth it there doesn't apply here.
    """
    from apps.trading.models import Product
    products_qs = Product.objects.filter(is_active=True)
    if company:
        products_qs = products_qs.filter(company=company)
    else:
        products_qs = products_qs.none()
    products = list(
        products_qs
        .prefetch_related('alias_set')
        .order_by('brand', 'name')
    )
    if not products:
        return '(no products configured)'

    lines = []
    for p in products:
        brand_part = f'[{p.brand}] ' if p.brand else ''
        line = f'ID:{p.pk}  {brand_part}{p.name}'
        aliases = [a.alias for a in p.alias_set.all()]
        if aliases:
            line += f'  (also known as: {", ".join(aliases)})'
        lines.append(line)
    return '\n'.join(lines)
