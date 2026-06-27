"""
Thin provider subclasses for every service that exposes an OpenAI-compatible API.
Each class only overrides the default base_url and default model — all HTTP logic
lives in the parent OpenAIChatProvider / OpenAIEmbeddingProvider.
"""
from .openai_provider import OpenAIChatProvider, OpenAIEmbeddingProvider


# ── Chat providers ─────────────────────────────────────────────────────────────

class DeepSeekChatProvider(OpenAIChatProvider):
    def __init__(self, api_key, model='deepseek-chat', base_url=''):
        super().__init__(api_key, model, base_url or 'https://api.deepseek.com/v1')


class GoogleChatProvider(OpenAIChatProvider):
    def __init__(self, api_key, model='gemini-2.0-flash', base_url=''):
        super().__init__(api_key, model, base_url or 'https://generativelanguage.googleapis.com/v1beta/openai')


class QwenChatProvider(OpenAIChatProvider):
    def __init__(self, api_key, model='qwen-max', base_url=''):
        super().__init__(api_key, model, base_url or 'https://dashscope.aliyuncs.com/compatible-mode/v1')


class KimiChatProvider(OpenAIChatProvider):
    def __init__(self, api_key, model='moonshot-v1-128k', base_url=''):
        super().__init__(api_key, model, base_url or 'https://api.moonshot.cn/v1')


class GroqChatProvider(OpenAIChatProvider):
    def __init__(self, api_key, model='llama-3.3-70b-versatile', base_url=''):
        super().__init__(api_key, model, base_url or 'https://api.groq.com/openai/v1')


class MistralChatProvider(OpenAIChatProvider):
    def __init__(self, api_key, model='mistral-large-latest', base_url=''):
        super().__init__(api_key, model, base_url or 'https://api.mistral.ai/v1')


class GrokChatProvider(OpenAIChatProvider):
    def __init__(self, api_key, model='grok-3-mini', base_url=''):
        super().__init__(api_key, model, base_url or 'https://api.x.ai/v1')


class PerplexityChatProvider(OpenAIChatProvider):
    def __init__(self, api_key, model='sonar-pro', base_url=''):
        super().__init__(api_key, model, base_url or 'https://api.perplexity.ai')


class TogetherChatProvider(OpenAIChatProvider):
    def __init__(self, api_key, model='meta-llama/Llama-3.3-70B-Instruct-Turbo', base_url=''):
        super().__init__(api_key, model, base_url or 'https://api.together.xyz/v1')


class CohereChatProvider(OpenAIChatProvider):
    def __init__(self, api_key, model='command-r-plus-08-2024', base_url=''):
        super().__init__(api_key, model, base_url or 'https://api.cohere.com/compatibility/v1')


# ── Embedding providers ────────────────────────────────────────────────────────

class GoogleEmbeddingProvider(OpenAIEmbeddingProvider):
    def __init__(self, api_key, model='text-embedding-004', base_url=''):
        super().__init__(api_key, model, base_url or 'https://generativelanguage.googleapis.com/v1beta/openai')


class MistralEmbeddingProvider(OpenAIEmbeddingProvider):
    def __init__(self, api_key, model='mistral-embed', base_url=''):
        super().__init__(api_key, model, base_url or 'https://api.mistral.ai/v1')


class CohereEmbeddingProvider(OpenAIEmbeddingProvider):
    def __init__(self, api_key, model='embed-v4', base_url=''):
        super().__init__(api_key, model, base_url or 'https://api.cohere.com/compatibility/v1')


class JinaEmbeddingProvider(OpenAIEmbeddingProvider):
    def __init__(self, api_key, model='jina-embeddings-v3', base_url=''):
        super().__init__(api_key, model, base_url or 'https://api.jina.ai/v1')


class TogetherEmbeddingProvider(OpenAIEmbeddingProvider):
    def __init__(self, api_key, model='togethercomputer/m2-bert-80M-8k-retrieval', base_url=''):
        super().__init__(api_key, model, base_url or 'https://api.together.xyz/v1')
