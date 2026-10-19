from urllib.parse import quote

import requests


class GoogleMapsError(RuntimeError):
    pass


class GoogleMapsClient:
    BASE_URL = 'https://places.googleapis.com/v1'

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
        error = payload.get('error') or {}
        return str(error.get('message') or '')
