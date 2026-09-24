from apps.whatsapp_bridge.models import TelemetryFetchStatus, WhatsAppChat
from apps.whatsapp_bridge.services.capacity_service import capacity_snapshot
from apps.whatsapp_bridge.services.destination_policy import (
    DIRECT_CONTACT,
    classify_destination,
    evaluate_destination,
)


def settings_snapshot(account):
    return {
        'outbound_sending_enabled': account.outbound_sending_enabled,
        'direct_sending_enabled': account.direct_sending_enabled,
        'group_sending_enabled': account.group_sending_enabled,
        'image_sending_enabled': account.image_sending_enabled,
        'recipient_interval_ms': account.recipient_interval_ms,
        'account_interval_ms': account.account_interval_ms,
        'allow_concurrent_sends': account.allow_concurrent_sends,
        'max_concurrent_sends': account.max_concurrent_sends,
        'unknown_new_chat_policy': account.unknown_new_chat_policy,
    }


def new_chat_snapshot(account, destination_jid):
    if classify_destination(destination_jid) != DIRECT_CONTACT:
        return {'state': 'not_applicable', 'confidence': 1, 'reason': 'non_direct_destination'}
    chat = WhatsAppChat.objects.filter(account=account, wa_chat_id=destination_jid).first()
    if chat and chat.messages.exists():
        return {'state': 'existing', 'confidence': 1, 'reason': 'existing_message_history'}
    return {'state': 'likely_new', 'confidence': 0.8, 'reason': 'no_message_history'}


def evaluate_outbound(message):
    from apps.whatsapp_bridge.models import WhatsAppGroup

    account = message.whatsapp_account
    group = WhatsAppGroup.objects.filter(
        account=account, wa_group_id=message.destination_jid,
    ).first()
    permission = evaluate_destination(account, message.destination_jid, group)
    if not permission['allowed']:
        return permission
    if message.content_type == 'image' and not account.image_sending_enabled:
        return {**permission, 'allowed': False, 'reason': 'image_sending_disabled'}

    capacity = capacity_snapshot(account)
    reachout = capacity['reachout']
    if reachout.get('is_active'):
        return {**permission, 'allowed': False, 'reason': 'reachout_locked', 'capacity': capacity}

    new_chat = new_chat_snapshot(account, message.destination_jid)
    if permission['destination_type'] == DIRECT_CONTACT and new_chat['state'] == 'likely_new':
        cap = capacity['cap']
        if cap.get('remaining_quota') == 0:
            return {**permission, 'allowed': False, 'reason': 'new_chat_cap_reached', 'capacity': capacity}
        cap_known = cap.get('state') == TelemetryFetchStatus.AVAILABLE and cap.get('sample_state') == 'fresh'
        if not cap_known and account.unknown_new_chat_policy == account.UNKNOWN_NEW_CHAT_BLOCK:
            return {**permission, 'allowed': False, 'reason': 'new_chat_cap_unknown', 'capacity': capacity}

    return {**permission, 'new_chat': new_chat, 'capacity': capacity}
