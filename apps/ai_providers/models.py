from django.db import models


class AIProviderConfig(models.Model):
    PROVIDER_VOYAGE      = 'voyage'
    PROVIDER_OPENAI      = 'openai'
    PROVIDER_ANTHROPIC   = 'anthropic'
    PROVIDER_GOOGLE      = 'google'
    PROVIDER_DEEPSEEK    = 'deepseek'
    PROVIDER_QWEN        = 'qwen'
    PROVIDER_KIMI        = 'kimi'
    PROVIDER_GROQ        = 'groq'
    PROVIDER_MISTRAL     = 'mistral'
    PROVIDER_GROK        = 'grok'
    PROVIDER_PERPLEXITY  = 'perplexity'
    PROVIDER_TOGETHER    = 'together'
    PROVIDER_COHERE      = 'cohere'
    PROVIDER_JINA        = 'jina'

    PROVIDER_CHOICES = [
        (PROVIDER_VOYAGE,     'Voyage AI'),
        (PROVIDER_OPENAI,     'OpenAI'),
        (PROVIDER_ANTHROPIC,  'Anthropic'),
        (PROVIDER_GOOGLE,     'Google Gemini'),
        (PROVIDER_DEEPSEEK,   'DeepSeek'),
        (PROVIDER_QWEN,       'Qwen (Alibaba)'),
        (PROVIDER_KIMI,       'Kimi (Moonshot)'),
        (PROVIDER_GROQ,       'Groq'),
        (PROVIDER_MISTRAL,    'Mistral AI'),
        (PROVIDER_GROK,       'Grok (xAI)'),
        (PROVIDER_PERPLEXITY, 'Perplexity'),
        (PROVIDER_TOGETHER,   'Together AI'),
        (PROVIDER_COHERE,     'Cohere'),
        (PROVIDER_JINA,       'Jina AI'),
    ]

    CAPABILITY_EMBEDDING = 'embedding'
    CAPABILITY_CHAT      = 'chat'
    CAPABILITY_AGENT     = 'agent'

    CAPABILITY_CHOICES = [
        (CAPABILITY_EMBEDDING, 'Embeddings'),
        (CAPABILITY_CHAT,      'Chat / Completion'),
        (CAPABILITY_AGENT,     'General AI Agent'),
    ]

    display_name = models.CharField(max_length=100)
    provider = models.CharField(max_length=50, choices=PROVIDER_CHOICES)
    capability = models.CharField(max_length=50, choices=CAPABILITY_CHOICES)
    # Stored plaintext for now. Swap TextField for an encrypted field (e.g. django-encrypted-fields)
    # when encryption is needed — the manager reads this transparently.
    api_key = models.TextField()
    model = models.CharField(max_length=100)
    base_url = models.URLField(blank=True, default='')
    extra_config = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['capability', '-is_active', 'display_name']

    def __str__(self):
        active = ' [active]' if self.is_active else ''
        return f'{self.display_name} ({self.get_capability_display()}){active}'

    def masked_key(self):
        key = self.api_key or ''
        if len(key) <= 8:
            return '••••••••'
        return f'{key[:4]}••••{key[-4:]}'
