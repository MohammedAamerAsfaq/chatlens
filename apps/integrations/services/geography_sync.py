import re
import unicodedata
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone

from apps.integrations.connectors import GeoNamesClient
from apps.integrations.models import AdministrativeArea, City, Country


def normalize_name(value):
    value = unicodedata.normalize('NFKD', str(value or '')).casefold()
    return re.sub(r'[^a-z0-9]+', ' ', value).strip()


def decimal_or_none(value):
    try:
        return Decimal(str(value)) if value not in (None, '') else None
    except (InvalidOperation, TypeError, ValueError):
        return None


def alternate_names(row):
    values = row.get('alternateNames') or []
    if isinstance(values, str):
        values = values.split(',')
    names = []
    for value in values:
        name = value.get('name') if isinstance(value, dict) else value
        if name and name not in names:
            names.append(name)
    return names[:250]


def _country_coordinates(row):
    north, south = decimal_or_none(row.get('north')), decimal_or_none(row.get('south'))
    east, west = decimal_or_none(row.get('east')), decimal_or_none(row.get('west'))
    latitude = (north + south) / 2 if north is not None and south is not None else None
    longitude = (east + west) / 2 if east is not None and west is not None else None
    return latitude, longitude


def sync_country(connection, country_code='AE'):
    username = connection.configuration.get('username', '')
    client = GeoNamesClient(username)
    country_row = client.country(country_code)
    area_rows = client.administrative_areas(country_code)
    city_rows = client.cities(country_code)
    now = timezone.now()
    latitude, longitude = _country_coordinates(country_row)

    with transaction.atomic():
        country, country_created = Country.objects.update_or_create(
            iso2=country_code.upper(), defaults={
                'iso3': country_row.get('isoAlpha3', ''),
                'name': country_row.get('countryName') or country_row.get('name'),
                'normalized_name': normalize_name(country_row.get('countryName') or country_row.get('name')),
                'geoname_id': int(country_row['geonameId']),
                'latitude': latitude, 'longitude': longitude,
                'alternate_names': alternate_names(country_row),
                'source_payload': country_row, 'is_active': True,
                'source_updated_at': now,
            },
        )
        area_ids = set()
        areas_by_code = {}
        created_areas = 0
        for row in area_rows:
            geoname_id = int(row['geonameId'])
            code = row.get('adminCode1') or ''
            area, created = AdministrativeArea.objects.update_or_create(
                geoname_id=geoname_id, defaults={
                    'country': country, 'level': 1, 'code': code,
                    'name': row['name'], 'normalized_name': normalize_name(row['name']),
                    'latitude': decimal_or_none(row.get('lat')),
                    'longitude': decimal_or_none(row.get('lng')),
                    'alternate_names': alternate_names(row), 'source_payload': row,
                    'is_active': True, 'source_updated_at': now,
                },
            )
            area_ids.add(area.pk)
            areas_by_code[code] = area
            created_areas += int(created)
        AdministrativeArea.objects.filter(country=country, level=1).exclude(pk__in=area_ids).update(is_active=False)

        city_ids = set()
        created_cities = 0
        skipped_cities = 0
        for row in city_rows:
            city_latitude = decimal_or_none(row.get('lat'))
            city_longitude = decimal_or_none(row.get('lng'))
            if city_latitude is None or city_longitude is None:
                skipped_cities += 1
                continue
            timezone_data = row.get('timezone') or {}
            city, created = City.objects.update_or_create(
                geoname_id=int(row['geonameId']), defaults={
                    'country': country,
                    'administrative_area': areas_by_code.get(row.get('adminCode1') or ''),
                    'name': row['name'], 'normalized_name': normalize_name(row['name']),
                    'feature_code': row.get('fcode') or row.get('featureCode') or '',
                    'latitude': city_latitude, 'longitude': city_longitude,
                    'population': max(0, int(row.get('population') or 0)),
                    'timezone': timezone_data.get('timeZoneId', '') if isinstance(timezone_data, dict) else '',
                    'alternate_names': alternate_names(row), 'source_payload': row,
                    'is_active': True, 'source_updated_at': now,
                },
            )
            city_ids.add(city.pk)
            created_cities += int(created)
        City.objects.filter(country=country).exclude(pk__in=city_ids).update(is_active=False)

    return {
        'country_code': country.iso2, 'country_created': country_created,
        'administrative_areas_total': len(area_rows),
        'administrative_areas_created': created_areas,
        'cities_total': len(city_ids), 'cities_created': created_cities,
        'cities_skipped': skipped_cities,
    }
