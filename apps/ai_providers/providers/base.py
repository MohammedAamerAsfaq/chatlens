from abc import ABC, abstractmethod


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
