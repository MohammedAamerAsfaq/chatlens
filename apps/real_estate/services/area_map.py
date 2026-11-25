"""Area map report: how many inquiries are in each area, and where each area is.

Each inquiry property's area comes from the Real Estate Location AI step
(services/location_service.py), saved on the item with a link to the area's AreaLocation
(its map position). This module counts inquiries per area and places areas on the map:
the geography directory first (free), then Google Maps text search for "area, city,
country", inside the Google Maps monthly request cap, only in the company's country.
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
TOP_SUB_AREAS = 8
TOP_ERRORS = 3
WAITING = (AreaLocation.STATUS_PENDING, AreaLocation.STATUS_ERROR)


def company_country(company):
    settings_row, _ = RealEstateSettings.objects.get_or_create(company=company)
    country = Country.objects.filter(normalized_name=normalize_name(settings_row.default_country)).first()
    if not country:
        raise ValueError(
            f'The Real Estate default country "{settings_row.default_country}" is not in the '
            'geography directory, so areas cannot be placed on the map.'
        )
    return country


def area_map_report(company, opportunities):
    from apps.real_estate.services.location_service import TASK_KEY
    from apps.task_management.models import BackgroundTask

    per_opportunity = defaultdict(set)
    errors = Counter()
    areas = defaultdict(lambda: {'opportunities': set(), 'by_activity': Counter(), 'sub_areas': defaultdict(set)})
    rows = OpportunityItem.objects.filter(opportunity__in=opportunities).values_list(
        'opportunity_id', 'opportunity__activity_type', 'geo_status', 'geo_area_location_id', 'geo_sub_area',
        'geo_error',
    )
    for opportunity_id, activity, geo_status, area_id, sub_area, geo_error in rows.iterator():
        per_opportunity[opportunity_id].add(geo_status)
        if geo_status == OpportunityItem.GEO_ERROR:
            errors[(geo_error or 'No reason recorded.')[:500]] += 1
        if geo_status != OpportunityItem.GEO_LOCATED or not area_id:
            continue
        area = areas[area_id]
        if opportunity_id not in area['opportunities']:
            area['opportunities'].add(opportunity_id)
            area['by_activity'][activity] += 1
        if sub_area:
            area['sub_areas'][sub_area].add(opportunity_id)

    totals = Counter(_opportunity_status(statuses) for statuses in per_opportunity.values())
    total = opportunities.count()
    places = AreaLocation.objects.in_bulk(list(areas))
    items = []
    for area_id, area in areas.items():
        place = places[area_id]
        sub_areas = sorted(area['sub_areas'].items(), key=lambda pair: (-len(pair[1]), pair[0].casefold()))
        items.append({
            'id': area_id,
            'name': place.name,
            'city': place.city,
            'count': len(area['opportunities']),
            'by_activity': dict(area['by_activity']),
            'sub_areas': [{'name': name, 'count': len(ids)} for name, ids in sub_areas[:TOP_SUB_AREAS]],
            'status': place.status,
            'source': place.source,
            'latitude': float(place.latitude) if place.latitude is not None else None,
            'longitude': float(place.longitude) if place.longitude is not None else None,
            'matched_label': place.matched_label,
            'error': place.error,
        })
    items.sort(key=lambda item: (-item['count'], item['name'].casefold()))

    country = company_country(company)
    settings_row, _ = RealEstateSettings.objects.get_or_create(company=company)
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
        'totals': {
            'opportunities': total,
            'no_properties': total - len(per_opportunity),
            'located': totals[OpportunityItem.GEO_LOCATED],
            'unknown': totals[OpportunityItem.GEO_UNKNOWN],
            'pending': totals[OpportunityItem.GEO_PENDING],
            'error': totals[OpportunityItem.GEO_ERROR],
        },
        # Why the location step failed, most common first (counted per property).
        'error_reasons': [{'error': text, 'count': count} for text, count in errors.most_common(TOP_ERRORS)],
        'locating': BackgroundTask.objects.filter(
            company=company, task_key=TASK_KEY, status__in=BackgroundTask.ACTIVE_STATUSES,
        ).count(),
        'location_search_mode': settings_row.location_search_mode,
        'areas': items,
        'google': {
            'available': google_ready,
            'waiting': sum(1 for item in items if item['status'] in WAITING),
            'batch': GOOGLE_BATCH,
            'usage': usage_snapshot(connection) if google_ready else None,
        },
    }


def location_status(company, opportunities):
    """For the location backfill in settings: how many inquiries still have no area (not
    located yet, or the AI step failed), how many are being located now, and why it failed."""
    from apps.real_estate.services.location_service import TASK_KEY
    from apps.task_management.models import BackgroundTask

    items = OpportunityItem.objects.filter(opportunity__in=opportunities)
    # Same precedence as the area map totals: located > error > pending > unknown.
    located = items.filter(geo_status=OpportunityItem.GEO_LOCATED).values('opportunity_id')
    failed = items.filter(geo_status=OpportunityItem.GEO_ERROR).values('opportunity_id')
    pending = items.filter(geo_status=OpportunityItem.GEO_PENDING).values('opportunity_id')
    with_items = opportunities.filter(pk__in=items.values('opportunity_id'))
    errors = Counter(
        (text or 'No reason recorded.')[:500]
        for text in items.filter(geo_status=OpportunityItem.GEO_ERROR).values_list('geo_error', flat=True).iterator()
    )
    settings_row, _ = RealEstateSettings.objects.get_or_create(company=company)
    return {
        'opportunities': opportunities.count(),
        'with_properties': with_items.count(),
        'error': with_items.filter(pk__in=failed).exclude(pk__in=located).count(),
        'pending': with_items.filter(pk__in=pending).exclude(pk__in=located).exclude(pk__in=failed).count(),
        'error_reasons': [{'error': text, 'count': count} for text, count in errors.most_common(TOP_ERRORS)],
        'locating': BackgroundTask.objects.filter(
            company=company, task_key=TASK_KEY, status__in=BackgroundTask.ACTIVE_STATUSES,
        ).count(),
        'location_search_mode': settings_row.location_search_mode,
    }


def place_waiting_areas(company, opportunities):
    """Place the areas still waiting (most inquiries first, up to GOOGLE_BATCH). Returns a
    notice for the user, or '' when everything went through."""
    from apps.real_estate.services.location_service import place_area

    connection = google_maps_connection()
    if not connection or not connection.is_enabled:
        raise ValueError('Google Maps is not configured or not enabled in Integrations.')
    counts = Counter(
        OpportunityItem.objects.filter(
            opportunity__in=opportunities, geo_status=OpportunityItem.GEO_LOCATED,
            geo_area_location__status__in=WAITING,
        ).values_list('geo_area_location_id', flat=True)
    )
    rows = AreaLocation.objects.in_bulk(list(counts))
    for area_id, _count in counts.most_common(GOOGLE_BATCH):
        notice = place_area(rows[area_id])
        if notice:
            return notice
    return ''


def google_place(row, country):
    """Look the area up on Google Maps and save the result on the (locked) row."""
    connection = google_maps_connection()
    if not connection or not connection.is_enabled:
        return 'Google Maps is not configured or not enabled in Integrations.'
    try:
        reserve_request(connection, 'area_map_search')
    except GoogleMapsQuotaError as exc:
        return f'{exc} The remaining areas stay off the map until next month or until the cap is raised.'
    query = ', '.join(part for part in (row.name, row.city, country.name) if part)
    try:
        place = client_for(connection).search_text(query, region_code=country.iso2)
    except GoogleMapsError as exc:
        row.status, row.error = AreaLocation.STATUS_ERROR, str(exc)
        row.save(update_fields=['status', 'error', 'updated_at'])
        return f'Google Maps lookup failed: {exc}'
    location = (place or {}).get('location') or {}
    if not place or location.get('latitude') is None or location.get('longitude') is None:
        row.status, row.error = AreaLocation.STATUS_NOT_FOUND, f'Google Maps found no place for "{query}".'
    elif place_country_code(place) != country.iso2:
        row.status = AreaLocation.STATUS_NOT_FOUND
        row.error = f'Google Maps matched "{place.get("formattedAddress", "")}", which is outside {country.name}.'
    else:
        row.status, row.source, row.error = AreaLocation.STATUS_PLACED, AreaLocation.SOURCE_GOOGLE, ''
        row.latitude, row.longitude = round(location['latitude'], 7), round(location['longitude'], 7)
        row.matched_label = place.get('formattedAddress') or (place.get('displayName') or {}).get('text', '')
    row.resolved_at = timezone.now()
    row.save()
    return ''


def directory_index(country):
    """normalized label -> {level: {pk: (record, {normalized city/emirate names})}} for the
    country's places with coordinates. Level 0 = locality, 1 = city, 2 = emirate/region."""
    index = defaultdict(lambda: defaultdict(dict))
    levels = (
        (0, Locality.objects.filter(country=country, is_active=True).select_related('city', 'administrative_area')),
        (1, City.objects.filter(country=country, is_active=True).select_related('administrative_area')),
        (2, AdministrativeArea.objects.filter(country=country, is_active=True, latitude__isnull=False)),
    )
    for level, queryset in levels:
        for record in queryset:
            parents = {
                normalize_name(getattr(getattr(record, attr, None), 'name', ''))
                for attr in ('city', 'administrative_area')
            } | ({normalize_name(record.name)} if level else set())
            for label in {record.name, record.normalized_name, *(record.alternate_names or [])}:
                key = normalize_name(label)
                if key:
                    index[key][level][record.pk] = (record, parents - {''})
    return index


def directory_match(index, area_key, city_key=''):
    """The single place at the most specific level carrying this name, narrowed to the city
    when several share it; None when unknown or still ambiguous (Google decides those)."""
    for level in sorted(index.get(area_key, {})):
        candidates = list(index[area_key][level].values())
        if len(candidates) > 1 and city_key:
            candidates = [pair for pair in candidates if city_key in pair[1]]
        return candidates[0][0] if len(candidates) == 1 else None
    return None


def _opportunity_status(statuses):
    for status in (OpportunityItem.GEO_LOCATED, OpportunityItem.GEO_ERROR, OpportunityItem.GEO_PENDING):
        if status in statuses:
            return status
    return OpportunityItem.GEO_UNKNOWN
