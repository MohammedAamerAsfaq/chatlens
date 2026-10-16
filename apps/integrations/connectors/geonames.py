import requests


class GeoNamesError(RuntimeError):
    pass


class GeoNamesClient:
    BASE_URL = 'https://secure.geonames.org'

    def __init__(self, username, *, timeout=20, session=None):
        if not str(username or '').strip():
            raise GeoNamesError('A GeoNames username is required.')
        self.username = username.strip()
        self.timeout = timeout
        self.session = session or requests.Session()

    def _get(self, endpoint, **params):
        params.update(username=self.username, type='json')
        try:
            response = self.session.get(
                f'{self.BASE_URL}/{endpoint}', params=params, timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise GeoNamesError(f'GeoNames request failed: {exc}') from exc
        if payload.get('status'):
            raise GeoNamesError(payload['status'].get('message', 'GeoNames rejected the request.'))
        return payload

    def country(self, country_code):
        rows = self._get(
            'countryInfoJSON', country=country_code.upper(), lang='en', style='FULL',
        ).get('geonames', [])
        if not rows:
            raise GeoNamesError(f'GeoNames returned no country for {country_code}.')
        return rows[0]

    def administrative_areas(self, country_code):
        return self._search_all(
            country=country_code.upper(), featureCode='ADM1', lang='en', style='FULL',
        )

    def cities(self, country_code):
        return self._search_all(
            country=country_code.upper(), featureClass='P', lang='en', style='FULL',
        )

    def _search_all(self, **params):
        rows = []
        start = 0
        while True:
            payload = self._get('searchJSON', maxRows=1000, startRow=start, **params)
            batch = payload.get('geonames', [])
            rows.extend(batch)
            start += len(batch)
            if not batch or start >= int(payload.get('totalResultsCount') or len(rows)):
                return rows
