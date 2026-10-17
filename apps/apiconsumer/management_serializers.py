from rest_framework import serializers

from .models import ApiKey


class ApiKeyCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    scopes = serializers.MultipleChoiceField(choices=ApiKey.SCOPE_CHOICES)
    expires_at = serializers.DateTimeField(required=False, allow_null=True)


class ApiKeySerializer(serializers.ModelSerializer):
    class Meta:
        model = ApiKey
        fields = [
            'id', 'name', 'key_prefix', 'scopes', 'status',
            'created_at', 'revoked_at', 'last_used_at', 'expires_at',
        ]


class ApiKeyCreatedSerializer(ApiKeySerializer):
    secret = serializers.CharField()

    class Meta(ApiKeySerializer.Meta):
        fields = ApiKeySerializer.Meta.fields + ['secret']
