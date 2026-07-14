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
    """Compose the text we embed for a single ProductAlias — deliberately just the bare
    alias string (no brand/name mixed in), so its vector represents that one phrasing on
    its own rather than being pulled toward the product's canonical name."""
    return (product_alias.alias or '').strip()


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

    alias = ProductAlias.objects.get(pk=alias_id)
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

    aliases = list(ProductAlias.objects.filter(pk__in=alias_ids))
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
    attribute-by-attribute matching the AI does."""
    from apps.ai_providers.manager import ai_manager
    from apps.message_intelligence.models import ProductEmbedding, ProductAliasEmbedding
    from pgvector.django import CosineDistance

    query_vec = ai_manager.embed(query)

    product_hits = (
        ProductEmbedding.objects
        .filter(embedding__isnull=False, product__is_active=True)
        .annotate(distance=CosineDistance('embedding', query_vec))
        .select_related('product')
    )
    alias_hits = (
        ProductAliasEmbedding.objects
        .filter(embedding__isnull=False, alias__product__is_active=True)
        .annotate(distance=CosineDistance('embedding', query_vec))
        .select_related('alias__product')
    )

    best_by_product: dict[int, SimilarProduct] = {}
    for hit in product_hits:
        best_by_product[hit.product_id] = SimilarProduct(hit.product, hit.distance)
    for hit in alias_hits:
        product = hit.alias.product
        existing = best_by_product.get(product.id)
        if existing is None or hit.distance < existing.distance:
            best_by_product[product.id] = SimilarProduct(product, hit.distance)

    ranked = sorted(best_by_product.values(), key=lambda r: r.distance)
    return ranked[:top_k]


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
