from urllib.parse import quote

import requests


class GoogleMapsError(RuntimeError):
    pass


class GoogleMapsClient:
    BASE_URL = 'https://places.googleapis.com/v1'
    GEOCODING_URL = 'https://maps.googleapis.com/maps/api/geocode/json'

    def __init__(self, api_key, *, timeout=20, session=None):
        if not str(api_key or '').strip():
            raise GoogleMapsError('The configured Google Maps API key is unavailable.')
        self.api_key = api_key.strip()
        self.timeout = timeout
        self.session = session or requests.Session()

    def autocomplete(self, query, *, country_code='AE', session_token):
        field_mask = ','.join([
            'suggestions.placePrediction.placeId',
            'suggestions.placePrediction.text',
            'suggestions.placePrediction.structuredFormat',
            'suggestions.placePrediction.types',
        ])
        payload = {
            'input': query,
            'includedRegionCodes': [country_code.lower()],
            'languageCode': 'en',
            'sessionToken': session_token,
        }
        response = self._request(
            'post', 'places:autocomplete', field_mask=field_mask, json=payload,
        )
        predictions = []
        for suggestion in response.get('suggestions', []):
            prediction = suggestion.get('placePrediction') or {}
            if prediction.get('placeId'):
                predictions.append({
                    'place_id': prediction['placeId'],
                    'text': (prediction.get('text') or {}).get('text', ''),
                    'main_text': (
                        prediction.get('structuredFormat', {}).get('mainText', {}).get('text', '')
                    ),
                    'secondary_text': (
                        prediction.get('structuredFormat', {}).get('secondaryText', {}).get('text', '')
                    ),
                    'types': prediction.get('types') or [],
                })
        return predictions

    def place_details(self, place_id, *, session_token):
        field_mask = 'id,formattedAddress,addressComponents,location,types'
        return self._request(
            'get', f'places/{quote(place_id, safe="")}', field_mask=field_mask,
            params={'sessionToken': session_token},
        )

    def reverse_geocode(self, latitude, longitude):
        try:
            response = self.session.get(
                self.GEOCODING_URL,
                params={
                    'latlng': f'{latitude},{longitude}',
                    'key': self.api_key,
                    'language': 'en',
                },
                timeout=self.timeout,
            )
            payload = response.json()
            response.raise_for_status()
        except (requests.RequestException, ValueError) as exc:
            message = self._error_message(locals().get('payload'))
            raise GoogleMapsError(message or f'Google Maps request failed: {exc}') from exc
        if payload.get('status') not in {'OK', 'ZERO_RESULTS'}:
            raise GoogleMapsError(payload.get('error_message') or payload.get('status'))
        results = payload.get('results') or []
        return self._normalize_geocode_result(results[0]) if results else None

    def _request(self, method, endpoint, *, field_mask, **kwargs):
        headers = {
            'X-Goog-Api-Key': self.api_key,
            'X-Goog-FieldMask': field_mask,
            'Content-Type': 'application/json',
        }
        try:
            response = self.session.request(
                method, f'{self.BASE_URL}/{endpoint}', headers=headers,
                timeout=self.timeout, **kwargs,
            )
            payload = response.json()
            response.raise_for_status()
        except (requests.RequestException, ValueError) as exc:
            message = self._error_message(locals().get('payload'))
            raise GoogleMapsError(message or f'Google Maps request failed: {exc}') from exc
        return payload

    @staticmethod
    def _error_message(payload):
        if not isinstance(payload, dict):
            return ''
        if payload.get('error_message'):
            return str(payload['error_message'])
        error = payload.get('error') or {}
        return str(error.get('message') or '')

    @staticmethod
    def _normalize_geocode_result(result):
        location = (result.get('geometry') or {}).get('location') or {}
        return {
            'id': result.get('place_id') or '',
            'formattedAddress': result.get('formatted_address') or '',
            'addressComponents': [{
                'longText': component.get('long_name') or '',
                'shortText': component.get('short_name') or '',
                'types': component.get('types') or [],
            } for component in result.get('address_components') or []],
            'location': {
                'latitude': location.get('lat'),
                'longitude': location.get('lng'),
            },
            'types': result.get('types') or [],
        }
