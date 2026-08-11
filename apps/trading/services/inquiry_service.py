import logging
from datetime import timedelta

from django.db import transaction
from django.utils.timezone import now

logger = logging.getLogger(__name__)

DEDUP_WINDOW_HOURS = 4
SIMILARITY_THRESHOLD = 0.92


def _link_message(inquiry, message) -> None:
    from apps.trading.models import InquiryMessage

    InquiryMessage.objects.get_or_create(inquiry=inquiry, message=message)
    logger.info(
        'inquiry_service | linked message | inquiry_id=%s | message_id=%s',
        inquiry.pk,
        message.pk,
    )


def _derive_source_type(chat) -> str:
    from apps.whatsapp_bridge.models import ChatType

    if chat.chat_type == ChatType.GROUP:
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


def _layer1_match(account, contact, dedup_key: str, inquiry_type: str):
    """Exact dedup_key lookup within the time window."""
    if not dedup_key:
        return None
    from apps.trading.models import Inquiry, InquiryStatus

    window = now() - timedelta(hours=DEDUP_WINDOW_HOURS)
    qs = Inquiry.objects.filter(
        account=account,
        contact=contact,
        dedup_key=dedup_key,
        status=InquiryStatus.OPEN,
        first_seen_at__gte=window,
    )
    if inquiry_type in ('buy', 'sell'):
        qs = qs.filter(inquiry_type=inquiry_type)
    return qs.first()


def _layer2_match(account, contact, message, inquiry_type: str):
    """Semantic similarity fallback using stored embeddings."""
    try:
        from apps.message_intelligence.models import MessageEmbedding
        from apps.trading.models import Inquiry, InquiryStatus
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
        if inquiry_type in ('buy', 'sell'):
            recent = recent.filter(inquiry_type=inquiry_type)
        for candidate in recent:
            first_link = candidate.inquiry_messages.select_related('message').first()
            if not first_link:
                continue
            src_emb_row = MessageEmbedding.objects.filter(message=first_link.message).first()
            if not src_emb_row or src_emb_row.embedding is None:
                continue
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
    from apps.trading.models import Inquiry
    from apps.tenancy.services.access import company_for_message

    with transaction.atomic():
        account = message.account
        company = company_for_message(message)
        contact = _resolve_contact(message)
        dedup_key = classification.dedup_key or ''
        inquiry_type = classification.inquiry_type
        match_inquiry_type = 'buy' if inquiry_type == 'both' else inquiry_type

        existing = _layer1_match(account, contact, dedup_key, match_inquiry_type)
        if not existing:
            existing = _layer2_match(account, contact, message, match_inquiry_type)

        from apps.trading.services.classification_service import validate_category_suggestion

        suggested_category = validate_category_suggestion(
            classification.suggested_contact_category,
            contact,
        )

        if existing:
            _link_message(existing, message)
            existing.suggested_contact_category = suggested_category
            existing.classification_version = classification.classification_version or existing.classification_version
            if classification.classification_version == 'v2':
                existing.product_match_status = Inquiry.CLASSIFICATION_MATCH_PENDING
                existing.product_match_error = ''
            existing.save(update_fields=[
                'suggested_contact_category',
                'classification_version',
                'product_match_status',
                'product_match_error',
            ])
            logger.info(
                'inquiry_service | linked to existing | inquiry_id=%s | message_id=%s',
                existing.pk,
                message.pk,
            )
            return [existing]

        if inquiry_type == 'both':
            inquiry_type = 'buy'

        inquiry = Inquiry.objects.create(
            company=company,
            account=account,
            contact=contact,
            inquiry_type=inquiry_type,
            products=classification.products,
            summary=classification.ai_summary,
            dedup_key=dedup_key,
            source_type=_derive_source_type(message.chat),
            first_seen_at=message.message_time,
            suggested_contact_category=suggested_category,
            classification_version=classification.classification_version or 'v1',
            product_match_status=(
                Inquiry.CLASSIFICATION_MATCH_PENDING
                if classification.classification_version == 'v2'
                else Inquiry.CLASSIFICATION_MATCH_NOT_REQUIRED
            ),
        )
        _link_message(inquiry, message)

        logger.info(
            'inquiry_service | created | inquiry_id=%s | type=%s | message_id=%s',
            inquiry.pk,
            inquiry_type,
            message.pk,
        )

        if classification.inquiry_type == 'both':
            sell_inquiry = Inquiry.objects.create(
                company=company,
                account=account,
                contact=contact,
                inquiry_type='sell',
                products=classification.products,
                summary=classification.ai_summary,
                dedup_key=dedup_key.replace('buy:', 'sell:', 1),
                source_type=inquiry.source_type,
                first_seen_at=message.message_time,
                suggested_contact_category=suggested_category,
                classification_version=classification.classification_version or 'v1',
                product_match_status=(
                    Inquiry.CLASSIFICATION_MATCH_PENDING
                    if classification.classification_version == 'v2'
                    else Inquiry.CLASSIFICATION_MATCH_NOT_REQUIRED
                ),
            )
            _link_message(sell_inquiry, message)
            logger.info(
                'inquiry_service | created sell-side | inquiry_id=%s | message_id=%s',
                sell_inquiry.pk,
                message.pk,
            )
            return [inquiry, sell_inquiry]

        return [inquiry]
