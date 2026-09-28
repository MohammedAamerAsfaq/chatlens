from .inquiry_forwarding_formatter import product_name, sender_link


def formation_state(inquiry, source):
    """Return whether every required classification stage for an inquiry is final."""
    from apps.trading.models import AiParseV2Log, MessageClassification

    if not source:
        return 'invalid', 'source_message_unavailable'
    classification = MessageClassification.objects.filter(message=source).first()
    if not classification:
        return 'pending', 'classification_incomplete'
    if not classification.is_inquiry or not classification.inquiry_type:
        return 'invalid', 'classification_not_inquiry'
    if not inquiry.products:
        return 'invalid', 'no_inquiry_products'
    if classification.classification_version != 'v2':
        return 'ready', ''
    if inquiry.product_match_status == inquiry.CLASSIFICATION_MATCH_ERROR:
        return 'invalid', 'v2_product_matching_error'
    if inquiry.product_match_status != inquiry.CLASSIFICATION_MATCH_COMPLETE:
        return 'pending', 'v2_product_matching_incomplete'

    linked_v2_message_ids = list(inquiry.inquiry_messages.filter(
        message__classification__classification_version='v2',
    ).values_list('message_id', flat=True))
    logs = AiParseV2Log.objects.filter(message_id__in=linked_v2_message_ids)
    if logs.filter(status=AiParseV2Log.STATUS_ERROR).exists():
        return 'invalid', 'linked_v2_processing_error'
    if logs.count() != len(linked_v2_message_ids):
        return 'pending', 'linked_v2_processing_incomplete'
    if logs.exclude(status=AiParseV2Log.STATUS_COMPLETE).exists():
        return 'pending', 'linked_v2_processing_incomplete'
    if not logs.filter(message=source, status=AiParseV2Log.STATUS_COMPLETE).exists():
        return 'pending', 'source_v2_processing_incomplete'
    return 'ready', ''


def ineligible_reason(rule, inquiry, source):
    from apps.trading.models import MessageClassification
    from apps.whatsapp_bridge.models import MessageDirection, WhatsAppGroup

    if not source or source.direction != MessageDirection.INBOUND:
        return 'source_message_not_inbound'
    classification = MessageClassification.objects.filter(message=source).first()
    if not classification or not classification.is_inquiry:
        return 'classification_not_inquiry'
    if classification.inquiry_type != rule.inquiry_type or inquiry.inquiry_type != rule.inquiry_type:
        return 'inquiry_type_mismatch'

    products = [row for row in (inquiry.products or []) if isinstance(row, dict) and product_name(row)]
    classified_products = [
        row for row in (classification.products or [])
        if isinstance(row, dict) and product_name(row)
    ]
    if not products or not classified_products:
        return 'no_inquiry_products'
    inquiry_names = {product_name(row).casefold() for row in products}
    classified_names = {product_name(row).casefold() for row in classified_products}
    if not inquiry_names.intersection(classified_names):
        return 'product_evidence_mismatch'
    if source.contact_id and rule.exclusions.filter(contact_id=source.contact_id).exists():
        return 'source_contact_excluded'
    source_group = WhatsAppGroup.objects.filter(
        account=source.account, wa_group_id=source.chat.wa_chat_id,
    ).first()
    if source_group and rule.exclusions.filter(group=source_group).exists():
        return 'source_group_excluded'
    if rule.include_sender_link and not sender_link(source):
        return 'sender_direct_link_unavailable'
    return ''


def source_destination_reason(target, source):
    if target.contact_id:
        if source.contact_id and target.contact_id == source.contact_id:
            return 'source_contact_is_destination'
        if (
            target.contact.account_id == source.account_id
            and target.contact.wa_contact_id == source.chat.wa_chat_id
        ):
            return 'source_contact_is_destination'
    if target.group_id and (
        target.group.account_id == source.account_id
        and target.group.wa_group_id == source.chat.wa_chat_id
    ):
        return 'source_group_is_destination'
    return ''
