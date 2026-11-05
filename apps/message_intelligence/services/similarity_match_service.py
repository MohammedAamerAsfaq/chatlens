"""Record embedding-similarity matches between group messages, for observation only.

Nothing here decides whether a message is skipped or merged — see
ingestion_service._is_duplicate_group_broadcast, which uses the exact fingerprint only.
"""
import logging
from datetime import timedelta

logger = logging.getLogger(__name__)

SIMILARITY_WINDOW_MINUTES = 60
SIMILARITY_THRESHOLD = 0.92


def record_similarity_match(message_id: int):
    """Store the closest earlier group message within the window, if similar enough.

    Called right after the message's embedding is stored. Returns the record or None.
    """
    from pgvector.django import CosineDistance
    from apps.message_intelligence.models import MessageEmbedding, MessageSimilarityMatch
    from apps.whatsapp_bridge.models import ChatType

    own = (
        MessageEmbedding.objects
        .select_related('message__chat')
        .filter(message_id=message_id, embedding__isnull=False)
        .first()
    )
    if not own:
        return None
    message = own.message
    if message.direction != 'inbound' or message.chat.chat_type != ChatType.GROUP:
        return None

    window_start = message.message_time - timedelta(minutes=SIMILARITY_WINDOW_MINUTES)
    window_end = message.message_time + timedelta(minutes=SIMILARITY_WINDOW_MINUTES)
    candidate = (
        MessageEmbedding.objects
        .filter(
            message__account_id=message.account_id,
            message__chat__chat_type=ChatType.GROUP,
            message__direction='inbound',
            message__message_time__range=(window_start, window_end),
            message_id__lt=message.pk,
            embedding__isnull=False,
        )
        .select_related('message')
        .annotate(distance=CosineDistance('embedding', own.embedding))
        .order_by('distance')
        .first()
    )
    if not candidate or candidate.distance > (1 - SIMILARITY_THRESHOLD):
        MessageSimilarityMatch.objects.filter(message=message).delete()
        return None

    similar = candidate.message
    same_sender = bool(
        (message.contact_id and message.contact_id == similar.contact_id)
        or (message.sender_number and message.sender_number == similar.sender_number)
    )
    record, _ = MessageSimilarityMatch.objects.update_or_create(
        message=message,
        defaults={
            'similar_message': similar,
            'distance': candidate.distance,
            'same_chat': similar.chat_id == message.chat_id,
            'same_sender': same_sender,
            'exact_fingerprint': bool(
                message.content_fingerprint
                and message.content_fingerprint == similar.content_fingerprint
            ),
        },
    )
    return record


def record_similarity_matches(message_ids) -> None:
    """Record matches for each message; a failure never affects the stored embedding."""
    for message_id in message_ids:
        try:
            record_similarity_match(message_id)
        except Exception:
            logger.exception('record_similarity_match failed | message_id=%s', message_id)
