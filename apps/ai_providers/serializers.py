from rest_framework import serializers
from .models import AIProviderConfig, KiwiRouter, KiwiRouterMember, KiwiRoutingDecision


# Default model options surfaced to the UI for each provider+capability combination.
PROVIDER_MODELS = {
    # ── Embedding ──────────────────────────────────────────────────────────────
    ('voyage',    'embedding'): ['voyage-3-lite', 'voyage-3', 'voyage-3-large', 'voyage-code-3'],
    ('openai',    'embedding'): ['text-embedding-3-small', 'text-embedding-3-large', 'text-embedding-ada-002'],
    ('google',    'embedding'): ['text-embedding-004', 'text-multilingual-embedding-002'],
    ('mistral',   'embedding'): ['mistral-embed'],
    ('cohere',    'embedding'): ['embed-v4', 'embed-english-v3.0', 'embed-multilingual-v3.0'],
    ('jina',      'embedding'): ['jina-embeddings-v3', 'jina-embeddings-v2-base-en', 'jina-embeddings-v2-base-code'],
    ('together',  'embedding'): ['togethercomputer/m2-bert-80M-8k-retrieval', 'togethercomputer/m2-bert-80M-32k-retrieval'],
    ('lm_studio', 'embedding'): ['local-embedding-model'],
    ('other',     'embedding'): ['custom-embedding-model'],

    # ── Chat ───────────────────────────────────────────────────────────────────
    ('openai',     'chat'): ['gpt-4o-mini', 'gpt-4o', 'gpt-4-turbo', 'gpt-3.5-turbo', 'o1-mini', 'o3-mini'],
    ('anthropic',  'chat'): ['claude-sonnet-4-6', 'claude-haiku-4-5-20251001', 'claude-opus-4-8'],
    ('google',     'chat'): ['gemini-2.0-flash', 'gemini-2.0-flash-lite', 'gemini-1.5-pro', 'gemini-1.5-flash'],
    ('deepseek',   'chat'): ['deepseek-v4-flash', 'deepseek-v4-pro'],
    ('qwen',       'chat'): ['qwen-max', 'qwen-plus', 'qwen-turbo', 'qwen-long', 'qwq-32b'],
    ('kimi',       'chat'): ['moonshot-v1-128k', 'moonshot-v1-32k', 'moonshot-v1-8k'],
    ('glm',        'chat'): ['glm-4.6', 'glm-4.5', 'glm-4.5-air', 'glm-4.5-flash'],
    ('openrouter', 'chat'): ['openrouter/auto', 'openai/gpt-4o-mini', 'anthropic/claude-sonnet-4', 'google/gemini-2.5-flash', 'deepseek/deepseek-chat-v3.1'],
    ('groq',       'chat'): ['llama-3.3-70b-versatile', 'llama-3.1-70b-versatile', 'llama3-8b-8192', 'mixtral-8x7b-32768', 'gemma2-9b-it'],
    ('mistral',    'chat'): ['mistral-large-latest', 'mistral-medium-latest', 'mistral-small-latest', 'codestral-latest', 'open-mistral-nemo'],
    ('grok',       'chat'): ['grok-3-mini', 'grok-3', 'grok-2-1212', 'grok-2-vision-1212'],
    ('perplexity', 'chat'): ['sonar-pro', 'sonar', 'sonar-reasoning-pro', 'sonar-reasoning'],
    ('together',   'chat'): ['meta-llama/Llama-3.3-70B-Instruct-Turbo', 'meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo', 'mistralai/Mistral-7B-Instruct-v0.3', 'Qwen/Qwen2.5-72B-Instruct-Turbo'],
    ('cohere',     'chat'): ['command-r-plus-08-2024', 'command-r-08-2024', 'command-r7b-12-2024'],
    ('lm_studio',  'chat'): ['local-model'],
    ('other',      'chat'): ['custom-model'],

    # ── General AI Agent (same providers as chat, tuned for speed/cost) ────────
    ('openai',     'agent'): ['gpt-4o-mini', 'gpt-4o', 'o3-mini', 'gpt-3.5-turbo'],
    ('anthropic',  'agent'): ['claude-haiku-4-5-20251001', 'claude-sonnet-4-6', 'claude-opus-4-8'],
    ('google',     'agent'): ['gemini-2.0-flash', 'gemini-2.0-flash-lite', 'gemini-1.5-flash', 'gemini-1.5-pro'],
    ('deepseek',   'agent'): ['deepseek-v4-flash', 'deepseek-v4-pro'],
    ('qwen',       'agent'): ['qwen-turbo', 'qwen-plus', 'qwen-max', 'qwq-32b'],
    ('kimi',       'agent'): ['moonshot-v1-8k', 'moonshot-v1-32k', 'moonshot-v1-128k'],
    ('glm',        'agent'): ['glm-4.5-flash', 'glm-4.5-air', 'glm-4.6', 'glm-4.5'],
    ('openrouter', 'agent'): ['openrouter/auto', 'openai/gpt-4o-mini', 'anthropic/claude-sonnet-4', 'google/gemini-2.5-flash', 'deepseek/deepseek-chat-v3.1'],
    ('groq',       'agent'): ['llama-3.3-70b-versatile', 'llama3-8b-8192', 'mixtral-8x7b-32768', 'gemma2-9b-it'],
    ('mistral',    'agent'): ['mistral-small-latest', 'mistral-large-latest', 'open-mistral-nemo'],
    ('grok',       'agent'): ['grok-3-mini', 'grok-3', 'grok-2-1212'],
    ('perplexity', 'agent'): ['sonar', 'sonar-pro', 'sonar-reasoning'],
    ('together',   'agent'): ['meta-llama/Llama-3.3-70B-Instruct-Turbo', 'meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo', 'Qwen/Qwen2.5-72B-Instruct-Turbo'],
    ('cohere',     'agent'): ['command-r7b-12-2024', 'command-r-08-2024', 'command-r-plus-08-2024'],
    ('lm_studio',  'agent'): ['local-model'],
    ('other',      'agent'): ['custom-model'],
}


class AIProviderConfigSerializer(serializers.ModelSerializer):
    api_key_masked = serializers.SerializerMethodField()
    # Write-only: only sent when creating or explicitly changing the key.
    # An empty/absent value on update leaves the stored key unchanged.
    api_key = serializers.CharField(write_only=True, required=False, allow_blank=True)
    provider_label = serializers.CharField(source='get_provider_display', read_only=True)
    capability_label = serializers.CharField(source='get_capability_display', read_only=True)

    class Meta:
        model = AIProviderConfig
        fields = [
            'id', 'display_name', 'provider', 'provider_label',
            'capability', 'capability_label',
            'api_key', 'api_key_masked',
            'model', 'base_url', 'extra_config',
            'is_active', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_api_key_masked(self, obj):
        return obj.masked_key()

    def validate_api_key(self, value):
        return value.strip()

    def validate(self, attrs):
        # On update, drop api_key from attrs if it is empty (keep existing key)
        if self.instance and not attrs.get('api_key'):
            attrs.pop('api_key', None)
        provider = attrs.get('provider') or getattr(self.instance, 'provider', '')
        api_key_optional = provider == AIProviderConfig.PROVIDER_LM_STUDIO
        # On create, api_key is required except for local LM Studio.
        if not self.instance and not attrs.get('api_key') and not api_key_optional:
            raise serializers.ValidationError({'api_key': 'API key is required.'})
        return attrs

    def create(self, validated_data):
        # Activating this provider deactivates any other active provider for the same capability
        if validated_data.get('is_active'):
            AIProviderConfig.objects.filter(
                capability=validated_data['capability'], is_active=True
            ).update(is_active=False)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        if validated_data.get('is_active') and not instance.is_active:
            AIProviderConfig.objects.filter(
                capability=instance.capability, is_active=True
            ).exclude(pk=instance.pk).update(is_active=False)
        return super().update(instance, validated_data)


class ProviderMetaSerializer(serializers.Serializer):
    """Static metadata about supported providers — returned by the /meta endpoint."""
    providers = serializers.DictField()
    capabilities = serializers.DictField()
    models = serializers.DictField()


class KiwiRouterMemberSerializer(serializers.ModelSerializer):
    provider_name = serializers.CharField(source='provider_config.display_name', read_only=True)
    provider_model = serializers.CharField(source='provider_config.model', read_only=True)

    class Meta:
        model = KiwiRouterMember
        fields = ['id', 'provider_config', 'provider_name', 'provider_model', 'priority', 'is_enabled',
                  'rpm_limit', 'tpm_limit', 'max_concurrency', 'input_cost_per_million',
                  'output_cost_per_million', 'metadata_source', 'metadata_verified_at',
                  'metadata_review_due_at', 'request_timeout_seconds']


class KiwiRouterSerializer(serializers.ModelSerializer):
    members = KiwiRouterMemberSerializer(many=True)

    class Meta:
        model = KiwiRouter
        fields = ['id', 'name', 'description', 'capability', 'strategy', 'default_request_timeout_seconds',
                  'is_active', 'members', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_members(self, members):
        priorities = [member['priority'] for member in members]
        if len(priorities) != len(set(priorities)):
            raise serializers.ValidationError('Each router member needs a unique priority.')
        return members

    def validate(self, attrs):
        capability = attrs.get('capability', getattr(self.instance, 'capability', ''))
        for member in attrs.get('members', []):
            if member['provider_config'].capability != capability:
                raise serializers.ValidationError({'members': 'Every member must match the router capability.'})
        return attrs

    def create(self, validated_data):
        members = validated_data.pop('members', [])
        router = KiwiRouter.objects.create(**validated_data)
        KiwiRouterMember.objects.bulk_create([KiwiRouterMember(router=router, **member) for member in members])
        return router

    def update(self, instance, validated_data):
        members = validated_data.pop('members', None)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        if members is not None:
            if instance.members.filter(reservations__isnull=False).exists():
                raise serializers.ValidationError({'members': 'Cannot replace members after routing activity exists.'})
            instance.members.all().delete()
            KiwiRouterMember.objects.bulk_create([KiwiRouterMember(router=instance, **member) for member in members])
        return instance


class KiwiRoutingDecisionSerializer(serializers.ModelSerializer):
    member_name = serializers.CharField(source='member.provider_config.display_name', read_only=True)

    class Meta:
        model = KiwiRoutingDecision
        fields = ['id', 'workflow_key', 'decision', 'reason', 'correlation_id', 'task_id',
                  'strategy', 'member_name', 'estimated_input_tokens', 'estimated_output_tokens', 'created_at']
