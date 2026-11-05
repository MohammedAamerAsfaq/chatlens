import logging
from datetime import timedelta

from django.db import transaction

logger = logging.getLogger(__name__)

# An inquiry absorbs a message only when one of its linked messages carries the same
# in-house dedup_key (same sender + identical normalized text) within this window.
DEDUP_WINDOW_MINUTES = 60


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


def _dedup_window(message):
    window = timedelta(minutes=DEDUP_WINDOW_MINUTES)
    return message.message_time - window, message.message_time + window


def _exact_match_inquiries(message, inquiry_type: str = ''):
    """Open inquiries holding a message with this message's dedup_key inside the window.

    Exact match only — never embedding similarity: near-identical template reposts that
    differ by one product-defining word are different requests.
    """
    from apps.trading.models import Inquiry, InquiryStatus
    from apps.whatsapp_bridge.services.message_fingerprint import dedup_scope_account_ids

    qs = Inquiry.objects.filter(
        account_id__in=dedup_scope_account_ids(message.account),
        dedup_key=message.dedup_key,
        status=InquiryStatus.OPEN,
        inquiry_messages__message__dedup_key=message.dedup_key,
        inquiry_messages__message__message_time__range=_dedup_window(message),
    )
    if inquiry_type:
        qs = qs.filter(inquiry_type=inquiry_type)
    return qs.distinct().order_by('-first_seen_at')


def _link_skipped_reposts(inquiry, message) -> None:
    """Attach exact copies that skipped classification as duplicate broadcasts, so the
    inquiry keeps the true repost frequency. Covers copies that arrived before this
    inquiry existed; link_duplicate_broadcast covers those arriving after."""
    from apps.whatsapp_bridge.models import WhatsAppMessage
    from apps.whatsapp_bridge.services.message_fingerprint import dedup_scope_account_ids

    reposts = (
        WhatsAppMessage.objects
        .filter(
            account_id__in=dedup_scope_account_ids(message.account),
            dedup_key=message.dedup_key,
            message_time__range=_dedup_window(message),
            ai_parsing_log__skip_reason='duplicate_broadcast',
        )
        .exclude(inquiry_links__inquiry=inquiry)
    )
    for repost in reposts:
        _link_message(inquiry, repost)


def link_duplicate_broadcast(message) -> list:
    """Link a message skipped as duplicate_broadcast to the open inquiry its exact
    original already produced. Returns the linked inquiries (none if the original is
    still being classified — _link_skipped_reposts attaches it once the inquiry exists)."""
    if not message.dedup_key:
        return []
    with transaction.atomic():
        inquiries = list(_exact_match_inquiries(message))
        for inquiry in inquiries:
            _link_message(inquiry, message)
    return inquiries


def process_inquiry(message, classification) -> None:
    """
    Create or update an Inquiry based on a classified message.
    Called from classify_message() when is_inquiry=True.
    """
    from apps.trading.models import Inquiry
    from apps.tenancy.services.access import company_for_message

    if not message.dedup_key:
        raise ValueError(f'process_inquiry | message has no dedup_key | message_id={message.pk}')

    with transaction.atomic():
        account = message.account
        company = company_for_message(message)
        contact = _resolve_contact(message)
        dedup_key = message.dedup_key
        inquiry_type = classification.inquiry_type

        existing = _exact_match_inquiries(message, inquiry_type).first()

        from apps.trading.services.classification_service import validate_category_suggestion

        suggested_category = validate_category_suggestion(
            classification.suggested_contact_category,
            contact,
        )

        if existing:
            _link_message(existing, message)
            _link_skipped_reposts(existing, message)
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
        _link_skipped_reposts(inquiry, message)

        logger.info(
            'inquiry_service | created | inquiry_id=%s | type=%s | message_id=%s',
            inquiry.pk,
            inquiry_type,
            message.pk,
        )

        return [inquiry]
