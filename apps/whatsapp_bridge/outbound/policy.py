from django.db.models import Q

from apps.whatsapp_bridge.models import TelemetryFetchStatus, WhatsAppChat, WhatsAppContact
from apps.whatsapp_bridge.services.capacity_service import capacity_snapshot
from apps.whatsapp_bridge.services.destination_policy import (
    DIRECT_CONTACT,
    classify_destination,
    evaluate_destination,
)


CAP_AVAILABLE = 'available'
CAP_EXHAUSTED = 'exhausted'
CAP_NOT_APPLICABLE = 'not_applicable'
CAP_UNKNOWN = 'unknown'


def new_chat_cap_state(cap):
    """Interpret provider capping telemetry without treating a 0/0 sentinel as exhaustion."""
    capping_status = str(cap.get('capping_status') or '').upper()
    total_quota = cap.get('total_quota')
    used_quota = cap.get('used_quota')
    remaining_quota = cap.get('remaining_quota')

    if capping_status == 'CAPPED':
        return CAP_EXHAUSTED
    if total_quota is not None and total_quota > 0:
        return CAP_EXHAUSTED if remaining_quota == 0 else CAP_AVAILABLE
    if (
        cap.get('state') == TelemetryFetchStatus.AVAILABLE
        and total_quota == 0
        and used_quota == 0
        and capping_status == 'NONE'
        and str(cap.get('ote_status') or '').upper() == 'NOT_ELIGIBLE'
        and str(cap.get('mv_status') or '').upper() == 'NOT_ELIGIBLE'
    ):
        return CAP_NOT_APPLICABLE
    return CAP_UNKNOWN


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
    contact = WhatsAppContact.objects.filter(account=account).filter(
        Q(wa_contact_id=destination_jid) | Q(lid_jid=destination_jid)
    ).first()
    if contact:
        if contact.is_existing_chat:
            return {'state': 'existing', 'confidence': 1, 'reason': 'operator_marked_existing'}
        return {'state': 'likely_new', 'confidence': 1, 'reason': 'operator_marked_new'}
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
        cap_state = new_chat_cap_state(cap)
        if cap_state == CAP_EXHAUSTED:
            return {**permission, 'allowed': False, 'reason': 'new_chat_cap_reached', 'capacity': capacity}
        cap_known = cap_state in {CAP_AVAILABLE, CAP_NOT_APPLICABLE}
        if cap_state == CAP_AVAILABLE and cap.get('sample_state') != 'fresh':
            cap_known = False
        if not cap_known and account.unknown_new_chat_policy == account.UNKNOWN_NEW_CHAT_BLOCK:
            return {**permission, 'allowed': False, 'reason': 'new_chat_cap_unknown', 'capacity': capacity}

    return {**permission, 'new_chat': new_chat, 'capacity': capacity}
