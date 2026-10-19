from django.db import transaction
from django.utils import timezone

from apps.integrations.connectors import GoogleMapsClient
from apps.integrations.models import IntegrationConnection, IntegrationUsagePeriod


DEFAULT_MONTHLY_LIMIT = 100
class GoogleMapsQuotaError(RuntimeError):
    pass


def google_maps_connection():
    return IntegrationConnection.objects.filter(
        scope=IntegrationConnection.SCOPE_PLATFORM,
        provider=IntegrationConnection.PROVIDER_GOOGLE_MAPS,
    ).first()


def monthly_limit(connection):
    try:
        return max(1, int(connection.configuration.get('monthly_request_limit', DEFAULT_MONTHLY_LIMIT)))
    except (TypeError, ValueError):
        return DEFAULT_MONTHLY_LIMIT


def current_period_start():
    today = timezone.localdate()
    return today.replace(day=1)


def usage_snapshot(connection):
    limit = monthly_limit(connection)
    usage = IntegrationUsagePeriod.objects.filter(
        connection=connection, period_start=current_period_start(),
    ).first()
    count = usage.request_count if usage else 0
    return {
        'period_start': current_period_start(),
        'request_count': count,
        'remaining': max(0, limit - count),
        'monthly_request_limit': limit,
        'operation_counts': usage.operation_counts if usage else {},
    }


def source_data(connection):
    if not connection:
        return None
    return {
        'id': connection.pk,
        'provider': connection.provider,
        'display_name': connection.display_name,
        'scope': connection.scope,
        'api_key_configured': bool(connection.secret_value),
        'api_key_masked': masked_secret(connection.secret_value),
        'browser_api_key_configured': bool(
            (connection.configuration or {}).get('browser_api_key', '')
        ),
        'browser_api_key_masked': masked_secret(
            (connection.configuration or {}).get('browser_api_key', '')
        ),
        'is_enabled': connection.is_enabled,
        'status': connection.status,
        'last_checked_at': connection.last_checked_at,
        'last_error': connection.last_error,
        'usage': usage_snapshot(connection),
    }


def client_for(connection):
    return GoogleMapsClient(connection.secret_value)


def masked_secret(value):
    secret = str(value or '')
    if not secret:
        return ''
    if len(secret) <= 8:
        return '********'
    return f'{secret[:4]}****{secret[-4:]}'


def reserve_request(connection, operation):
    with transaction.atomic():
        # One provider connection lock serializes the first request of a new month too.
        IntegrationConnection.objects.select_for_update().get(pk=connection.pk)
        usage, _ = IntegrationUsagePeriod.objects.get_or_create(
            connection=connection,
            period_start=current_period_start(),
        )
        limit = monthly_limit(connection)
        if usage.request_count >= limit:
            raise GoogleMapsQuotaError(
                f'Google Maps monthly request cap of {limit} has been reached.'
            )
        operations = dict(usage.operation_counts or {})
        operations[operation] = int(operations.get(operation, 0)) + 1
        usage.request_count += 1
        usage.operation_counts = operations
        usage.save(update_fields=['request_count', 'operation_counts', 'updated_at'])
    return usage_snapshot(connection)


def default_locality_query(locality):
    parts = [locality.name]
    if locality.administrative_area_id:
        parts.append(locality.administrative_area.name)
    parts.append(locality.country.name)
    return ', '.join(dict.fromkeys(part for part in parts if part))


def place_country_code(details):
    for component in details.get('addressComponents') or []:
        if 'country' in (component.get('types') or []):
            return str(component.get('shortText') or '').upper()
    return ''


def property_address(details):
    components = {}
    for component in details.get('addressComponents') or []:
        for component_type in component.get('types') or []:
            components.setdefault(component_type, component)

    def long_value(*types):
        for component_type in types:
            value = (components.get(component_type) or {}).get('longText')
            if value:
                return value
        return ''

    location = details.get('location') or {}
    street = ' '.join(filter(None, [
        long_value('street_number'), long_value('route'),
    ]))
    return {
        'country': long_value('country'),
        'state_region': long_value('administrative_area_level_1'),
        'city': long_value(
            'locality', 'postal_town', 'administrative_area_level_2',
        ),
        'community': long_value(
            'sublocality_level_1', 'sublocality', 'neighborhood',
        ),
        'project_building': long_value('premise'),
        'street': street,
        'unit_number': long_value('subpremise'),
        'postal_code': long_value('postal_code'),
        'latitude': location.get('latitude'),
        'longitude': location.get('longitude'),
        'normalized_location': details.get('formattedAddress') or '',
    }
