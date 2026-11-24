"""Area map report: how many inquiries mention each area, and where each area is.

Inquiry locations are free text (OpportunityItem.locations, as brokers write them). Each
distinct normalized name is placed once per company and remembered in AreaLocation:

1. the geography directory (GeoNames localities, cities and emirates of the company's
   country) when the name matches exactly one place at the most specific level - free;
2. otherwise Google Maps text search, only when someone asks for it, one request per
   name, inside the Google Maps monthly request cap.

Names that cannot be placed stay in the report with the reason, never dropped.
"""

from collections import Counter, defaultdict

from django.utils import timezone

from apps.integrations.connectors import GoogleMapsError
from apps.integrations.models import AdministrativeArea, City, Country, Locality
from apps.integrations.services.geography_sync import normalize_name
from apps.integrations.services.google_maps import (
    GoogleMapsQuotaError, client_for, google_maps_connection, place_country_code,
    reserve_request, usage_snapshot,
)
from apps.real_estate.models import AreaLocation, OpportunityItem, RealEstateSettings

GOOGLE_BATCH = 20
MAX_NAME_LENGTH = 200


def company_country(company):
    settings_row, _ = RealEstateSettings.objects.get_or_create(company=company)
    wanted = normalize_name(settings_row.default_country)
    country = Country.objects.filter(normalized_name=wanted).first()
    if not country:
        raise ValueError(
            f'The Real Estate default country "{settings_row.default_country}" is not in the '
            'geography directory, so areas cannot be placed on the map.'
        )
    return country


def area_counts(opportunities):
    """{normalized name: {'name', 'opportunities': set, 'by_activity': Counter}} plus the
    number of opportunities with no location at all."""
    areas = defaultdict(lambda: {'spellings': Counter(), 'opportunities': set(), 'by_activity': Counter()})
    located = set()
    rows = OpportunityItem.objects.filter(opportunity__in=opportunities).values_list(
        'opportunity_id', 'opportunity__activity_type', 'locations', 'location_raw',
    )
    for opportunity_id, activity, locations, raw in rows.iterator():
        names = [value for value in (locations or []) if isinstance(value, str) and value.strip()]
        if not names and (raw or '').strip():
            names = [raw]
        for name in names:
            name = name.strip()[:MAX_NAME_LENGTH]
            key = normalize_name(name)
            if not key:
                continue
            area = areas[key]
            area['spellings'][name] += 1
            if opportunity_id not in area['opportunities']:
                area['opportunities'].add(opportunity_id)
                area['by_activity'][activity] += 1
            located.add(opportunity_id)
    total = opportunities.count()
    for area in areas.values():
        area['name'] = area.pop('spellings').most_common(1)[0][0]
    return dict(areas), total, total - len(located)


def place_from_directory(company, areas):
    """Create the AreaLocation rows for names not seen before, placed from the directory
    when it has exactly one match, otherwise left waiting for Google."""
    known = set(AreaLocation.objects.filter(company=company, normalized_name__in=list(areas)).values_list('normalized_name', flat=True))
    new = [key for key in areas if key not in known]
    if not new:
        return
    index = _directory_index(company_country(company))
    now = timezone.now()
    rows = []
    for key in new:
        row = AreaLocation(company=company, normalized_name=key, name=areas[key]['name'])
        match = _directory_match(index, key)
        if match:
            row.status, row.source = AreaLocation.STATUS_PLACED, AreaLocation.SOURCE_DIRECTORY
            row.latitude, row.longitude = match.latitude, match.longitude
            row.matched_label = str(match)
            row.resolved_at = now
        rows.append(row)
    AreaLocation.objects.bulk_create(rows, ignore_conflicts=True)


def place_with_google(company, areas):
    """Look up the waiting names with the most inquiries on Google, up to GOOGLE_BATCH.
    Returns a notice to show, or '' when everything went through."""
    connection = google_maps_connection()
    if not connection or not connection.is_enabled:
        raise ValueError('Google Maps is not configured or not enabled in Integrations.')
    country = company_country(company)
    waiting = {
        row.normalized_name: row
        for row in AreaLocation.objects.filter(
            company=company, normalized_name__in=list(areas),
            status__in=[AreaLocation.STATUS_PENDING, AreaLocation.STATUS_ERROR],
        )
    }
    order = sorted(waiting, key=lambda key: -len(areas[key]['opportunities']))[:GOOGLE_BATCH]
    client = client_for(connection)
    for key in order:
        row = waiting[key]
        try:
            reserve_request(connection, 'area_map_search')
        except GoogleMapsQuotaError as exc:
            return f'{exc} The remaining areas stay off the map until next month or until the cap is raised.'
        try:
            place = client.search_text(f'{row.name}, {country.name}', region_code=country.iso2)
        except GoogleMapsError as exc:
            row.status, row.error = AreaLocation.STATUS_ERROR, str(exc)
            row.save(update_fields=['status', 'error', 'updated_at'])
            return f'Google Maps lookup failed: {exc}'
        _apply_google_result(row, place, country)
    return ''


def area_map_report(company, opportunities):
    areas, total, without_location = area_counts(opportunities)
    place_from_directory(company, areas)
    rows = {row.normalized_name: row for row in AreaLocation.objects.filter(company=company, normalized_name__in=list(areas))}
    items = []
    for key, area in areas.items():
        row = rows.get(key)
        items.append({
            'key': key,
            'name': area['name'],
            'count': len(area['opportunities']),
            'by_activity': dict(area['by_activity']),
            'status': row.status if row else AreaLocation.STATUS_PENDING,
            'source': row.source if row else '',
            'latitude': float(row.latitude) if row and row.latitude is not None else None,
            'longitude': float(row.longitude) if row and row.longitude is not None else None,
            'matched_label': row.matched_label if row else '',
            'error': row.error if row else '',
        })
    items.sort(key=lambda item: (-item['count'], item['name'].casefold()))
    country = company_country(company)
    connection = google_maps_connection()
    google_ready = bool(connection and connection.is_enabled)
    browser_key = str((connection.configuration or {}).get('browser_api_key') or '').strip() if google_ready else ''
    return {
        'country': {
            'name': country.name, 'iso2': country.iso2,
            'latitude': float(country.latitude) if country.latitude is not None else None,
            'longitude': float(country.longitude) if country.longitude is not None else None,
        },
        'browser_api_key': browser_key,
        'map_error': '' if browser_key else 'Configure and enable Google Maps with a browser API key in Integrations to show the map.',
        'total_opportunities': total,
        'without_location': without_location,
        'areas': items,
        'google': {
            'available': google_ready,
            'waiting': sum(1 for item in items if item['status'] in (AreaLocation.STATUS_PENDING, AreaLocation.STATUS_ERROR)),
            'batch': GOOGLE_BATCH,
            'usage': usage_snapshot(connection) if google_ready else None,
        },
    }


def _directory_index(country):
    """normalized label -> {level: {records}} for the country's places that have coordinates."""
    index = defaultdict(lambda: defaultdict(dict))
    levels = (
        (0, Locality.objects.filter(country=country, is_active=True)),
        (1, City.objects.filter(country=country, is_active=True)),
        (2, AdministrativeArea.objects.filter(country=country, is_active=True, latitude__isnull=False)),
    )
    for level, queryset in levels:
        for record in queryset.only('pk', 'name', 'normalized_name', 'alternate_names', 'latitude', 'longitude', 'country'):
            for label in {record.name, record.normalized_name, *(record.alternate_names or [])}:
                key = normalize_name(label)
                if key:
                    index[key][level][record.pk] = record
    return index


def _directory_match(index, key):
    """The single place at the most specific level carrying this name; None when the name is
    unknown or that level has several different places with it (Google decides those)."""
    for level in sorted(index.get(key, {})):
        records = list(index[key][level].values())
        if len(records) == 1:
            return records[0]
        return None
    return None


def _apply_google_result(row, place, country):
    now = timezone.now()
    location = (place or {}).get('location') or {}
    found_country = place_country_code(place) if place else ''
    if not place or location.get('latitude') is None or location.get('longitude') is None:
        row.status, row.error = AreaLocation.STATUS_NOT_FOUND, 'Google Maps found no place with this name.'
    elif found_country != country.iso2:
        row.status = AreaLocation.STATUS_NOT_FOUND
        row.error = f'Google Maps matched "{place.get("formattedAddress", "")}", which is outside {country.name}.'
    else:
        row.status, row.source, row.error = AreaLocation.STATUS_PLACED, AreaLocation.SOURCE_GOOGLE, ''
        row.latitude, row.longitude = round(location['latitude'], 7), round(location['longitude'], 7)
        row.matched_label = place.get('formattedAddress') or (place.get('displayName') or {}).get('text', '')
    row.resolved_at = now
    row.save()
