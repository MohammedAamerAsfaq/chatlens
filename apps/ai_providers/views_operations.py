from django.db.models import Count, Sum
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from apps.ai_providers.operations_data import (
    embedding_rows,
    filter_section_queryset,
    sanitize_data,
    section_queryset,
    serialize_row,
)
from apps.tenancy.permissions import CompanyAdminPermission
from apps.tenancy.services.access import default_company_for_user


SECTIONS = ('parsing', 'calls', 'routing', 'reservations', 'embeddings', 'tasks', 'limits')


class AIOperationsViewSet(ViewSet):
    permission_classes = [IsAuthenticated, CompanyAdminPermission]

    @staticmethod
    def _company(request):
        return default_company_for_user(request.user)

    @action(detail=False, methods=['get'])
    def overview(self, request):
        company = self._company(request)
        if not company:
            return Response({'detail': 'An active company is required.'}, status=400)
        counts = {}
        statuses = {}
        for section in SECTIONS:
            if section == 'embeddings':
                rows = embedding_rows(company)
                counts[section] = len(rows)
                status_counts = {}
                for row in rows:
                    status_counts[row['status']] = status_counts.get(row['status'], 0) + 1
                statuses[section] = status_counts
                continue
            queryset = section_queryset(company, section)
            counts[section] = queryset.count()
            if section == 'calls':
                raw_counts = {
                    item['success']: item['count']
                    for item in queryset.values('success').annotate(count=Count('pk'))
                }
                statuses[section] = {
                    'succeeded': raw_counts.get(True, 0),
                    'failed': raw_counts.get(False, 0),
                }
            elif section != 'limits':
                status_field = 'decision' if section == 'routing' else 'status'
                statuses[section] = {
                    str(item[status_field]): item['count']
                    for item in queryset.values(status_field).annotate(count=Count('pk'))
                }
        calls = section_queryset(company, 'calls')
        token_totals = calls.aggregate(input=Sum('input_tokens'), output=Sum('output_tokens'))
        return Response({
            'company': company.name, 'industry': company.industry_type,
            'counts': counts, 'statuses': statuses,
            'tokens': {'input': token_totals['input'] or 0, 'output': token_totals['output'] or 0},
        })

    @action(detail=False, methods=['get'])
    def records(self, request):
        company = self._company(request)
        section = request.query_params.get('section', 'parsing')
        if not company:
            return Response({'detail': 'An active company is required.'}, status=400)
        if section not in SECTIONS:
            return Response({'detail': 'Unknown AI operations section.'}, status=400)
        page = max(1, self._integer(request.query_params.get('page'), 1))
        page_size = min(100, max(10, self._integer(request.query_params.get('page_size'), 25)))
        status_value = request.query_params.get('status', '').strip().lower()
        search = request.query_params.get('search', '').strip().lower()
        if section == 'embeddings':
            rows = embedding_rows(company)
            if status_value:
                rows = [row for row in rows if str(row['status']).lower() == status_value]
            if search:
                rows = [row for row in rows if search in self._search_text(row)]
            count = len(rows)
            start = (page - 1) * page_size
            results = [sanitize_data(row) for row in rows[start:start + page_size]]
        else:
            queryset = filter_section_queryset(
                section_queryset(company, section), section, status_value, search,
            )
            order_field = '-reserved_at' if section == 'reservations' else '-created_at'
            queryset = queryset.order_by(order_field)
            count = queryset.count()
            start = (page - 1) * page_size
            results = [
                sanitize_data(serialize_row(section, row))
                for row in queryset[start:start + page_size]
            ]
        return Response({
            'count': count, 'page': page, 'page_size': page_size,
            'total_pages': max(1, (count + page_size - 1) // page_size),
            'results': results,
        })

    @staticmethod
    def _integer(value, default):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _search_text(row):
        return ' '.join(str(row.get(key, '')) for key in ('id', 'title', 'category', 'status', 'summary')).lower()
