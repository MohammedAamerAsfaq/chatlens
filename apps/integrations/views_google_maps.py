import uuid

from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.tenancy.services.access import is_platform_admin
from apps.tenancy.services.authorization import has_company_permission
from .connectors import GoogleMapsError
from .models import City, GeographyExternalReference, IntegrationConnection, Locality
from .serializers import LocalitySerializer
from .services.google_maps import (
    GoogleMapsQuotaError, client_for, default_locality_query, google_maps_connection,
    place_country_code, reserve_request, source_data,
)


def _require_platform_manager(request):
    if not has_company_permission(request.user, 'integrations.connections.manage'):
        raise PermissionDenied('You do not have permission to perform this action.')
    if not is_platform_admin(request.user):
        raise PermissionDenied('Google Maps geography can only be managed by a platform administrator.')


def _ready_connection():
    connection = google_maps_connection()
    if not connection or not connection.is_enabled:
        raise ValidationError({'detail': 'Configure and enable Google Maps first.'})
    return connection


def _provider_error(connection, error):
    connection.status = IntegrationConnection.STATUS_ERROR
    connection.last_error = str(error)
    connection.last_checked_at = timezone.now()
    connection.save(update_fields=['status', 'last_error', 'last_checked_at', 'updated_at'])
    return Response({'detail': str(error)}, status=status.HTTP_400_BAD_REQUEST)


def _quota_error(error):
    return Response({'detail': str(error)}, status=status.HTTP_429_TOO_MANY_REQUESTS)


@api_view(['POST', 'PUT'])
@permission_classes([IsAuthenticated])
def google_maps_source(request):
    _require_platform_manager(request)
    try:
        request_limit = int(request.data.get('monthly_request_limit', 100))
    except ValueError as exc:
        raise ValidationError({'detail': str(exc)}) from exc
    if not 1 <= request_limit <= 100000:
        raise ValidationError({'monthly_request_limit': 'Use a value from 1 to 100000.'})
    connection = google_maps_connection()
    api_key = str(request.data.get('api_key') or '').strip()
    if not api_key and not (connection and connection.secret_value):
        raise ValidationError({'api_key': 'Google Maps API key is required.'})
    defaults = {
        'company': None,
        'display_name': 'Google Maps Geography',
        'configuration': {'monthly_request_limit': request_limit},
        'secret_reference': '',
        'is_enabled': bool(request.data.get('is_enabled', False)),
        'created_by': request.user,
    }
    if api_key:
        defaults['secret_value'] = api_key
        defaults['status'] = IntegrationConnection.STATUS_NOT_CONFIGURED
        defaults['last_error'] = ''
    connection, _ = IntegrationConnection.objects.update_or_create(
        scope=IntegrationConnection.SCOPE_PLATFORM,
        provider=IntegrationConnection.PROVIDER_GOOGLE_MAPS,
        defaults=defaults,
    )
    return Response(source_data(connection))


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def test_google_maps_source(request):
    _require_platform_manager(request)
    connection = _ready_connection()
    token = str(uuid.uuid4())
    try:
        reserve_request(connection, 'autocomplete')
        matches = client_for(connection).autocomplete(
            'Dubai, United Arab Emirates', country_code='AE', session_token=token,
        )
    except GoogleMapsQuotaError as exc:
        return _quota_error(exc)
    except GoogleMapsError as exc:
        return _provider_error(connection, exc)
    connection.status = IntegrationConnection.STATUS_READY
    connection.last_error = ''
    connection.last_checked_at = timezone.now()
    connection.save(update_fields=['status', 'last_error', 'last_checked_at', 'updated_at'])
    payload = source_data(connection)
    payload['sample'] = matches[:1]
    return Response(payload)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def locality_suggestions(request, locality_id):
    _require_platform_manager(request)
    connection = _ready_connection()
    locality = Locality.objects.select_related(
        'country', 'administrative_area',
    ).filter(pk=locality_id, is_active=True).first()
    if not locality:
        raise ValidationError({'locality_id': 'Locality was not found.'})
    query = str(request.data.get('query') or default_locality_query(locality)).strip()
    token = str(uuid.uuid4())
    try:
        reserve_request(connection, 'autocomplete')
        matches = client_for(connection).autocomplete(
            query, country_code=locality.country.iso2, session_token=token,
        )
    except GoogleMapsQuotaError as exc:
        return _quota_error(exc)
    except GoogleMapsError as exc:
        return _provider_error(connection, exc)
    return Response({
        'query': query, 'session_token': token, 'results': matches,
        'usage': source_data(connection)['usage'],
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def resolve_locality(request, locality_id):
    _require_platform_manager(request)
    connection = _ready_connection()
    locality = Locality.objects.select_related('country', 'administrative_area').filter(
        pk=locality_id, is_active=True,
    ).first()
    place_id = str(request.data.get('place_id') or '').strip()
    session_token = str(request.data.get('session_token') or '').strip()
    try:
        city_id = int(request.data.get('city_id'))
    except (TypeError, ValueError):
        city_id = None
    city = City.objects.select_related('country', 'administrative_area').filter(
        pk=city_id, is_active=True,
    ).first()
    if not locality or not place_id or not session_token or not city:
        raise ValidationError({'detail': 'Locality, Google place, session, and city are required.'})
    if city.country_id != locality.country_id:
        raise ValidationError({'city_id': 'The city must belong to the locality country.'})
    if locality.administrative_area_id and city.administrative_area_id != locality.administrative_area_id:
        raise ValidationError({'city_id': 'The city must belong to the locality administrative area.'})
    try:
        reserve_request(connection, 'place_details')
        details = client_for(connection).place_details(place_id, session_token=session_token)
    except GoogleMapsQuotaError as exc:
        return _quota_error(exc)
    except GoogleMapsError as exc:
        return _provider_error(connection, exc)
    if details.get('id') != place_id or place_country_code(details) != locality.country.iso2:
        raise ValidationError({'place_id': 'Google place details do not match this locality country.'})
    conflict = GeographyExternalReference.objects.filter(
        provider=GeographyExternalReference.PROVIDER_GOOGLE_MAPS,
        external_id=place_id,
    ).exclude(locality=locality).exists()
    if conflict:
        raise ValidationError({'place_id': 'This Google place is already linked to another locality.'})
    now = timezone.now()
    with transaction.atomic():
        GeographyExternalReference.objects.update_or_create(
            locality=locality,
            provider=GeographyExternalReference.PROVIDER_GOOGLE_MAPS,
            defaults={
                'city': city, 'external_id': place_id,
                'status': GeographyExternalReference.STATUS_VERIFIED,
                'resolved_by': request.user, 'verified_at': now, 'last_checked_at': now,
            },
        )
        locality.city = city
        locality.mapping_status = Locality.MAPPING_MAPPED
        locality.save(update_fields=['city', 'mapping_status', 'updated_at'])
    locality = Locality.objects.select_related(
        'country', 'administrative_area', 'city',
    ).prefetch_related('external_references').get(pk=locality.pk)
    return Response({
        'locality': LocalitySerializer(locality).data,
        'usage': source_data(connection)['usage'],
    })
