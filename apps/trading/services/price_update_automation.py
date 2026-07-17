"""
Automated price-list detection — the "Automated Price Updates" section of the
Product Price Update page (Sale Price tab only). Called once per classify-eligible
inbound message from apps.whatsapp_bridge.services.ingestion_service, using the
exact same eligibility gate as trading classification (_classify_skip_reason), so
there's no separate/looser filter deciding what's "worth checking."

Design: a message is matched against each active AutomationRule's watched sources
(contact DM / whole group / one contact scoped to one group — independently
combinable) and content trigger (heading text and/or "let the AI parse decide").
There is deliberately no separate "is this a price list" classification call —
the message is run through the same AI sale-price matching process the manual
flow uses (parse_against_inventory), and getting back at least one item with a
real sale_price *is* the price-list signal. This avoids a redundant AI call per
candidate message: one call both detects and extracts.
"""
import logging

logger = logging.getLogger(__name__)


def check_automation_rules(message) -> None:
    """Entry point called from the ingestion pipeline for one inbound message.
    Never raises — a failure here must not break message ingestion or
    classification, which is why the caller also wraps this in its own guard."""
    from apps.trading.models import AutomationRule

    if hasattr(message, 'price_capture'):
        return  # already processed (defensive — re-delivery, re-run, etc.)

    rule = _find_matching_rule(message)
    if rule is None:
        return

    _process_match(rule, message)


def _find_matching_rule(message):
    from apps.trading.models import AutomationRule

    rules = (
        AutomationRule.objects
        .filter(is_active=True)
        .prefetch_related('sources__contact', 'sources__group')
        .order_by('created_at')
    )
    for rule in rules:
        if _source_matches(rule, message) and _content_matches(rule, message):
            return rule
    return None


def _source_matches(rule, message) -> bool:
    from apps.whatsapp_bridge.models import ChatType
    from apps.trading.models import AutomationRuleSource

    chat = message.chat
    is_group = chat is not None and chat.chat_type == ChatType.GROUP

    for src in rule.sources.all():
        if src.source_type == AutomationRuleSource.SOURCE_CONTACT:
            if not is_group and message.contact_id and message.contact_id == src.contact_id:
                return True

        elif src.source_type == AutomationRuleSource.SOURCE_GROUP:
            if is_group and src.group_id and _chat_is_group(chat, src.group):
                return True

        elif src.source_type == AutomationRuleSource.SOURCE_CONTACT_IN_GROUP:
            if (
                is_group
                and src.group_id and _chat_is_group(chat, src.group)
                and message.contact_id and message.contact_id == src.contact_id
            ):
                return True

    return False


def _chat_is_group(chat, group) -> bool:
    """A WhatsAppGroup's `chat` FK can be stale/null (group metadata and chat rows
    arrive independently) — match on (account, wa_chat_id/wa_group_id) instead of
    trusting the FK directly, same defensive approach GroupViewSet's serializer
    already uses for the same reason."""
    return chat.account_id == group.account_id and chat.wa_chat_id == group.wa_group_id


def _content_matches(rule, message) -> bool:
    has_heading = bool(rule.trigger_heading)
    has_ai      = rule.trigger_ai_detect

    if not has_heading and not has_ai:
        return True  # "any message" — no content filter configured

    if has_heading and rule.trigger_heading.lower() in (message.message_text or '').lower():
        return True

    if has_ai:
        return True  # no reliable signal yet — defer to the AI parse step itself

    return False


def _process_match(rule, message) -> None:
    from django.db.models import F
    from django.utils.timezone import now
    from apps.trading.models import AutomationRule, AutomatedPriceCapture, PromptConfig, SALE_PRICE_UPDATE_DEFAULT
    from apps.trading.services.price_update_service import parse_against_inventory

    try:
        items = parse_against_inventory(
            message.message_text, PromptConfig.KEY_SALE_PRICE_UPDATE, SALE_PRICE_UPDATE_DEFAULT,
        )
    except Exception:
        logger.exception('check_automation_rules | parse failed | rule_id=%s | message_id=%s', rule.pk, message.pk)
        return

    priced_items = [item for item in items if item.get('sale_price') is not None]
    if not priced_items:
        # Matched on source + a soft trigger (AI-detect / any-message), but the AI
        # itself found nothing price-list-shaped here — not a false "queued" entry.
        return

    # Test mode still runs the real match + parse (so an AI-detect-gated rule is
    # genuinely exercised, not just assumed to pass) but never applies anything and
    # never needs review — it's purely "yes, this rule fires and here's what it
    # would have found."
    initial_status = (
        AutomatedPriceCapture.STATUS_TEST if rule.action_mode == rule.ACTION_TEST
        else AutomatedPriceCapture.STATUS_QUEUED
    )
    capture = AutomatedPriceCapture.objects.create(
        rule=rule, message=message, items=priced_items,
        status=initial_status,
    )

    AutomationRule.objects.filter(pk=rule.pk).update(
        last_triggered_at=now(), trigger_count=F('trigger_count') + 1,
    )

    if rule.action_mode == rule.ACTION_AUTO:
        apply_capture(capture)

    logger.info(
        'check_automation_rules | matched | rule_id=%s | message_id=%s | items=%d | action=%s',
        rule.pk, message.pk, len(priced_items), rule.action_mode,
    )


def apply_capture(capture) -> None:
    """Applies a capture's items to inventory (sale_price only) and marks it
    applied. Used both for auto-apply-on-match and for a human clicking Apply
    from the review queue."""
    from django.utils.timezone import now
    from apps.trading.models import AutomatedPriceCapture
    from apps.trading.services.price_update_service import apply_items_to_inventory

    apply_items_to_inventory(capture.items, [('sale_price', 'sale_price')])
    capture.status = AutomatedPriceCapture.STATUS_APPLIED
    capture.applied_at = now()
    capture.save(update_fields=['status', 'applied_at'])
