"""Deeper WhatsApp ingestion-pipeline diagnostics, split out from diagnostics_views.py.

Same auth/trust model as that module (X-Internal-Token) - see its module docstring
for why. This file covers the sources that are specific to diagnosing *why a message
didn't make it through*: StuckReceipt, WorkerAlert, BaileysEvent, SyncLog ("Activity"),
and a reuse of the existing per-message trace_message() service for deep-diving one
specific message once a problem account/time window has been identified via the
summary endpoint.
"""
from datetime import timedelta

from django.db.models import Count
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET

from apps.whatsapp_bridge.models import BaileysEvent, StuckReceipt, SyncLog, WhatsAppAccount, WorkerAlert
from apps.whatsapp_bridge.views import _verify_internal_token

RECENT_LIMIT = 30
DEFAULT_WINDOW_HOURS = 24
MAX_WINDOW_HOURS = 24 * 14
DETAIL_TRUNCATE_CHARS = 500


def _int_param(request, name, default, maximum=None):
    raw = request.GET.get(name)
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    if maximum is not None:
        value = min(value, maximum)
    return max(value, 1)


def _account_filter(request):
    account_id = request.GET.get('account_id')
    return int(account_id) if account_id and account_id.isdigit() else None


def _stuck_receipts(account_id):
    qs = StuckReceipt.objects.select_related('account')
    if account_id:
        qs = qs.filter(account_id=account_id)
    by_account = [
        {'account_id': row['account_id'], 'account_name': row['account__display_name'], 'count': row['count']}
        for row in qs.values('account_id', 'account__display_name').annotate(count=Count('id')).order_by('-count')[:20]
    ]
    recent = [
        {
            'id': row.pk,
            'account_id': row.account_id,
            'remote_jid': row.remote_jid,
            'participant': row.participant,
            'message_id': row.message_id,
            'from_me': row.from_me,
            'occurrence_count': row.occurrence_count,
            'first_seen_at': row.first_seen_at,
            'last_seen_at': row.last_seen_at,
            'resolved_at': row.resolved_at,
        }
        for row in qs.order_by('-last_seen_at')[:RECENT_LIMIT]
    ]
    return {
        'total': qs.count(),
        'unresolved': qs.filter(resolved_at__isnull=True).count(),
        'by_account': by_account,
        'recent': recent,
    }


def _worker_alerts(account_id, since):
    qs = WorkerAlert.objects.filter(created_at__gte=since).select_related('account')
    if account_id:
        qs = qs.filter(account_id=account_id)
    by_type = {
        row['alert_type']: row['count']
        for row in qs.values('alert_type').annotate(count=Count('id')).order_by('-count')
    }
    by_severity = {
        row['severity']: row['count']
        for row in qs.values('severity').annotate(count=Count('id')).order_by('-count')
    }
    recent = [
        {
            'id': row.pk,
            'account_id': row.account_id,
            'account_name': row.account.display_name if row.account_id else '',
            'alert_type': row.alert_type,
            'severity': row.severity,
            'message': row.message[:DETAIL_TRUNCATE_CHARS],
            'created_at': row.created_at,
            'acknowledged_at': row.acknowledged_at,
        }
        for row in qs.order_by('-created_at')[:RECENT_LIMIT]
    ]
    return {
        'total': qs.count(),
        'unacknowledged': qs.filter(acknowledged_at__isnull=True).count(),
        'by_alert_type': by_type,
        'by_severity': by_severity,
        'recent': recent,
    }


def _baileys_events(account_id, since):
    # BaileysEvent logs every message at every pipeline stage - this table can be very
    # large on an active account, so every query here is bounded by the time window;
    # never count()/list() it unbounded.
    qs = BaileysEvent.objects.filter(created_at__gte=since)
    if account_id:
        qs = qs.filter(account_id=account_id)
    by_stage = {
        row['event_stage']: row['count']
        for row in qs.values('event_stage').annotate(count=Count('id')).order_by('-count')
    }
    by_status = {
        row['status']: row['count']
        for row in qs.values('status').annotate(count=Count('id')).order_by('-count')
    }
    by_reason = {
        row['reason']: row['count']
        for row in qs.exclude(reason='').values('reason').annotate(count=Count('id')).order_by('-count')[:20]
    }
    recent_failures = [
        {
            'id': row.pk,
            'account_id': row.account_id,
            'event_stage': row.event_stage,
            'status': row.status,
            'event_type': row.event_type,
            'reason': row.reason,
            'error_message': row.error_message[:DETAIL_TRUNCATE_CHARS],
            'provider_message_id': row.provider_message_id,
            'raw_jid': row.raw_jid,
            'created_at': row.created_at,
        }
        for row in qs.filter(status='failure').order_by('-created_at')[:RECENT_LIMIT]
    ]
    return {
        'window_total': qs.count(),
        'by_stage': by_stage,
        'by_status': by_status,
        'by_reason': by_reason,
        'recent_failures': recent_failures,
    }


def _activity(account_id, since):
    qs = SyncLog.objects.filter(created_at__gte=since).select_related('account')
    if account_id:
        qs = qs.filter(account_id=account_id)
    recent = [
        {
            'id': row.pk,
            'account_id': row.account_id,
            'account_name': row.account.display_name,
            'event_type': row.event_type,
            'status': row.status,
            'message': row.message[:DETAIL_TRUNCATE_CHARS],
            'created_at': row.created_at,
        }
        for row in qs.order_by('-created_at')[:RECENT_LIMIT]
    ]
    return {'window_total': qs.count(), 'recent': recent}


@require_GET
def internal_diagnostics_messages(request):
    """WhatsApp ingestion-pipeline diagnostics: stuck receipts, worker alerts,
    Baileys per-stage events, and account activity log.

    Query params (all optional): account_id to scope every section to one
    WhatsApp account, hours to widen/narrow the Baileys-event/activity window
    (default 24, capped at 14 days - StuckReceipt/WorkerAlert summaries aren't
    time-windowed by default since those tables are naturally low-volume).
    """
    if not _verify_internal_token(request):
        return JsonResponse({'detail': 'Invalid internal token.'}, status=401)

    account_id = _account_filter(request)
    hours = _int_param(request, 'hours', DEFAULT_WINDOW_HOURS, maximum=MAX_WINDOW_HOURS)
    since = timezone.now() - timedelta(hours=hours)

    return JsonResponse({
        'window_hours': hours,
        'account_id': account_id,
        'stuck_receipts': _stuck_receipts(account_id),
        'worker_alerts': _worker_alerts(account_id, since),
        'baileys_events': _baileys_events(account_id, since),
        'activity': _activity(account_id, since),
    })


@require_GET
def internal_diagnostics_trace(request):
    """Full cross-table lifecycle trace for one (account, provider_message_id) pair -
    thin wrapper around the existing apps.whatsapp_bridge.services.message_trace
    service that already backs the session-authenticated Message Trace screen.
    """
    if not _verify_internal_token(request):
        return JsonResponse({'detail': 'Invalid internal token.'}, status=401)

    account_id = request.GET.get('account_id')
    provider_message_id = (request.GET.get('provider_message_id') or '').strip()
    if not account_id or not provider_message_id:
        return JsonResponse(
            {'detail': 'account_id and provider_message_id query params are both required.'}, status=400,
        )

    account = WhatsAppAccount.objects.filter(pk=account_id).first()
    if not account:
        return JsonResponse({'detail': 'Account not found.'}, status=404)

    from apps.whatsapp_bridge.services.message_trace import trace_message
    return JsonResponse(trace_message(account, provider_message_id))
