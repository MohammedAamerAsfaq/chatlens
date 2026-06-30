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
