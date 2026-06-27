from rest_framework import serializers
from .models import AIProviderConfig


# Default model options surfaced to the UI for each provider+capability combination.
PROVIDER_MODELS = {
    ('voyage', 'embedding'): ['voyage-3-lite', 'voyage-3', 'voyage-3-large', 'voyage-code-3'],
    ('openai', 'embedding'): ['text-embedding-3-small', 'text-embedding-3-large', 'text-embedding-ada-002'],
    ('openai', 'chat'):      ['gpt-4o-mini', 'gpt-4o', 'gpt-4-turbo', 'gpt-3.5-turbo'],
    ('anthropic', 'chat'):   ['claude-sonnet-4-6', 'claude-haiku-4-5-20251001', 'claude-opus-4-8'],
    ('cohere', 'embedding'): ['embed-v4', 'embed-english-v3.0', 'embed-multilingual-v3.0'],
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
        # On create, api_key is required
        if not self.instance and not attrs.get('api_key'):
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
