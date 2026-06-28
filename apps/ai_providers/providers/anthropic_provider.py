import requests
from .base import ChatProvider, friendly_error

DEFAULT_BASE_URL = 'https://api.anthropic.com/v1'
ANTHROPIC_VERSION = '2023-06-01'


class AnthropicChatProvider(ChatProvider):
    def __init__(self, api_key: str, model: str = 'claude-sonnet-4-6', base_url: str = ''):
        self.model = model
        self.session = requests.Session()
        self.session.headers.update({
            'x-api-key': api_key,
            'anthropic-version': ANTHROPIC_VERSION,
            'Content-Type': 'application/json',
        })
        self.base_url = (base_url or DEFAULT_BASE_URL).rstrip('/')

    def chat(self, messages: list, **kwargs) -> str:
        # Anthropic separates system from conversation messages
        system = None
        conv = []
        for msg in messages:
            if msg.get('role') == 'system':
                system = msg['content']
            else:
                conv.append(msg)

        body = {
            'model': self.model,
            'messages': conv,
            'max_tokens': kwargs.pop('max_tokens', 1024),
            **kwargs,
        }
        if system:
            body['system'] = system

        resp = self.session.post(
            f'{self.base_url}/messages',
            json=body,
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()['content'][0]['text']

    def test_connection(self) -> dict:
        try:
            result = self.chat(
                [{'role': 'user', 'content': 'Reply with the single word: ok'}],
                max_tokens=5,
            )
            return {'ok': True, 'response': result, 'model': self.model}
        except Exception as e:
            return {'ok': False, 'error': friendly_error(e)}

    def list_models(self) -> list:
        try:
            resp = self.session.get(f'{self.base_url}/models', timeout=10)
            resp.raise_for_status()
            return [m['id'] for m in resp.json().get('data', [])]
        except Exception:
            return []
