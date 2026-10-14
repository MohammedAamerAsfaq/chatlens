from uuid import uuid4

from django.db.models import Count, Q
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.queue_management.services import enqueue_task
from apps.real_estate.api_base import CompanyOwnedViewSet
from apps.real_estate.models import RealEstateMockSourceRecord
from apps.real_estate.serializers import RealEstateMockSourceRecordSerializer
from apps.real_estate.services.mock_source_files import available_workbooks, resolve_workbooks
from apps.task_management.models import BackgroundTask


class MockSourceRecordViewSet(CompanyOwnedViewSet):
    queryset = RealEstateMockSourceRecord.objects.all()
    serializer_class = RealEstateMockSourceRecordSerializer
    read_permission = 'real_estate.properties.view'
    write_permission = 'real_estate.properties.manage'
    http_method_names = ['get', 'post', 'delete', 'head', 'options']

    def get_queryset(self):
        qs = super().get_queryset()
        if value := self.request.query_params.get('source_file_name'):
            qs = qs.filter(source_file_name=value)
        if value := self.request.query_params.get('row_kind'):
            qs = qs.filter(row_kind=value)
        if value := self.request.query_params.get('processing_status'):
            qs = qs.filter(processing_status=value)
        if search := self.request.query_params.get('search'):
            qs = qs.filter(
                Q(source_file_name__icontains=search)
                | Q(source_sheet_name__icontains=search)
                | Q(processing_notes__icontains=search)
            )
        ordering = self.request.query_params.get('ordering', '-imported_at')
        allowed = {
            'source_file_name', 'source_sheet_name', 'source_sheet_index',
            'source_row_number', 'row_kind', 'processing_status', 'imported_at',
        }
        return qs.order_by(ordering if ordering.lstrip('-') in allowed else '-imported_at')

    @action(detail=False, methods=['get'], url_path='available-files')
    def available_files(self, request):
        return Response({'files': available_workbooks()})

    @action(detail=False, methods=['get'])
    def summary(self, request):
        qs = super().get_queryset()
        totals = qs.aggregate(
            records=Count('id'), files=Count('source_file_name', distinct=True),
            runs=Count('import_run_id', distinct=True),
        )
        sheets = qs.values('source_file_name', 'source_sheet_index').distinct().count()
        return Response({**totals, 'sheets': sheets})

    @action(detail=False, methods=['post'], url_path='import-files')
    def import_files(self, request):
        company = self.active_company()
        import_all = request.data.get('import_all') is True
        file_names = None if import_all else request.data.get('file_names')
        if not import_all and not isinstance(file_names, list):
            raise ValidationError({'file_names': 'Select one or more workbooks.'})
        resolved = resolve_workbooks(file_names)
        run_id = uuid4()
        task = enqueue_task(
            task_key='real_estate.import_mock_sources',
            payload={
                'version': 1,
                'company_id': company.pk,
                'import_run_id': str(run_id),
                'file_names': None if import_all else [name for name, _ in resolved],
            },
            idempotency_key=f'real-estate-mock-import:{company.pk}',
            correlation_id=f'real-estate-mock-import:{company.pk}:{run_id}',
            company=company,
            created_by=request.user,
        )
        return Response({
            'task_id': task.pk,
            'status': task.status,
            'import_run_id': task.payload['import_run_id'],
            'files_queued': len(resolved),
        }, status=status.HTTP_202_ACCEPTED)

    @action(detail=False, methods=['delete'], url_path='delete-all')
    def delete_all(self, request):
        company = self.active_company()
        active = BackgroundTask.objects.filter(
            company=company,
            task_key='real_estate.import_mock_sources',
            status__in=BackgroundTask.ACTIVE_STATUSES,
        ).exists()
        if active:
            return Response(
                {'detail': 'Wait for the active mock-source import to finish before deleting records.'},
                status=status.HTTP_409_CONFLICT,
            )
        deleted, _ = super().get_queryset().delete()
        return Response({'deleted': deleted})
