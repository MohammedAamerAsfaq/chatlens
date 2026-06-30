import logging
import threading

logger = logging.getLogger(__name__)

_lock  = threading.Lock()
_cache = {'block': None}


def get_product_prompt_block() -> str:
    """Return a compact product list string for AI prompt injection.

    Built from the active product catalogue and cached in-process.
    Call invalidate() after any product create/update/delete to force a rebuild
    on the next classification call.
    """
    with _lock:
        if _cache['block'] is not None:
            return _cache['block']

        from apps.trading.models import Product
        products = list(Product.objects.filter(is_active=True).order_by('brand', 'name'))

        if not products:
            _cache['block'] = '(no products configured)'
            return _cache['block']

        lines = []
        for p in products:
            aliases_str = ', '.join(p.aliases) if p.aliases else 'none'
            brand_part  = f'[{p.brand}] ' if p.brand else ''
            lines.append(f'ID:{p.pk}  {brand_part}{p.name}  →  aliases: {aliases_str}')

        _cache['block'] = '\n'.join(lines)
        logger.debug('product_cache | rebuilt | products=%d', len(products))
        return _cache['block']


def invalidate():
    """Invalidate the cached product block. Called when products change."""
    with _lock:
        _cache['block'] = None
    logger.debug('product_cache | invalidated')
