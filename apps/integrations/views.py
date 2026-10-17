from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.queue_management.services import enqueue_task
from apps.tenancy.services.access import control_company_for_platform_admin, is_platform_admin
from apps.tenancy.services.authorization import has_company_permission
from .connectors import GeoNamesClient, GeoNamesError
from .models import (
    AdministrativeArea, City, Country, IntegrationConnection, IntegrationSyncRun, Locality,
)
from .serializers import (
    AdministrativeAreaSerializer, CitySerializer, CountrySerializer,
    IntegrationSyncRunSerializer, LocalitySerializer,
)


def _require(request, code):
    if not has_company_permission(request.user, code):
        raise PermissionDenied('You do not have permission to perform this action.')


def _source_data(connection):
    return {
        'id': connection.pk, 'provider': connection.provider,
        'display_name': connection.display_name, 'scope': connection.scope,
        'username': connection.configuration.get('username', ''),
        'is_enabled': connection.is_enabled, 'status': connection.status,
        'last_checked_at': connection.last_checked_at,
        'last_successful_sync_at': connection.last_successful_sync_at,
        'last_error': connection.last_error,
    }


def _geonames_connection():
    return IntegrationConnection.objects.filter(
        scope=IntegrationConnection.SCOPE_PLATFORM,
        provider=IntegrationConnection.PROVIDER_GEONAMES,
    ).first()


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def overview(request):
    _require(request, 'integrations.connections.view')
    source = _geonames_connection()
    runs = IntegrationSyncRun.objects.select_related('connection').filter(
        connection__provider=IntegrationConnection.PROVIDER_GEONAMES,
    )[:10]
    return Response({
        'can_manage_platform': is_platform_admin(request.user),
        'geonames': _source_data(source) if source else None,
        'geography': {
            'countries': Country.objects.filter(is_active=True).count(),
            'administrative_areas': AdministrativeArea.objects.filter(is_active=True).count(),
            'cities': City.objects.filter(is_active=True).count(),
            'localities': Locality.objects.filter(is_active=True).count(),
            'unmapped_localities': Locality.objects.filter(
                is_active=True, mapping_status=Locality.MAPPING_UNMAPPED,
            ).count(),
        },
        'runs': IntegrationSyncRunSerializer(runs, many=True).data,
    })


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def geography_source(request):
    _require(request, 'integrations.connections.manage')
    if not is_platform_admin(request.user):
        raise PermissionDenied('The shared geography source can only be managed by a platform administrator.')
    username = str(request.data.get('username') or '').strip()
    if not username:
        raise ValidationError({'username': 'GeoNames username is required.'})
    source, _ = IntegrationConnection.objects.update_or_create(
        scope=IntegrationConnection.SCOPE_PLATFORM,
        provider=IntegrationConnection.PROVIDER_GEONAMES,
        defaults={
            'company': None, 'display_name': 'GeoNames Geography',
            'configuration': {'username': username},
            'is_enabled': bool(request.data.get('is_enabled', True)),
            'status': IntegrationConnection.STATUS_NOT_CONFIGURED,
            'last_error': '',
            'created_by': request.user,
        },
    )
    return Response(_source_data(source))


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def test_geography_source(request):
    _require(request, 'integrations.connections.manage')
    if not is_platform_admin(request.user):
        raise PermissionDenied('The shared geography source can only be tested by a platform administrator.')
    source = _geonames_connection()
    if not source:
        raise ValidationError({'detail': 'Configure GeoNames before testing it.'})
    now = timezone.now()
    try:
        country = GeoNamesClient(source.configuration.get('username')).country('AE')
    except GeoNamesError as exc:
        source.status = IntegrationConnection.STATUS_ERROR
        source.last_error = str(exc)
        response_status = status.HTTP_400_BAD_REQUEST
    else:
        source.status = IntegrationConnection.STATUS_READY
        source.last_error = ''
        response_status = status.HTTP_200_OK
    source.last_checked_at = now
    source.save(update_fields=['status', 'last_error', 'last_checked_at', 'updated_at'])
    payload = _source_data(source)
    if response_status == status.HTTP_200_OK:
        payload['sample'] = {'country': country.get('countryName'), 'iso2': country.get('countryCode')}
    return Response(payload, status=response_status)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def sync_geography(request):
    _require(request, 'integrations.sync.execute')
    company = control_company_for_platform_admin(request.user)
    if not company:
        raise PermissionDenied('Shared geography can only be synchronized by a platform administrator.')
    source = _geonames_connection()
    if not source or not source.is_enabled:
        raise ValidationError({'detail': 'Enable and test the GeoNames connection first.'})
    country_code = str(request.data.get('country_code') or 'AE').strip().upper()
    if len(country_code) != 2 or not country_code.isalpha():
        raise ValidationError({'country_code': 'Use a two-letter ISO country code.'})
    try:
        with transaction.atomic():
            run = IntegrationSyncRun.objects.create(
                connection=source, company=company, resource='geography',
                country_code=country_code, requested_by=request.user,
            )
    except IntegrityError:
        run = IntegrationSyncRun.objects.filter(
            connection=source, resource='geography', country_code=country_code,
            status__in=[IntegrationSyncRun.STATUS_PENDING, IntegrationSyncRun.STATUS_RUNNING],
        ).first()
        if run:
            return Response(IntegrationSyncRunSerializer(run).data, status=status.HTTP_202_ACCEPTED)
        raise
    try:
        task = enqueue_task(
            task_key='integrations.sync_geography',
            payload={
                'version': 1, 'connection_id': source.pk,
                'run_id': str(run.pk), 'country_code': country_code,
            },
            idempotency_key=f'integrations:geography:{country_code}:{run.pk}',
            correlation_id=f'integration-sync:{run.pk}', company=company,
            created_by=request.user,
        )
    except Exception as exc:
        run.status = IntegrationSyncRun.STATUS_FAILED
        run.error = str(exc)
        run.finished_at = timezone.now()
        run.save(update_fields=['status', 'error', 'finished_at'])
        raise
    run.background_task_id = task.pk
    run.save(update_fields=['background_task_id'])
    return Response(IntegrationSyncRunSerializer(run).data, status=status.HTTP_202_ACCEPTED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def locations(request):
    _require(request, 'integrations.connections.view')
    level = request.query_params.get('level', 'city')
    search = request.query_params.get('search', '').strip()
    country_code = request.query_params.get('country_code', 'AE').upper()
    models = {
        'country': (Country.objects.all(), CountrySerializer),
        'area': (AdministrativeArea.objects.select_related('country'), AdministrativeAreaSerializer),
        'city': (City.objects.select_related('country', 'administrative_area'), CitySerializer),
        'locality': (
            Locality.objects.select_related('country', 'administrative_area', 'city'),
            LocalitySerializer,
        ),
    }
    if level not in models:
        raise ValidationError({'level': 'Use country, area, city, or locality.'})
    queryset, serializer = models[level]
    queryset = queryset.filter(is_active=True)
    if level != 'country':
        queryset = queryset.filter(country__iso2=country_code)
    if search:
        queryset = queryset.filter(Q(name__icontains=search) | Q(normalized_name__icontains=search))
    if level in {'city', 'locality'} and request.query_params.get('area_id'):
        queryset = queryset.filter(administrative_area_id=request.query_params['area_id'])
    if level == 'locality' and request.query_params.get('city_id'):
        queryset = queryset.filter(city_id=request.query_params['city_id'])
    try:
        page = max(1, int(request.query_params.get('page', 1)))
        page_size = max(1, min(3000, int(request.query_params.get('page_size', 25))))
    except (TypeError, ValueError):
        page, page_size = 1, 25
    count = queryset.count()
    start = (page - 1) * page_size
    return Response({
        'count': count, 'page': page, 'page_size': page_size,
        'results': serializer(queryset[start:start + page_size], many=True).data,
    })
