from django.db import transaction
from django.utils import timezone

from apps.whatsapp_bridge.models import OutboundMessage
from .events import record_event


STATUS_RANK = {
    OutboundMessage.STATUS_SENT: 1,
    OutboundMessage.STATUS_DELIVERED: 2,
    OutboundMessage.STATUS_READ: 3,
}


@transaction.atomic
def apply_outbound_receipt(account_id, provider_message_id, receipt_status):
    if receipt_status not in STATUS_RANK:
        raise ValueError('invalid_outbound_receipt_status')
    message = OutboundMessage.objects.select_for_update().filter(
        whatsapp_account_id=account_id,
        provider_message_id=provider_message_id,
    ).first()
    if not message:
        return {'matched': False, 'changed': False}
    current_rank = STATUS_RANK.get(message.status, 0)
    if current_rank >= STATUS_RANK[receipt_status]:
        return {'matched': True, 'changed': False, 'status': message.status}
    if message.status in {
        OutboundMessage.STATUS_BLOCKED, OutboundMessage.STATUS_FAILED,
        OutboundMessage.STATUS_CANCELLED,
    }:
        return {'matched': True, 'changed': False, 'status': message.status}

    now = timezone.now()
    message.status = receipt_status
    fields = ['status', 'updated_at']
    if receipt_status in {OutboundMessage.STATUS_DELIVERED, OutboundMessage.STATUS_READ}:
        message.delivered_at = message.delivered_at or now
        fields.append('delivered_at')
    if receipt_status == OutboundMessage.STATUS_READ:
        message.read_at = now
        fields.append('read_at')
    message.save(update_fields=fields)
    record_event(message, receipt_status, actor='system:baileys-receipt')
    return {'matched': True, 'changed': True, 'status': message.status}
