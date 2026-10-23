"""Company-scoped Real Estate AI-parse-cycle diagnostics for the external API.

Mirrors external_diagnostics_views.py's approach (apiconsumer data:read key, never
sees anything outside that key's own company) but for the real estate pipeline
instead of WhatsApp ingestion: gate -> extraction -> the resulting opportunity.

RealEstateParseLog and RealEstateAgentCallLog both carry a direct company FK
(unlike the WhatsApp diagnostics models, which only reach their company through
account__communication_account), so filtering here is a plain company=... lookup.

Three access points:
  - RealEstateDiagnosticsView: one-shot overview (counts/breakdowns/stuck-in-progress
    detection), same shape as the WhatsApp DiagnosticsView.
  - RealEstateParseLogViewSet: paginated, filterable drill-down into individual parse
    cycles - the actual gate/extraction request+response+duration for one message.
  - RealEstateAgentCallLogViewSet: paginated, filterable drill-down into the raw AI
    calls (gate/extraction/match_rerank), reachable with the apiconsumer key where
    the existing internal apps/real_estate/views_prompts.py agent-logs action is not.
"""
from datetime import timedelta

from django.db.models import Avg, Count, Q, Sum
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.real_estate.models import RealEstateAgentCallLog, RealEstateParseLog

from .external_views import ExternalApiMixin
from .models import ApiKey
from .pagination import ApiKeyPageNumberPagination
from .real_estate_diagnostics_serializers import (
    RealEstateAgentCallLogSerializer, RealEstateParseLogSerializer,
)

RECENT_LIMIT = 20
DEFAULT_WINDOW_HOURS = 24
MAX_WINDOW_HOURS = 24 * 14
DETAIL_TRUNCATE_CHARS = 500
# A parse log still sitting in an in-progress status this long after creation almost
# certainly means its task crashed or was lost rather than that it's still running -
# gate/extraction calls normally finish in seconds, not minutes.
STUCK_IN_PROGRESS_MINUTES = 15
IN_PROGRESS_STATUSES = (
    RealEstateParseLog.STATUS_GATE_PENDING, RealEstateParseLog.STATUS_GATE_RUNNING,
    RealEstateParseLog.STATUS_EXTRACT_PENDING, RealEstateParseLog.STATUS_EXTRACT_RUNNING,
)


class RealEstateDiagnosticsView(ExternalApiMixin, APIView):
    """Real estate AI-parse-cycle health for the key's own company: parse-log status
    breakdown, stuck-in-progress detection, and raw AI call stats (gate/extraction/
    match_rerank) - everything needed to answer "is the parse pipeline keeping up and
    where is it failing", scoped strictly to this key's company.
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
            'parse_logs': self._parse_logs(company, now, since),
            'agent_calls': self._agent_calls(company, since),
        })

    def _parse_logs(self, company, now, since):
        qs = RealEstateParseLog.objects.filter(company=company)
        window = qs.filter(created_at__gte=since)
        by_status = {
            row['status']: row['count']
            for row in window.values('status').annotate(count=Count('id')).order_by('-count')
        }
        by_gate_decision = {
            row['gate_decision']: row['count']
            for row in window.exclude(gate_decision='').values('gate_decision').annotate(count=Count('id')).order_by('-count')
        }
        by_skip_reason = {
            row['skip_reason']: row['count']
            for row in window.exclude(skip_reason='').values('skip_reason').annotate(count=Count('id')).order_by('-count')
        }
        stuck = qs.filter(
            status__in=IN_PROGRESS_STATUSES,
            created_at__lt=now - timedelta(minutes=STUCK_IN_PROGRESS_MINUTES),
        )
        recent_errors = [
            {
                'id': row.pk, 'message_id': row.message_id, 'opportunity_id': row.opportunity_id,
                'status': row.status, 'gate_decision': row.gate_decision,
                'error': row.error[:DETAIL_TRUNCATE_CHARS], 'created_at': row.created_at,
            }
            for row in window.filter(status=RealEstateParseLog.STATUS_ERROR).order_by('-created_at')[:RECENT_LIMIT]
        ]
        return {
            'window_total': window.count(),
            'by_status': by_status,
            'by_gate_decision': by_gate_decision,
            'by_skip_reason': by_skip_reason,
            'stuck_in_progress': {
                'count': stuck.count(),
                'threshold_minutes': STUCK_IN_PROGRESS_MINUTES,
                'recent': [
                    {
                        'id': row.pk, 'message_id': row.message_id, 'status': row.status,
                        'created_at': row.created_at,
                    }
                    for row in stuck.order_by('created_at')[:RECENT_LIMIT]
                ],
            },
            'recent_errors': recent_errors,
        }

    def _agent_calls(self, company, since):
        qs = RealEstateAgentCallLog.objects.filter(company=company, created_at__gte=since)
        by_purpose = {}
        for row in qs.values('purpose').annotate(
            count=Count('id'), failures=Count('id', filter=Q(success=False)),
            avg_duration_ms=Avg('duration_ms'), total_input_tokens=Sum('input_tokens'),
            total_output_tokens=Sum('output_tokens'),
        ):
            by_purpose[row['purpose']] = {
                'count': row['count'], 'failures': row['failures'],
                'avg_duration_ms': round(row['avg_duration_ms'] or 0),
                'total_input_tokens': row['total_input_tokens'] or 0,
                'total_output_tokens': row['total_output_tokens'] or 0,
            }
        recent_failures = [
            {
                'id': row.pk, 'purpose': row.purpose, 'provider': row.provider, 'model': row.model,
                'error': row.error[:DETAIL_TRUNCATE_CHARS], 'wa_message_id': row.wa_message_id,
                'created_at': row.created_at,
            }
            for row in qs.filter(success=False).order_by('-created_at')[:RECENT_LIMIT]
        ]
        return {
            'window_total': qs.count(),
            'by_purpose': by_purpose,
            'recent_failures': recent_failures,
        }


class RealEstateParseLogViewSet(ExternalApiMixin, viewsets.ReadOnlyModelViewSet):
    """Full per-message parse-cycle detail - gate and extraction request/response/
    duration, the resulting opportunity, and any error - for drilling into one
    specific message's AI parse cycle rather than just the aggregate counts above."""

    required_scope = ApiKey.SCOPE_DATA_READ
    serializer_class = RealEstateParseLogSerializer
    pagination_class = ApiKeyPageNumberPagination

    def get_queryset(self):
        qs = RealEstateParseLog.objects.filter(company=self.request.auth.company)
        params = self.request.query_params
        if status := params.get('status'):
            qs = qs.filter(status=status)
        if gate_decision := params.get('gate_decision'):
            qs = qs.filter(gate_decision=gate_decision)
        if message_id := params.get('message_id'):
            qs = qs.filter(message_id=message_id)
        return qs


class RealEstateAgentCallLogViewSet(ExternalApiMixin, viewsets.ReadOnlyModelViewSet):
    """Full raw AI call detail (messages sent, response, tokens, duration) for every
    gate/extraction/match_rerank call - the apiconsumer-key-reachable equivalent of
    apps/real_estate/views_prompts.py's agent-logs action, which requires a Django
    session and is unreachable with this key."""

    required_scope = ApiKey.SCOPE_DATA_READ
    serializer_class = RealEstateAgentCallLogSerializer
    pagination_class = ApiKeyPageNumberPagination

    def get_queryset(self):
        qs = RealEstateAgentCallLog.objects.filter(company=self.request.auth.company)
        params = self.request.query_params
        if purpose := params.get('purpose'):
            qs = qs.filter(purpose=purpose)
        if success := params.get('success'):
            qs = qs.filter(success=success.lower() == 'true')
        return qs
