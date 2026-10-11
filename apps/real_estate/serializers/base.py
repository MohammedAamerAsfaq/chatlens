from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers


class CleanModelSerializer(serializers.ModelSerializer):
    def create(self, validated_data):
        instance = self.Meta.model(**validated_data)
        self._clean(instance)
        instance.save()
        return instance

    def update(self, instance, validated_data):
        for field, value in validated_data.items():
            setattr(instance, field, value)
        self._clean(instance)
        instance.save()
        return instance

    @staticmethod
    def _clean(instance):
        try:
            instance.full_clean()
        except DjangoValidationError as exc:
            detail = getattr(exc, 'message_dict', None) or {'non_field_errors': exc.messages}
            raise serializers.ValidationError(detail) from exc
