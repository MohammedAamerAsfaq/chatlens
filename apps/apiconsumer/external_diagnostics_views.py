"""Company-scoped WhatsApp ingestion-pipeline diagnostics for the external API.

Deliberately separate from apps/queue_management/diagnostics_views.py (the
internal, cross-company, X-Internal-Token-gated ops endpoint) - this one is
reachable with an ordinary apiconsumer data:read key and never sees anything
outside that key's own company. Every query below filters through
account__communication_account__company=request.auth.company; none of the
underlying models have a direct company FK.
"""
from datetime import timedelta

from django.db.models import Count
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.whatsapp_bridge.models import (
    BaileysEvent, DroppedMessage, ResolutionStatus, StuckReceipt, SyncLog, WorkerAlert,
    WhatsAppUnresolvedMessage,
)

from .external_views import ExternalApiMixin
from .models import ApiKey

RECENT_LIMIT = 20
DEFAULT_WINDOW_HOURS = 24
MAX_WINDOW_HOURS = 24 * 14
DETAIL_TRUNCATE_CHARS = 500
MESSAGE_TEXT_TRUNCATE_CHARS = 300


class DiagnosticsView(ExternalApiMixin, APIView):
    """WhatsApp ingestion-pipeline health for the key's own company: dropped and
    unresolved messages, stuck receipts, worker alerts, a Baileys-event breakdown,
    and recent activity - everything needed to answer "why aren't my messages
    arriving", scoped strictly to this key's company.
    """

    required_scope = ApiKey.SCOPE_DATA_READ

    def get(self, request):
        company = request.auth.company
        now = timezone.now()
        try:
            hours = min(max(int(request.query_params.get('hours') or DEFAULT_WINDOW_HOURS), 1), MAX_WINDOW_HOURS)
        except ValueError:
            hours = DEFAULT_WINDOW_HOURS
        since = now - timedelta(hours=hours)

        return Response({
            'window_hours': hours,
            'dropped_messages': self._dropped_messages(company, now),
            'unresolved_messages': self._unresolved_messages(company, now),
            'stuck_receipts': self._stuck_receipts(company),
            'worker_alerts': self._worker_alerts(company, since),
            'baileys_events': self._baileys_events(company, since),
            'activity': self._activity(company, since),
        })

    def _dropped_messages(self, company, now):
        qs = DroppedMessage.objects.filter(account__communication_account__company=company)
        by_reason = {
            row['reason']: row['count']
            for row in qs.values('reason').annotate(count=Count('id')).order_by('-count')
        }
        recent = [
            {
                'id': row.pk, 'account_id': row.account_id, 'reason': row.reason,
                'raw_jid': row.raw_jid, 'created_at': row.created_at, 'resolved_at': row.resolved_at,
            }
            for row in qs.order_by('-created_at')[:RECENT_LIMIT]
        ]
        return {
            'total': qs.count(),
            'last_24h': qs.filter(created_at__gte=now - timedelta(hours=24)).count(),
            'still_unresolved': qs.filter(resolved_at__isnull=True).count(),
            'by_reason': by_reason,
            'recent': recent,
        }

    def _unresolved_messages(self, company, now):
        qs = WhatsAppUnresolvedMessage.objects.filter(account__communication_account__company=company)
        by_status = {
            row['resolution_status']: row['count']
            for row in qs.values('resolution_status').annotate(count=Count('id')).order_by('-count')
        }
        recent = [
            {
                'id': row.pk, 'account_id': row.account_id, 'raw_jid': row.raw_jid, 'lid_jid': row.lid_jid,
                'message_text': (row.message_text or '')[:MESSAGE_TEXT_TRUNCATE_CHARS],
                'resolution_status': row.resolution_status, 'created_at': row.created_at,
            }
            for row in qs.order_by('-created_at')[:RECENT_LIMIT]
        ]
        return {
            'total': qs.count(),
            'last_24h': qs.filter(created_at__gte=now - timedelta(hours=24)).count(),
            'pending': qs.filter(resolution_status=ResolutionStatus.PENDING).count(),
            'by_status': by_status,
            'recent': recent,
        }

    def _stuck_receipts(self, company):
        qs = StuckReceipt.objects.filter(account__communication_account__company=company)
        recent = [
            {
                'id': row.pk, 'account_id': row.account_id, 'remote_jid': row.remote_jid,
                'message_id': row.message_id, 'occurrence_count': row.occurrence_count,
                'first_seen_at': row.first_seen_at, 'last_seen_at': row.last_seen_at,
                'resolved_at': row.resolved_at,
            }
            for row in qs.order_by('-last_seen_at')[:RECENT_LIMIT]
        ]
        return {'total': qs.count(), 'unresolved': qs.filter(resolved_at__isnull=True).count(), 'recent': recent}

    def _worker_alerts(self, company, since):
        qs = WorkerAlert.objects.filter(account__communication_account__company=company, created_at__gte=since)
        by_type = {
            row['alert_type']: row['count']
            for row in qs.values('alert_type').annotate(count=Count('id')).order_by('-count')
        }
        recent = [
            {
                'id': row.pk, 'account_id': row.account_id, 'alert_type': row.alert_type,
                'severity': row.severity, 'message': row.message[:DETAIL_TRUNCATE_CHARS],
                'created_at': row.created_at, 'acknowledged_at': row.acknowledged_at,
            }
            for row in qs.order_by('-created_at')[:RECENT_LIMIT]
        ]
        return {
            'total': qs.count(),
            'unacknowledged': qs.filter(acknowledged_at__isnull=True).count(),
            'by_alert_type': by_type,
            'recent': recent,
        }

    def _baileys_events(self, company, since):
        qs = BaileysEvent.objects.filter(account__communication_account__company=company, created_at__gte=since)
        by_stage = {
            row['event_stage']: row['count']
            for row in qs.values('event_stage').annotate(count=Count('id')).order_by('-count')
        }
        by_reason = {
            row['reason']: row['count']
            for row in qs.exclude(reason='').values('reason').annotate(count=Count('id')).order_by('-count')[:20]
        }
        recent_failures = [
            {
                'id': row.pk, 'account_id': row.account_id, 'event_stage': row.event_stage,
                'status': row.status, 'reason': row.reason,
                'error_message': row.error_message[:DETAIL_TRUNCATE_CHARS],
                'provider_message_id': row.provider_message_id, 'created_at': row.created_at,
            }
            for row in qs.filter(status='failure').order_by('-created_at')[:RECENT_LIMIT]
        ]
        return {
            'window_total': qs.count(),
            'by_stage': by_stage,
            'by_reason': by_reason,
            'recent_failures': recent_failures,
        }

    def _activity(self, company, since):
        qs = SyncLog.objects.filter(account__communication_account__company=company, created_at__gte=since)
        recent = [
            {
                'id': row.pk, 'account_id': row.account_id, 'event_type': row.event_type,
                'status': row.status, 'message': row.message[:DETAIL_TRUNCATE_CHARS],
                'created_at': row.created_at,
            }
            for row in qs.order_by('-created_at')[:RECENT_LIMIT]
        ]
        return {'window_total': qs.count(), 'recent': recent}
