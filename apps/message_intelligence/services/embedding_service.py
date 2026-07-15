import logging
from django.conf import settings

logger = logging.getLogger(__name__)

BATCH_SIZE = getattr(settings, 'EMBEDDING_BATCH_SIZE', 128)


def _build_text(message) -> str:
    """Compose the text we embed for a given WhatsAppMessage."""
    parts = []
    if message.message_text:
        parts.append(message.message_text)
    # Future: append transcribed audio, OCR'd image text, etc.
    return ' '.join(parts).strip()


def embed_message(message_id: int) -> bool:
    """Generate and store an embedding for a single message. Returns True if stored."""
    from apps.whatsapp_bridge.models import WhatsAppMessage
    from apps.message_intelligence.models import MessageEmbedding
    from apps.ai_providers.manager import ai_manager

    message = WhatsAppMessage.objects.get(pk=message_id)
    text = _build_text(message)
    if not text:
        logger.debug('embed_message | skip (no text) | message_id=%s', message_id)
        return False

    config = ai_manager.active_config('embedding')
    if config is None:
        logger.warning('embed_message | no active embedding provider configured')
        return False

    vector = ai_manager.embed(text)

    MessageEmbedding.objects.update_or_create(
        message=message,
        defaults={
            'embedding': vector,
            'embedding_model': config.model,
            'metadata': {'provider': config.provider, 'dimensions': len(vector)},
        },
    )
    logger.info('embed_message | stored | message_id=%s | dims=%s', message_id, len(vector))
    return True


def embed_messages_batch(message_ids: list[int]) -> dict:
    """Embed a list of messages in provider-side batches. Returns counts."""
    from apps.whatsapp_bridge.models import WhatsAppMessage
    from apps.message_intelligence.models import MessageEmbedding
    from apps.ai_providers.manager import ai_manager

    config = ai_manager.active_config('embedding')
    if config is None:
        logger.warning('embed_messages_batch | no active embedding provider')
        return {'total': len(message_ids), 'embedded': 0, 'skipped': 0, 'errors': 0}

    messages = list(WhatsAppMessage.objects.filter(pk__in=message_ids))
    pending = [(m, _build_text(m)) for m in messages]
    to_embed = [(m, t) for m, t in pending if t]
    skipped = len(pending) - len(to_embed)

    embedded = errors = 0

    for i in range(0, len(to_embed), BATCH_SIZE):
        chunk = to_embed[i:i + BATCH_SIZE]
        texts = [t for _, t in chunk]
        try:
            vectors = ai_manager.embed_batch(texts)
        except Exception:
            logger.exception('embed_messages_batch | provider error | chunk_start=%s', i)
            errors += len(chunk)
            continue

        objs = []
        for (message, _), vector in zip(chunk, vectors):
            objs.append(MessageEmbedding(
                message=message,
                embedding=vector,
                embedding_model=config.model,
                metadata={'provider': config.provider, 'dimensions': len(vector)},
            ))

        MessageEmbedding.objects.bulk_create(
            objs,
            update_conflicts=True,
            update_fields=['embedding', 'embedding_model', 'metadata'],
            unique_fields=['message'],
        )
        embedded += len(chunk)

    logger.info(
        'embed_messages_batch | done | total=%s embedded=%s skipped=%s errors=%s',
        len(message_ids), embedded, skipped, errors,
    )
    return {'total': len(message_ids), 'embedded': embedded, 'skipped': skipped, 'errors': errors}


def _build_product_text(product) -> str:
    """Compose the text we embed for a given Product's own name — same signal the AI
    already reads off the plain-text product master block, so retrieval and prompt
    injection stay consistent with each other. Aliases are NOT folded in here anymore —
    each one gets its own embedding (see _build_alias_text/embed_product_alias) so a
    query is compared against every individual phrasing, not one vector averaged across
    all of them, which is what actually helps when the same product gets typed
    differently in every inquiry."""
    parts = [product.brand, product.name]
    return ' '.join(p for p in parts if p).strip()


def _build_alias_text(product_alias) -> str:
    """Compose the text we embed for a single ProductAlias — the product's own brand +
    name, followed by the alias. Still one vector per alias (multi-vector retrieval is
    unchanged: a query is compared against every phrasing independently, best one wins),
    but a bare short alias like "jp" embeds almost meaninglessly on its own — too little
    text for the model to anchor a vector to. Giving it its product's context means the
    vector represents "this specific product, referred to this way" instead of a
    near-empty string floating alone in embedding space, without needing to know or
    special-case what the alias means (region code, color shorthand, submodel, etc.)."""
    product = product_alias.product
    parts = [product.brand, product.name, product_alias.alias]
    return ' '.join(p for p in parts if p).strip()


def embed_product(product_id: int) -> bool:
    """Generate and store an embedding for a single product. Returns True if stored."""
    from apps.trading.models import Product
    from apps.message_intelligence.models import ProductEmbedding
    from apps.ai_providers.manager import ai_manager

    product = Product.objects.get(pk=product_id)
    text = _build_product_text(product)
    if not text:
        logger.debug('embed_product | skip (no text) | product_id=%s', product_id)
        return False

    config = ai_manager.active_config('embedding')
    if config is None:
        logger.warning('embed_product | no active embedding provider configured')
        return False

    vector = ai_manager.embed(text)

    ProductEmbedding.objects.update_or_create(
        product=product,
        defaults={
            'embedding': vector,
            'embedding_model': config.model,
            'metadata': {'provider': config.provider, 'dimensions': len(vector)},
        },
    )
    logger.info('embed_product | stored | product_id=%s | dims=%s', product_id, len(vector))
    return True


def embed_products_batch(product_ids: list[int]) -> dict:
    """Embed a list of products in provider-side batches. Returns counts."""
    from apps.trading.models import Product
    from apps.message_intelligence.models import ProductEmbedding
    from apps.ai_providers.manager import ai_manager

    config = ai_manager.active_config('embedding')
    if config is None:
        logger.warning('embed_products_batch | no active embedding provider')
        return {'total': len(product_ids), 'embedded': 0, 'skipped': 0, 'errors': 0}

    products = list(Product.objects.filter(pk__in=product_ids))
    pending = [(p, _build_product_text(p)) for p in products]
    to_embed = [(p, t) for p, t in pending if t]
    skipped = len(pending) - len(to_embed)

    embedded = errors = 0

    for i in range(0, len(to_embed), BATCH_SIZE):
        chunk = to_embed[i:i + BATCH_SIZE]
        texts = [t for _, t in chunk]
        try:
            vectors = ai_manager.embed_batch(texts)
        except Exception:
            logger.exception('embed_products_batch | provider error | chunk_start=%s', i)
            errors += len(chunk)
            continue

        objs = []
        for (product, _), vector in zip(chunk, vectors):
            objs.append(ProductEmbedding(
                product=product,
                embedding=vector,
                embedding_model=config.model,
                metadata={'provider': config.provider, 'dimensions': len(vector)},
            ))

        ProductEmbedding.objects.bulk_create(
            objs,
            update_conflicts=True,
            update_fields=['embedding', 'embedding_model', 'metadata'],
            unique_fields=['product'],
        )
        embedded += len(chunk)

    logger.info(
        'embed_products_batch | done | total=%s embedded=%s skipped=%s errors=%s',
        len(product_ids), embedded, skipped, errors,
    )
    return {'total': len(product_ids), 'embedded': embedded, 'skipped': skipped, 'errors': errors}


def embed_product_alias(alias_id: int) -> bool:
    """Generate and store an embedding for a single ProductAlias. Returns True if stored."""
    from apps.trading.models import ProductAlias
    from apps.message_intelligence.models import ProductAliasEmbedding
    from apps.ai_providers.manager import ai_manager

    alias = ProductAlias.objects.select_related('product').get(pk=alias_id)
    text = _build_alias_text(alias)
    if not text:
        logger.debug('embed_product_alias | skip (no text) | alias_id=%s', alias_id)
        return False

    config = ai_manager.active_config('embedding')
    if config is None:
        logger.warning('embed_product_alias | no active embedding provider configured')
        return False

    vector = ai_manager.embed(text)

    ProductAliasEmbedding.objects.update_or_create(
        alias=alias,
        defaults={
            'embedding': vector,
            'embedding_model': config.model,
            'metadata': {'provider': config.provider, 'dimensions': len(vector)},
        },
    )
    logger.info('embed_product_alias | stored | alias_id=%s | dims=%s', alias_id, len(vector))
    return True


def embed_product_aliases_batch(alias_ids: list[int]) -> dict:
    """Embed a list of ProductAlias rows in provider-side batches. Returns counts."""
    from apps.trading.models import ProductAlias
    from apps.message_intelligence.models import ProductAliasEmbedding
    from apps.ai_providers.manager import ai_manager

    config = ai_manager.active_config('embedding')
    if config is None:
        logger.warning('embed_product_aliases_batch | no active embedding provider')
        return {'total': len(alias_ids), 'embedded': 0, 'skipped': 0, 'errors': 0}

    aliases = list(ProductAlias.objects.select_related('product').filter(pk__in=alias_ids))
    pending = [(a, _build_alias_text(a)) for a in aliases]
    to_embed = [(a, t) for a, t in pending if t]
    skipped = len(pending) - len(to_embed)

    embedded = errors = 0

    for i in range(0, len(to_embed), BATCH_SIZE):
        chunk = to_embed[i:i + BATCH_SIZE]
        texts = [t for _, t in chunk]
        try:
            vectors = ai_manager.embed_batch(texts)
        except Exception:
            logger.exception('embed_product_aliases_batch | provider error | chunk_start=%s', i)
            errors += len(chunk)
            continue

        objs = []
        for (alias, _), vector in zip(chunk, vectors):
            objs.append(ProductAliasEmbedding(
                alias=alias,
                embedding=vector,
                embedding_model=config.model,
                metadata={'provider': config.provider, 'dimensions': len(vector)},
            ))

        ProductAliasEmbedding.objects.bulk_create(
            objs,
            update_conflicts=True,
            update_fields=['embedding', 'embedding_model', 'metadata'],
            unique_fields=['alias'],
        )
        embedded += len(chunk)

    logger.info(
        'embed_product_aliases_batch | done | total=%s embedded=%s skipped=%s errors=%s',
        len(alias_ids), embedded, skipped, errors,
    )
    return {'total': len(alias_ids), 'embedded': embedded, 'skipped': skipped, 'errors': errors}


class SimilarProduct:
    """Lightweight result wrapper for find_similar_products — exposes the same
    .product/.distance shape callers already use, regardless of whether the winning
    vector came from the product's own name or one of its aliases."""
    __slots__ = ('product', 'distance')

    def __init__(self, product, distance):
        self.product = product
        self.distance = distance


_SIMILAR_PRODUCTS_SQL = """
    WITH scored AS (
        SELECT p.id AS product_id, (pe.embedding <=> %(qv)s::vector) AS distance
        FROM product_embedding pe
        JOIN trading_product p ON p.id = pe.product_id
        WHERE pe.embedding IS NOT NULL AND p.is_active = TRUE

        UNION ALL

        SELECT pa.product_id AS product_id, (pae.embedding <=> %(qv)s::vector) AS distance
        FROM product_alias_embedding pae
        JOIN trading_product_alias pa ON pa.id = pae.alias_id
        JOIN trading_product p ON p.id = pa.product_id
        WHERE pae.embedding IS NOT NULL AND p.is_active = TRUE
    )
    SELECT product_id, MIN(distance) AS best_distance
    FROM scored
    GROUP BY product_id
    ORDER BY best_distance ASC
    LIMIT %(top_k)s
"""


def find_similar_products(query: str, top_k: int = 10) -> list:
    """Return top_k products most similar to query using cosine distance — comparing
    the query against BOTH each product's own name embedding AND every one of its
    aliases' embeddings independently (multi-vector retrieval), keeping only the single
    best-matching vector per product. This is what actually helps when the same product
    gets typed differently in every inquiry: a customer's exact phrasing can be very
    close to one specific alias even when it's nowhere near the product's canonical
    name. Not yet wired into classification — the live catalog is still small enough to
    send as plain text in full (apps/trading/services/product_cache.py). This exists as
    the retrieval building block for when catalog size makes that no longer true:
    narrow to the top-K candidates here, then still hand those to the AI as text for the
    actual exact/near/null judgment — embeddings pick candidates, they don't replace the
    attribute-by-attribute matching the AI does.

    The product-vs-alias merge (keep whichever vector scores best per product) runs
    entirely in SQL — one UNION ALL of both tables' distances, grouped by product_id
    with MIN(), ordered and limited there — rather than pulling every active product's
    and every alias's embedding into Python and reducing them in a dict. The earlier
    version did exactly that: two full queries fetched in full, merged in a Python loop.
    Harmless at ~30 products, but designed for a catalog this embedding infrastructure
    was explicitly built ahead of (§ product embedding infra) to eventually be much
    larger — at that scale, only ever materializing top_k rows back into Django,
    instead of the whole active catalog on every search, is the difference that matters.
    """
    from django.db import connection
    from pgvector import Vector
    from apps.ai_providers.manager import ai_manager
    from apps.trading.models import Product

    query_vec = ai_manager.embed(query)
    query_vec_text = Vector(query_vec).to_text()

    with connection.cursor() as cursor:
        cursor.execute(_SIMILAR_PRODUCTS_SQL, {'qv': query_vec_text, 'top_k': top_k})
        rows = cursor.fetchall()  # [(product_id, distance), ...] already ranked + limited

    if not rows:
        return []

    products_by_id = Product.objects.in_bulk([product_id for product_id, _ in rows])
    return [
        SimilarProduct(products_by_id[product_id], float(distance))
        for product_id, distance in rows
        if product_id in products_by_id
    ]


def semantic_search(query: str, account_id: int, top_k: int = 10) -> list:
    """Return top_k messages most similar to query using cosine distance."""
    from apps.ai_providers.manager import ai_manager
    from apps.message_intelligence.models import MessageEmbedding
    from pgvector.django import CosineDistance

    query_vec = ai_manager.embed(query)

    results = (
        MessageEmbedding.objects
        .filter(message__account_id=account_id, embedding__isnull=False)
        .annotate(distance=CosineDistance('embedding', query_vec))
        .select_related('message__chat', 'message__contact')
        .order_by('distance')[:top_k]
    )
    return list(results)
