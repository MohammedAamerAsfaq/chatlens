import requests
from .base import EmbeddingProvider, ChatProvider

EMBEDDING_BASE_URL = 'https://api.openai.com/v1'
CHAT_BASE_URL = 'https://api.openai.com/v1'


def _openai_session(api_key: str) -> requests.Session:
    s = requests.Session()
    s.headers.update({
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
    })
    return s


class OpenAIEmbeddingProvider(EmbeddingProvider):
    def __init__(self, api_key: str, model: str = 'text-embedding-3-small', base_url: str = ''):
        self.model = model
        self.session = _openai_session(api_key)
        self.base_url = (base_url or EMBEDDING_BASE_URL).rstrip('/')

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
            return {'ok': False, 'error': str(e)}

    def list_models(self) -> list:
        try:
            resp = self.session.get(f'{self.base_url}/models', timeout=10)
            resp.raise_for_status()
            return sorted(m['id'] for m in resp.json().get('data', []))
        except Exception:
            return []


class OpenAIChatProvider(ChatProvider):
    def __init__(self, api_key: str, model: str = 'gpt-4o-mini', base_url: str = ''):
        self.model = model
        self.session = _openai_session(api_key)
        self.base_url = (base_url or CHAT_BASE_URL).rstrip('/')

    def chat(self, messages: list, **kwargs) -> str:
        resp = self.session.post(
            f'{self.base_url}/chat/completions',
            json={'model': self.model, 'messages': messages, **kwargs},
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()['choices'][0]['message']['content']

    def test_connection(self) -> dict:
        try:
            result = self.chat([{'role': 'user', 'content': 'Reply with the single word: ok'}], max_tokens=5)
            return {'ok': True, 'response': result, 'model': self.model}
        except Exception as e:
            return {'ok': False, 'error': str(e)}

    def list_models(self) -> list:
        try:
            resp = self.session.get(f'{self.base_url}/models', timeout=10)
            resp.raise_for_status()
            return sorted(m['id'] for m in resp.json().get('data', []))
        except Exception:
            return []
