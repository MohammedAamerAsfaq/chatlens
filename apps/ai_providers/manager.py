import logging
from .models import AIProviderConfig
from .providers.voyage import VoyageEmbeddingProvider
from .providers.openai_provider import OpenAIEmbeddingProvider, OpenAIChatProvider
from .providers.anthropic_provider import AnthropicChatProvider
from .providers.openai_compatible import (
    DeepSeekChatProvider,
    GoogleChatProvider, GoogleEmbeddingProvider,
    QwenChatProvider,
    KimiChatProvider,
    GroqChatProvider,
    MistralChatProvider, MistralEmbeddingProvider,
    GrokChatProvider,
    PerplexityChatProvider,
    TogetherChatProvider, TogetherEmbeddingProvider,
    CohereChatProvider, CohereEmbeddingProvider,
    JinaEmbeddingProvider,
)

logger = logging.getLogger(__name__)

_EMBEDDING_REGISTRY = {
    'voyage':    VoyageEmbeddingProvider,
    'openai':    OpenAIEmbeddingProvider,
    'google':    GoogleEmbeddingProvider,
    'mistral':   MistralEmbeddingProvider,
    'cohere':    CohereEmbeddingProvider,
    'jina':      JinaEmbeddingProvider,
    'together':  TogetherEmbeddingProvider,
}

_CHAT_REGISTRY = {
    'openai':      OpenAIChatProvider,
    'anthropic':   AnthropicChatProvider,
    'google':      GoogleChatProvider,
    'deepseek':    DeepSeekChatProvider,
    'qwen':        QwenChatProvider,
    'kimi':        KimiChatProvider,
    'groq':        GroqChatProvider,
    'mistral':     MistralChatProvider,
    'grok':        GrokChatProvider,
    'perplexity':  PerplexityChatProvider,
    'together':    TogetherChatProvider,
    'cohere':      CohereChatProvider,
}


def build_provider(config: AIProviderConfig):
    """Instantiate the concrete provider class for a given config row."""
    if config.capability == AIProviderConfig.CAPABILITY_EMBEDDING:
        cls = _EMBEDDING_REGISTRY.get(config.provider)
    else:
        cls = _CHAT_REGISTRY.get(config.provider)

    if cls is None:
        raise ValueError(
            f'No implementation registered for provider={config.provider!r} '
            f'capability={config.capability!r}'
        )

    return cls(
        api_key=config.api_key,
        model=config.model,
        base_url=config.base_url or '',
    )


class AIManager:
    """
    Thin routing layer.  Callers never import a specific provider class;
    they call ai_manager.embed() / ai_manager.chat() and the active
    provider for that capability is resolved from the DB at call time.

    To switch providers: set a different AIProviderConfig row to is_active=True
    (and deactivate the previous one) — no code changes required.
    """

    def _active(self, capability: str):
        try:
            config = AIProviderConfig.objects.get(capability=capability, is_active=True)
        except AIProviderConfig.DoesNotExist:
            raise RuntimeError(
                f'No active {capability} provider configured. '
                'Add one in AI Providers settings.'
            )
        return build_provider(config)

    # ── Embedding ──────────────────────────────────────────────────────────────

    def embed(self, text: str) -> list:
        return self._active(AIProviderConfig.CAPABILITY_EMBEDDING).embed(text)

    def embed_batch(self, texts: list) -> list:
        return self._active(AIProviderConfig.CAPABILITY_EMBEDDING).embed_batch(texts)

    # ── Chat ───────────────────────────────────────────────────────────────────

    def chat(self, messages: list, **kwargs) -> str:
        return self._active(AIProviderConfig.CAPABILITY_CHAT).chat(messages, **kwargs)

    # ── Utility ────────────────────────────────────────────────────────────────

    def test(self, config_id: int) -> dict:
        config = AIProviderConfig.objects.get(pk=config_id)
        return build_provider(config).test_connection()

    def active_config(self, capability: str):
        """Return the active AIProviderConfig for a capability, or None."""
        return AIProviderConfig.objects.filter(
            capability=capability, is_active=True
        ).first()


ai_manager = AIManager()
