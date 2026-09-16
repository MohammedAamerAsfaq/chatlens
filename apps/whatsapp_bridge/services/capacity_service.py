from datetime import datetime, timedelta, timezone as datetime_timezone

from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.whatsapp_bridge.models import TelemetryFetchStatus, WhatsAppAccountCapacity


VALID_FETCH_STATUSES = set(TelemetryFetchStatus.values)


def _parse_timestamp(value):
    if value in (None, ''):
        return None
    text = str(value).strip()
    parsed = parse_datetime(text)
    if parsed:
        if timezone.is_naive(parsed):
            parsed = timezone.make_aware(parsed, datetime_timezone.utc)
        return parsed
    try:
        numeric = float(text)
        if numeric > 10_000_000_000:
            numeric /= 1000
        return datetime.fromtimestamp(numeric, tz=datetime_timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return None


def _safe_nonnegative_int(value):
    try:
        return max(0, int(value)) if value is not None else None
    except (TypeError, ValueError):
        return None


def _fetch_status(section):
    status = str(section.get('status') or TelemetryFetchStatus.UNKNOWN)
    return status if status in VALID_FETCH_STATUSES else TelemetryFetchStatus.UNKNOWN


def apply_capacity_telemetry(account, payload):
    capacity, _ = WhatsAppAccountCapacity.objects.get_or_create(account=account)
    now = timezone.now()
    capacity.source = str(payload.get('source') or capacity.source or 'baileys_v7')[:50]

    cap = payload.get('cap')
    if isinstance(cap, dict):
        checked_at = _parse_timestamp(cap.get('checked_at')) or now
        if not capacity.cap_checked_at or checked_at >= capacity.cap_checked_at:
            capacity.cap_fetch_status = _fetch_status(cap)
            capacity.cap_checked_at = checked_at
            capacity.cap_error = str(cap.get('error') or '')
            if capacity.cap_fetch_status == TelemetryFetchStatus.AVAILABLE:
                data = cap.get('data') if isinstance(cap.get('data'), dict) else {}
                capacity.total_quota = _safe_nonnegative_int(data.get('total_quota'))
                capacity.used_quota = _safe_nonnegative_int(data.get('used_quota'))
                capacity.cycle_started_at = _parse_timestamp(data.get('cycle_start_timestamp'))
                capacity.cycle_ends_at = _parse_timestamp(data.get('cycle_end_timestamp'))
                capacity.server_sent_at = _parse_timestamp(data.get('server_sent_timestamp'))
                capacity.capping_status = str(data.get('capping_status') or '')[:40]
                capacity.ote_status = str(data.get('ote_status') or '')[:50]
                capacity.mv_status = str(data.get('mv_status') or '')[:50]
                capacity.cap_updated_at = now

    reachout = payload.get('reachout')
    if isinstance(reachout, dict):
        checked_at = _parse_timestamp(reachout.get('checked_at')) or now
        if not capacity.reachout_checked_at or checked_at >= capacity.reachout_checked_at:
            capacity.reachout_fetch_status = _fetch_status(reachout)
            capacity.reachout_checked_at = checked_at
            capacity.reachout_error = str(reachout.get('error') or '')
            if capacity.reachout_fetch_status == TelemetryFetchStatus.AVAILABLE:
                data = reachout.get('data') if isinstance(reachout.get('data'), dict) else {}
                capacity.reachout_lock_active = bool(data.get('is_active', False))
                capacity.reachout_lock_ends_at = _parse_timestamp(data.get('time_enforcement_ends'))
                capacity.reachout_enforcement_type = str(data.get('enforcement_type') or '')[:100]
                capacity.reachout_updated_at = now

    capacity.save()
    return capacity


def _sample_state(updated_at, now):
    if not updated_at:
        return 'none'
    max_age = getattr(settings, 'WHATSAPP_CAPACITY_MAX_AGE_SECONDS', 300)
    return 'fresh' if updated_at >= now - timedelta(seconds=max_age) else 'stale'


def capacity_snapshot(account):
    try:
        capacity = account.message_capacity
    except WhatsAppAccountCapacity.DoesNotExist:
        capacity = None
    now = timezone.now()
    if not capacity:
        return {
            'source': 'baileys_v7',
            'cap': {'state': 'unknown', 'sample_state': 'none'},
            'reachout': {'state': 'unknown', 'sample_state': 'none'},
        }

    return {
        'source': capacity.source,
        'cap': {
            'state': capacity.cap_fetch_status,
            'sample_state': _sample_state(capacity.cap_updated_at, now),
            'total_quota': capacity.total_quota,
            'used_quota': capacity.used_quota,
            'remaining_quota': capacity.remaining_quota,
            'cycle_started_at': capacity.cycle_started_at,
            'cycle_ends_at': capacity.cycle_ends_at,
            'server_sent_at': capacity.server_sent_at,
            'capping_status': capacity.capping_status,
            'ote_status': capacity.ote_status,
            'mv_status': capacity.mv_status,
            'checked_at': capacity.cap_checked_at,
            'updated_at': capacity.cap_updated_at,
            'error': capacity.cap_error,
        },
        'reachout': {
            'state': capacity.reachout_fetch_status,
            'sample_state': _sample_state(capacity.reachout_updated_at, now),
            'is_active': capacity.reachout_lock_active,
            'ends_at': capacity.reachout_lock_ends_at,
            'enforcement_type': capacity.reachout_enforcement_type,
            'checked_at': capacity.reachout_checked_at,
            'updated_at': capacity.reachout_updated_at,
            'error': capacity.reachout_error,
        },
    }
