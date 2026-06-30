import logging
from datetime import timedelta
from django.utils.timezone import now

logger = logging.getLogger(__name__)

DEDUP_WINDOW_HOURS = 4
SIMILARITY_THRESHOLD = 0.92


def _derive_source_type(chat) -> str:
    from apps.whatsapp_bridge.models import ChatType
    if chat.chat_type == ChatType.GROUP:
        # Check if chat belongs to a community (has a linked WhatsAppGroup with a community parent)
        try:
            group = chat.group
            if group and group.community_id:
                return 'community'
        except Exception:
            pass
        return 'group'
    return 'direct'


def _resolve_contact(message):
    """Return the WhatsAppContact for the message sender, or None."""
    if message.contact:
        return message.contact
    if message.sender_number:
        try:
            from apps.whatsapp_bridge.models import WhatsAppContact
            return WhatsAppContact.objects.get(
                account=message.account,
                wa_contact_id=f'{message.sender_number}@s.whatsapp.net',
            )
        except Exception:
            pass
    return None


def _layer1_match(account, contact, dedup_key: str):
    """Exact dedup_key lookup within the time window."""
    if not dedup_key:
        return None
    from apps.trading.models import Inquiry, InquiryStatus
    window = now() - timedelta(hours=DEDUP_WINDOW_HOURS)
    return Inquiry.objects.filter(
        account=account,
        contact=contact,
        dedup_key=dedup_key,
        status=InquiryStatus.OPEN,
        first_seen_at__gte=window,
    ).first()


def _layer2_match(account, contact, message):
    """Semantic similarity fallback using stored embeddings."""
    try:
        from apps.message_intelligence.models import MessageEmbedding
        from apps.trading.models import Inquiry, InquiryMessage, InquiryStatus
        from pgvector.django import CosineDistance

        new_emb_row = MessageEmbedding.objects.filter(message=message).first()
        if not new_emb_row or new_emb_row.embedding is None:
            return None

        window = now() - timedelta(hours=DEDUP_WINDOW_HOURS)
        recent = Inquiry.objects.filter(
            account=account,
            contact=contact,
            status=InquiryStatus.OPEN,
            first_seen_at__gte=window,
        )
        for candidate in recent:
            first_link = candidate.inquiry_messages.select_related('message').first()
            if not first_link:
                continue
            src_emb_row = MessageEmbedding.objects.filter(message=first_link.message).first()
            if not src_emb_row or src_emb_row.embedding is None:
                continue
            # CosineDistance returns 0 for identical, 1 for orthogonal
            dist = (
                MessageEmbedding.objects
                .filter(pk=src_emb_row.pk)
                .annotate(d=CosineDistance('embedding', new_emb_row.embedding))
                .values_list('d', flat=True)
                .first()
            )
            if dist is not None and dist <= (1 - SIMILARITY_THRESHOLD):
                return candidate
    except Exception:
        logger.debug('inquiry_service | layer2 similarity check failed', exc_info=True)
    return None


def process_inquiry(message, classification) -> None:
    """
    Create or update an Inquiry based on a classified message.
    Called from classify_message() when is_inquiry=True.
    """
    from apps.trading.models import Inquiry, InquiryMessage

    account = message.account
    contact = _resolve_contact(message)
    dedup_key = classification.dedup_key or ''

    # Layer 1: exact dedup_key match
    existing = _layer1_match(account, contact, dedup_key)

    # Layer 2: semantic similarity fallback
    if not existing:
        existing = _layer2_match(account, contact, message)

    if existing:
        InquiryMessage.objects.get_or_create(inquiry=existing, message=message)
        logger.info(
            'inquiry_service | linked to existing | inquiry_id=%s | message_id=%s',
            existing.pk, message.pk,
        )
        return

    # Map "both" inquiry_type to "buy" for the Inquiry record
    # (two separate inquiries would be created for genuine buy+sell in one message)
    inquiry_type = classification.inquiry_type
    if inquiry_type == 'both':
        inquiry_type = 'buy'

    inquiry = Inquiry.objects.create(
        account      = account,
        contact      = contact,
        inquiry_type = inquiry_type,
        products     = classification.products,
        summary      = classification.ai_summary,
        dedup_key    = dedup_key,
        source_type  = _derive_source_type(message.chat),
        first_seen_at = message.message_time,
    )
    InquiryMessage.objects.create(inquiry=inquiry, message=message)

    logger.info(
        'inquiry_service | created | inquiry_id=%s | type=%s | message_id=%s',
        inquiry.pk, inquiry_type, message.pk,
    )

    # If the original inquiry_type was "both", also create a sell inquiry
    if classification.inquiry_type == 'both':
        sell_inquiry = Inquiry.objects.create(
            account      = account,
            contact      = contact,
            inquiry_type = 'sell',
            products     = classification.products,
            summary      = classification.ai_summary,
            dedup_key    = dedup_key.replace('buy:', 'sell:', 1),
            source_type  = inquiry.source_type,
            first_seen_at = message.message_time,
        )
        InquiryMessage.objects.create(inquiry=sell_inquiry, message=message)
        logger.info(
            'inquiry_service | created sell-side | inquiry_id=%s | message_id=%s',
            sell_inquiry.pk, message.pk,
        )
