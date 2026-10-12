from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.tenancy.services.access import default_company_for_user


class CompanyPropertyTypeField(serializers.Field):
    default_error_messages = {'invalid': 'Select an active property type for this company.'}

    def to_representation(self, value):
        return value.code if value else None

    def to_internal_value(self, data):
        from apps.real_estate.services.property_types import resolve_property_type

        request = self.context.get('request')
        company = default_company_for_user(request.user) if request else None
        match = resolve_property_type(company, data) if company else None
        if not match:
            self.fail('invalid')
        return match


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
