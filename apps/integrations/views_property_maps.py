import uuid

from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.tenancy.services.authorization import has_company_permission
from .connectors import GoogleMapsError
from .models import IntegrationConnection
from .services.google_maps import (
    GoogleMapsQuotaError, client_for, google_maps_connection, place_country_code,
    property_address, reserve_request, source_data,
)


def _connection(request):
    if not has_company_permission(request.user, 'real_estate.properties.manage'):
        raise PermissionDenied('You do not have permission to manage properties.')
    connection = google_maps_connection()
    if not connection or not connection.is_enabled:
        raise ValidationError({'detail': 'Configure and enable Google Maps first.'})
    return connection


def _error(connection, error):
    if isinstance(error, GoogleMapsQuotaError):
        return Response({'detail': str(error)}, status=status.HTTP_429_TOO_MANY_REQUESTS)
    connection.status = IntegrationConnection.STATUS_ERROR
    connection.last_error = str(error)
    connection.last_checked_at = timezone.now()
    connection.save(update_fields=['status', 'last_error', 'last_checked_at', 'updated_at'])
    return Response({'detail': str(error)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def property_map_config(request):
    connection = _connection(request)
    browser_key = str(connection.configuration.get('browser_api_key') or '').strip()
    if not browser_key:
        raise ValidationError({
            'detail': 'Configure a browser-restricted Maps JavaScript API key first.',
        })
    return Response({'browser_api_key': browser_key})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def property_address_suggestions(request):
    connection = _connection(request)
    query = str(request.data.get('query') or '').strip()
    country_code = str(request.data.get('country_code') or 'AE').strip().upper()
    session_token = str(request.data.get('session_token') or uuid.uuid4()).strip()
    if len(query) < 3:
        raise ValidationError({'query': 'Enter at least 3 characters.'})
    if len(country_code) != 2:
        raise ValidationError({'country_code': 'Use a two-letter country code.'})
    try:
        reserve_request(connection, 'property_autocomplete')
        matches = client_for(connection).autocomplete(
            query, country_code=country_code, session_token=session_token,
        )
    except (GoogleMapsQuotaError, GoogleMapsError) as exc:
        return _error(connection, exc)
    return Response({
        'session_token': session_token,
        'results': matches,
        'usage': source_data(connection)['usage'],
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def property_place_details(request):
    connection = _connection(request)
    place_id = str(request.data.get('place_id') or '').strip()
    session_token = str(request.data.get('session_token') or '').strip()
    country_code = str(request.data.get('country_code') or 'AE').strip().upper()
    if not place_id or not session_token:
        raise ValidationError({'detail': 'Google place and autocomplete session are required.'})
    try:
        reserve_request(connection, 'property_place_details')
        details = client_for(connection).place_details(place_id, session_token=session_token)
    except (GoogleMapsQuotaError, GoogleMapsError) as exc:
        return _error(connection, exc)
    if details.get('id') != place_id or place_country_code(details) != country_code:
        raise ValidationError({'place_id': 'Google place details do not match the selected country.'})
    return Response({
        'place_id': place_id,
        'address': property_address(details),
        'usage': source_data(connection)['usage'],
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def property_reverse_geocode(request):
    connection = _connection(request)
    country_code = str(request.data.get('country_code') or 'AE').strip().upper()
    try:
        latitude = float(request.data.get('latitude'))
        longitude = float(request.data.get('longitude'))
    except (TypeError, ValueError) as exc:
        raise ValidationError({'detail': 'Valid latitude and longitude are required.'}) from exc
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise ValidationError({'detail': 'Coordinates are outside the valid range.'})
    try:
        reserve_request(connection, 'property_reverse_geocode')
        details = client_for(connection).reverse_geocode(latitude, longitude)
    except (GoogleMapsQuotaError, GoogleMapsError) as exc:
        return _error(connection, exc)
    if not details:
        raise ValidationError({'detail': 'No address was found at this map location.'})
    if country_code and place_country_code(details) != country_code:
        raise ValidationError({'detail': 'The selected map location is outside the selected country.'})
    return Response({
        'place_id': details.get('id') or '',
        'address': property_address(details),
        'usage': source_data(connection)['usage'],
    })
