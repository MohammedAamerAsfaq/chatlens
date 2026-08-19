import logging
from . import rate_limiter
from .models import AIProviderConfig
from .providers.voyage import VoyageEmbeddingProvider
from .providers.openai_provider import OpenAIEmbeddingProvider, OpenAIChatProvider
from .providers.anthropic_provider import AnthropicChatProvider
from .providers.openai_compatible import (
    DeepSeekChatProvider,
    GoogleChatProvider, GoogleEmbeddingProvider,
    QwenChatProvider,
    KimiChatProvider,
    GlmChatProvider,
    GroqChatProvider,
    MistralChatProvider, MistralEmbeddingProvider,
    GrokChatProvider,
    PerplexityChatProvider,
    TogetherChatProvider, TogetherEmbeddingProvider,
    CohereChatProvider, CohereEmbeddingProvider,
    JinaEmbeddingProvider,
    LMStudioChatProvider, LMStudioEmbeddingProvider,
    OtherOpenAICompatibleChatProvider, OtherOpenAICompatibleEmbeddingProvider,
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
    'lm_studio': LMStudioEmbeddingProvider,
    'other':     OtherOpenAICompatibleEmbeddingProvider,
}

_CHAT_REGISTRY = {
    'openai':      OpenAIChatProvider,
    'anthropic':   AnthropicChatProvider,
    'google':      GoogleChatProvider,
    'deepseek':    DeepSeekChatProvider,
    'qwen':        QwenChatProvider,
    'kimi':        KimiChatProvider,
    'glm':         GlmChatProvider,
    'groq':        GroqChatProvider,
    'mistral':     MistralChatProvider,
    'grok':        GrokChatProvider,
    'perplexity':  PerplexityChatProvider,
    'together':    TogetherChatProvider,
    'cohere':      CohereChatProvider,
    'lm_studio':   LMStudioChatProvider,
    'other':       OtherOpenAICompatibleChatProvider,
}

# Agent uses the same ChatProvider interface — registered separately so
# a different model/provider can be assigned for background AI tasks.
_AGENT_REGISTRY = _CHAT_REGISTRY


def build_provider(config: AIProviderConfig):
    """Instantiate the concrete provider class for a given config row."""
    if config.capability == AIProviderConfig.CAPABILITY_EMBEDDING:
        cls = _EMBEDDING_REGISTRY.get(config.provider)
    elif config.capability == AIProviderConfig.CAPABILITY_AGENT:
        cls = _AGENT_REGISTRY.get(config.provider)
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

    def _active_config(self, capability: str) -> AIProviderConfig:
        try:
            return AIProviderConfig.objects.get(capability=capability, is_active=True)
        except AIProviderConfig.DoesNotExist:
            raise RuntimeError(
                f'No active {capability} provider configured. '
                'Add one in AI Providers settings.'
            )

    def _active(self, capability: str):
        return build_provider(self._active_config(capability))

    def _throttle(self, config: AIProviderConfig, tokens_needed: int):
        """Blocks until this config's own configured rate limit (AI Providers screen →
        extra_config.rate_limit_rpm/rate_limit_tpm) allows another request. A no-op for
        any config that hasn't had a limit set — existing/default behavior unchanged.
        Keyed by config id, not provider name, so every caller sharing the same active
        config (live message embeds, product embeds, alias embeds) draws from one real
        shared quota instead of racing independently for the same provider-side limit."""
        extra = config.extra_config or {}
        rate_limiter.acquire(
            config_id=config.id,
            rpm=extra.get('rate_limit_rpm'),
            tpm=extra.get('rate_limit_tpm'),
            tokens_needed=tokens_needed,
        )

    # ── Embedding ──────────────────────────────────────────────────────────────

    def embed(self, text: str) -> list:
        config = self._active_config(AIProviderConfig.CAPABILITY_EMBEDDING)
        self._throttle(config, rate_limiter.estimate_tokens(text))
        return build_provider(config).embed(text)

    def embed_batch(self, texts: list) -> list:
        config = self._active_config(AIProviderConfig.CAPABILITY_EMBEDDING)
        self._throttle(config, sum(rate_limiter.estimate_tokens(t) for t in texts))
        return build_provider(config).embed_batch(texts)

    # ── Chat ───────────────────────────────────────────────────────────────────

    def chat(self, messages: list, **kwargs) -> str:
        config = self._active_config(AIProviderConfig.CAPABILITY_CHAT)
        self._throttle(config, sum(rate_limiter.estimate_tokens(m.get('content', '')) for m in messages))
        return build_provider(config).chat(messages, **kwargs)

    # ── Agent ──────────────────────────────────────────────────────────────────
    # Same interface as chat but routed to the active agent provider — typically
    # a faster/cheaper model assigned for background tasks (enrichment, tagging,
    # summarisation) independently of the user-facing chat model.

    def agent(self, messages: list, config=None, **kwargs) -> str:
        config = config or self._active_config(AIProviderConfig.CAPABILITY_AGENT)
        self._throttle(config, sum(rate_limiter.estimate_tokens(m.get('content', '')) for m in messages))
        return build_provider(config).chat(messages, **kwargs)

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
