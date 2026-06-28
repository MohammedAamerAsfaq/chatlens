from abc import ABC, abstractmethod
import requests


def friendly_error(exc: Exception) -> str:
    """Return a concise error string from an exception.

    For HTTP errors, tries to extract the provider's own error message from
    the response body instead of showing the raw URL + status line.
    """
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        status = exc.response.status_code
        try:
            body = exc.response.json()
            # Most providers nest the message under error.message or error
            msg = (
                body.get('error', {}).get('message')
                or body.get('error')
                or body.get('message')
                or body.get('detail')
            )
            if msg and isinstance(msg, str):
                return f'{status}: {msg}'
        except Exception:
            pass
        return f'HTTP {status}: {exc.response.reason}'
    return str(exc)


class EmbeddingProvider(ABC):
    @abstractmethod
    def embed(self, text: str) -> list:
        pass

    @abstractmethod
    def embed_batch(self, texts: list) -> list:
        pass

    @abstractmethod
    def test_connection(self) -> dict:
        pass

    def list_models(self) -> list:
        """Return available model IDs from the provider API. Empty list = not supported."""
        return []


class ChatProvider(ABC):
    @abstractmethod
    def chat(self, messages: list, **kwargs) -> str:
        pass

    @abstractmethod
    def test_connection(self) -> dict:
        pass

    def list_models(self) -> list:
        """Return available model IDs from the provider API. Empty list = not supported."""
        return []
