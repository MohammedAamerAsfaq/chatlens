"""
Thin provider subclasses for every service that exposes an OpenAI-compatible API.
Each class only overrides the default base_url and default model — all HTTP logic
lives in the parent OpenAIChatProvider / OpenAIEmbeddingProvider.
"""
from .openai_provider import OpenAIChatProvider, OpenAIEmbeddingProvider


# ── Chat providers ─────────────────────────────────────────────────────────────

class DeepSeekChatProvider(OpenAIChatProvider):
    def __init__(self, api_key, model='deepseek-v4-flash', base_url=''):
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


class GlmChatProvider(OpenAIChatProvider):
    def __init__(self, api_key, model='glm-4.5-flash', base_url=''):
        super().__init__(api_key, model, base_url or 'https://open.bigmodel.cn/api/paas/v4')


class OpenRouterChatProvider(OpenAIChatProvider):
    def __init__(self, api_key, model='openrouter/auto', base_url=''):
        super().__init__(api_key, model, base_url or 'https://openrouter.ai/api/v1')

    def list_models_with_metadata(self) -> list:
        """Return model IDs with the pricing published by OpenRouter."""
        response = self.session.get(f'{self.base_url}/models', timeout=10)
        response.raise_for_status()
        rows = []
        for model in response.json().get('data', []):
            model_id = model.get('id')
            if not model_id:
                continue
            pricing = model.get('pricing') or {}
            try:
                input_cost = float(pricing['prompt']) * 1_000_000
                output_cost = float(pricing['completion']) * 1_000_000
            except (KeyError, TypeError, ValueError):
                input_cost = output_cost = None
            rows.append({
                'id': model_id,
                'input_cost_per_million': input_cost,
                'output_cost_per_million': output_cost,
            })
        return sorted(rows, key=lambda row: row['id'])

    def fetch_metadata(self) -> dict:
        """Fetch OpenRouter-published model pricing and current key usage.

        OpenRouter's key endpoint exposes spending/credit data, not reliable model
        RPM, TPM, or concurrency limits. Its documented rate-limit field is
        deprecated, so it is returned as account feedback rather than capacity.
        """
        model = next((row for row in self.list_models_with_metadata() if row['id'] == self.model), None)
        metadata = {}
        if model:
            if model['input_cost_per_million'] is not None:
                metadata['input_cost_per_million'] = model['input_cost_per_million']
            if model['output_cost_per_million'] is not None:
                metadata['output_cost_per_million'] = model['output_cost_per_million']

        account_metadata = {}
        try:
            key_response = self.session.get(f'{self.base_url}/key', timeout=10)
            key_response.raise_for_status()
            key = key_response.json().get('data') or {}
            account_metadata = {
                'limit': key.get('limit'),
                'limit_remaining': key.get('limit_remaining'),
                'limit_reset': key.get('limit_reset'),
                'usage_daily': key.get('usage_daily'),
                'usage_monthly': key.get('usage_monthly'),
                'rate_limit_requests': (key.get('rate_limit') or {}).get('requests'),
            }
        except Exception as exc:
            account_metadata = {'fetch_error': friendly_error(exc)}

        return {
            'metadata': metadata,
            'account_metadata': account_metadata,
            'detail': (
                'OpenRouter model pricing was fetched. Key credit and usage are shown below. '
                'OpenRouter does not publish usable model RPM, TPM, or concurrency values here; '
                'its key rate-limit field is deprecated and is not used for routing capacity.'
            ),
        }


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


class LMStudioChatProvider(OpenAIChatProvider):
    def __init__(self, api_key='', model='local-model', base_url=''):
        super().__init__(api_key or 'lm-studio', model, base_url or 'http://localhost:1234/v1')

    def list_models(self) -> list:
        resp = self.session.get(f'{self.base_url}/models', timeout=10)
        resp.raise_for_status()
        return sorted(m['id'] for m in resp.json().get('data', []))


class OtherOpenAICompatibleChatProvider(OpenAIChatProvider):
    def __init__(self, api_key, model='custom-model', base_url=''):
        if not base_url:
            raise ValueError('Base URL is required for Other OpenAI-compatible chat providers.')
        super().__init__(api_key, model, base_url)


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


class LMStudioEmbeddingProvider(OpenAIEmbeddingProvider):
    def __init__(self, api_key='', model='local-embedding-model', base_url=''):
        super().__init__(api_key or 'lm-studio', model, base_url or 'http://localhost:1234/v1')

    def list_models(self) -> list:
        resp = self.session.get(f'{self.base_url}/models', timeout=10)
        resp.raise_for_status()
        return sorted(m['id'] for m in resp.json().get('data', []))


class OtherOpenAICompatibleEmbeddingProvider(OpenAIEmbeddingProvider):
    def __init__(self, api_key, model='custom-embedding-model', base_url=''):
        if not base_url:
            raise ValueError('Base URL is required for Other OpenAI-compatible embedding providers.')
        super().__init__(api_key, model, base_url)
