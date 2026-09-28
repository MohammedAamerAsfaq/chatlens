from .inquiry_forwarding_formatter import product_name, sender_link


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
    if (
        classification.classification_version == 'v2'
        and inquiry.product_match_status != inquiry.CLASSIFICATION_MATCH_COMPLETE
    ):
        return 'v2_product_matching_incomplete'

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
