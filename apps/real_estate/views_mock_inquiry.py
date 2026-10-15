from django.db.models import Count
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.queue_management.services import enqueue_task
from apps.real_estate.api_base import CompanyOwnedViewSet
from apps.real_estate.models import (
    RealEstateMockInquiry, RealEstateMockInquiryRun, RealEstateMockSourceRecord,
)
from apps.real_estate.serializers import RealEstateMockInquirySerializer
from apps.real_estate.serializers.mock_inquiry import RealEstateMockInquiryRunSerializer
from apps.real_estate.services.mock_inquiry_cleanup import clear_mock_inquiries, reconcile_mock_inquiries
from apps.real_estate.services.mock_inquiry_profiles import PROFILES, dataset_profiles


class MockInquiryViewSet(CompanyOwnedViewSet):
    queryset = RealEstateMockInquiry.objects.select_related(
        'run', 'source_record', 'live_task', 'message__real_estate_parse_log',
        'message__real_estate_opportunity', 'message__embedding',
    )
    serializer_class = RealEstateMockInquirySerializer
    read_permission = 'real_estate.properties.view'
    write_permission = 'real_estate.properties.manage'
    http_method_names = ['get', 'post', 'delete', 'head', 'options']

    def get_queryset(self):
        reconcile_mock_inquiries(self.active_company())
        qs = super().get_queryset()
        if value := self.request.query_params.get('run_id'):
            qs = qs.filter(run_id=value)
        if value := self.request.query_params.get('status'):
            qs = qs.filter(status=value)
        return qs.order_by('-created_at')

    @action(detail=False, methods=['get'])
    def datasets(self, request):
        return Response({'datasets': dataset_profiles(self.active_company())})

    @action(detail=False, methods=['get'])
    def runs(self, request):
        rows = RealEstateMockInquiryRun.objects.filter(
            company=self.active_company(),
        ).select_related('task', 'mock_account')[:25]
        return Response({'results': RealEstateMockInquiryRunSerializer(rows, many=True).data})

    @action(detail=False, methods=['get'])
    def summary(self, request):
        company = self.active_company()
        reconcile_mock_inquiries(company)
        inquiry_counts = {
            row['status']: row['total'] for row in RealEstateMockInquiry.objects.filter(
                company=company,
            ).values('status').annotate(total=Count('id'))
        }
        return Response({
            'runs': RealEstateMockInquiryRun.objects.filter(company=company).count(),
            'queued': inquiry_counts.get('queued', 0),
            'ingested': inquiry_counts.get('ingested', 0),
            'failed': inquiry_counts.get('failed', 0),
            'ai_parsing_enabled': company.ai_parsing_enabled,
        })

    @action(detail=False, methods=['post'], url_path='start-run')
    def start_run(self, request):
        company = self.active_company()
        source_file_name = str(request.data.get('source_file_name') or '').strip()
        profile = PROFILES.get(source_file_name)
        if not profile:
            raise ValidationError({'source_file_name': 'Select a supported first-phase dataset.'})
        try:
            requested_count = int(request.data.get('record_count'))
        except (TypeError, ValueError):
            raise ValidationError({'record_count': 'Choose 1, 10, or 100 records.'})
        if requested_count not in {1, 10, 100}:
            raise ValidationError({'record_count': 'Choose 1, 10, or 100 records.'})
        if not RealEstateMockSourceRecord.objects.filter(
            company=company, source_file_name=source_file_name,
            row_kind='data', processing_status='pending',
        ).exists():
            raise ValidationError({
                'source_file_name': 'This dataset has no pending data rows to mock.',
            })
        if RealEstateMockInquiryRun.objects.filter(
            company=company, status__in=['pending', 'running'],
        ).exists():
            return Response(
                {'detail': 'Wait for the active mock inquiry run to finish.'},
                status=status.HTTP_409_CONFLICT,
            )
        run = RealEstateMockInquiryRun.objects.create(
            company=company, source_file_name=source_file_name,
            activity_type=profile.activity_type, requested_count=requested_count,
            created_by=request.user,
        )
        task = enqueue_task(
            task_key='real_estate.generate_mock_inquiries',
            payload={'version': 1, 'company_id': company.pk, 'run_id': str(run.pk)},
            idempotency_key=f'real-estate-mock-inquiries:{run.pk}',
            correlation_id=f'real-estate-mock-run:{run.pk}',
            company=company, created_by=request.user,
        )
        run.task = task
        run.save(update_fields=['task', 'updated_at'])
        return Response(RealEstateMockInquiryRunSerializer(run).data, status=status.HTTP_202_ACCEPTED)

    @action(detail=False, methods=['delete'], url_path='clear-all')
    def clear_all(self, request):
        try:
            result = clear_mock_inquiries(self.active_company())
        except RuntimeError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(result)
