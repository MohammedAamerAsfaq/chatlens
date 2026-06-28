import requests
from .base import EmbeddingProvider, friendly_error

DEFAULT_BASE_URL = 'https://api.voyageai.com/v1'


class VoyageEmbeddingProvider(EmbeddingProvider):
    def __init__(self, api_key: str, model: str = 'voyage-3-lite', base_url: str = ''):
        self.model = model
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
        })
        self.base_url = (base_url or DEFAULT_BASE_URL).rstrip('/')

    def embed(self, text: str) -> list:
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: list) -> list:
        resp = self.session.post(
            f'{self.base_url}/embeddings',
            json={'input': texts, 'model': self.model},
            timeout=30,
        )
        resp.raise_for_status()
        return [item['embedding'] for item in resp.json()['data']]

    def test_connection(self) -> dict:
        try:
            vec = self.embed('connection test')
            return {'ok': True, 'dimensions': len(vec), 'model': self.model}
        except Exception as e:
            return {'ok': False, 'error': friendly_error(e)}
