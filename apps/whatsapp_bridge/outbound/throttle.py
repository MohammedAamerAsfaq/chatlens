from datetime import timedelta

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.whatsapp_bridge.models import OutboundAccountState, OutboundRecipientState


class OutboundDeferred(Exception):
    def __init__(self, available_at, reason):
        super().__init__(reason)
        self.available_at = available_at
        self.reason = reason


def _after(timestamp, milliseconds):
    return timestamp + timedelta(milliseconds=milliseconds) if timestamp else None


@transaction.atomic
def reserve(message):
    account = message.whatsapp_account
    account_state, _ = OutboundAccountState.objects.get_or_create(whatsapp_account=account)
    account_state = OutboundAccountState.objects.select_for_update().get(pk=account_state.pk)
    recipient_state, _ = OutboundRecipientState.objects.get_or_create(
        whatsapp_account=account,
        canonical_recipient_key=message.canonical_recipient_key,
    )
    recipient_state = OutboundRecipientState.objects.select_for_update().get(pk=recipient_state.pk)

    now = timezone.now()
    eligible_times = [now]
    account_eligible = _after(account_state.last_dispatch_started_at, account.account_interval_ms)
    recipient_eligible = _after(recipient_state.last_dispatch_started_at, account.recipient_interval_ms)
    if account_eligible:
        eligible_times.append(account_eligible)
    if recipient_eligible:
        eligible_times.append(recipient_eligible)
    eligible_at = max(eligible_times)
    if eligible_at > now:
        reason = 'recipient_interval_wait' if recipient_eligible == eligible_at else 'account_interval_wait'
        raise OutboundDeferred(eligible_at, reason)

    limit = account.max_concurrent_sends if account.allow_concurrent_sends else 1
    if account_state.in_flight_count >= limit:
        raise OutboundDeferred(now + timedelta(seconds=1), 'account_concurrency_wait')
    if recipient_state.in_flight_count:
        raise OutboundDeferred(now + timedelta(seconds=1), 'recipient_concurrency_wait')

    account_state.in_flight_count += 1
    account_state.last_dispatch_started_at = now
    account_state.lease_version += 1
    account_state.save(update_fields=[
        'in_flight_count', 'last_dispatch_started_at', 'lease_version', 'updated_at',
    ])
    recipient_state.in_flight_count = 1
    recipient_state.last_dispatch_started_at = now
    recipient_state.save(update_fields=['in_flight_count', 'last_dispatch_started_at', 'updated_at'])
    return now


def release(message):
    OutboundAccountState.objects.filter(
        whatsapp_account=message.whatsapp_account, in_flight_count__gt=0,
    ).update(in_flight_count=F('in_flight_count') - 1)
    OutboundRecipientState.objects.filter(
        whatsapp_account=message.whatsapp_account,
        canonical_recipient_key=message.canonical_recipient_key,
        in_flight_count__gt=0,
    ).update(in_flight_count=F('in_flight_count') - 1)
