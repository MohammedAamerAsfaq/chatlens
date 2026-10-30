from django.db import transaction
from rest_framework import serializers

from apps.real_estate.models import (
    PropertyAttributeAlias, PropertyAttributeDefinition, PropertyAttributeOption,
)
from .base import CleanModelSerializer


class PropertyAttributeAliasSerializer(serializers.ModelSerializer):
    class Meta:
        model = PropertyAttributeAlias
        fields = ('id', 'alias', 'locale', 'is_active')


class PropertyAttributeOptionSerializer(serializers.ModelSerializer):
    aliases = serializers.SerializerMethodField()

    class Meta:
        model = PropertyAttributeOption
        fields = (
            'id', 'code', 'label', 'numeric_value', 'sort_order', 'is_active', 'aliases',
        )

    @staticmethod
    def get_aliases(obj):
        return [row.alias for row in obj.aliases.all() if row.is_active]


class PropertyAttributeDefinitionSerializer(CleanModelSerializer):
    aliases = serializers.SerializerMethodField()
    options = PropertyAttributeOptionSerializer(many=True, read_only=True)

    class Meta:
        model = PropertyAttributeDefinition
        exclude = ('company',)
        read_only_fields = ('is_system',)

    @staticmethod
    def get_aliases(obj):
        return [row.alias for row in obj.aliases.all() if row.option_id is None and row.is_active]


class PropertyAttributeDefinitionWriteSerializer(PropertyAttributeDefinitionSerializer):
    aliases = serializers.ListField(
        child=serializers.CharField(max_length=160), required=False,
    )
    options = serializers.ListField(child=serializers.DictField(), required=False)

    @transaction.atomic
    def create(self, validated_data):
        aliases = validated_data.pop('aliases', [])
        options = validated_data.pop('options', [])
        instance = super().create(validated_data)
        self._sync(instance, aliases, options)
        return instance

    @transaction.atomic
    def update(self, instance, validated_data):
        aliases = validated_data.pop('aliases', None)
        options = validated_data.pop('options', None)
        instance = super().update(instance, validated_data)
        self._sync(instance, aliases, options)
        return instance

    def _sync(self, definition, aliases, options):
        if aliases is not None:
            self._sync_aliases(definition, None, aliases)
        if options is None:
            return
        retained = []
        for position, payload in enumerate(options):
            code = str(payload.get('code') or '').strip().lower()
            label = str(payload.get('label') or '').strip()
            if not code or not label:
                raise serializers.ValidationError({'options': 'Every option needs a code and label.'})
            numeric_value = payload.get('numeric_value')
            if numeric_value in ('', None):
                numeric_value = None
            option, _created = PropertyAttributeOption.objects.update_or_create(
                company=definition.company, definition=definition, code=code,
                defaults={
                    'label': label,
                    'numeric_value': numeric_value,
                    'sort_order': payload.get('sort_order', position),
                    'is_active': payload.get('is_active', True),
                },
            )
            option.full_clean()
            option.save()
            retained.append(option.pk)
            self._sync_aliases(definition, option, payload.get('aliases', []))
        definition.options.exclude(pk__in=retained).update(is_active=False)

    @staticmethod
    def _sync_aliases(definition, option, aliases):
        normalized = {
            PropertyAttributeAlias.normalize(value): str(value).strip()
            for value in aliases if str(value).strip()
        }
        scope = definition.aliases.filter(option=option)
        scope.exclude(normalized_alias__in=normalized).update(is_active=False)
        for normalized_value, value in normalized.items():
            alias, _created = PropertyAttributeAlias.objects.update_or_create(
                company=definition.company,
                definition=definition,
                normalized_alias=normalized_value,
                defaults={'option': option, 'alias': value, 'is_active': True},
            )
            alias.full_clean()
            alias.save()
