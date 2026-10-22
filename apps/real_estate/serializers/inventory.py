from rest_framework import serializers

from apps.real_estate.models import (
    Listing, Property, PropertyAddress, PropertyDevelopment, PropertyMedia, PropertyType,
    PropertyTypeFieldDefinition,
)
from .base import CleanModelSerializer, CompanyPropertyTypeField
from .parties import PropertyPartyAssociationSerializer


class PropertyTypeFieldDefinitionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PropertyTypeFieldDefinition
        fields = (
            'id', 'code', 'label', 'data_type', 'options', 'unit_hint',
            'is_required', 'is_filterable', 'is_embeddable',
            'condition_field', 'condition_value', 'sort_order', 'is_active',
        )


class PropertyTypeSerializer(CleanModelSerializer):
    field_definitions = PropertyTypeFieldDefinitionSerializer(many=True, read_only=True)

    def validate_code(self, value):
        from apps.real_estate.services.property_types import normalize_property_type_code

        normalized = normalize_property_type_code(value)
        if self.instance and normalized != self.instance.code:
            raise serializers.ValidationError('The code cannot be changed after creation.')
        return normalized

    class Meta:
        model = PropertyType
        exclude = ('company',)
        read_only_fields = ('created_at', 'updated_at')


class PropertyAddressSerializer(CleanModelSerializer):
    country_master_name = serializers.CharField(source='country_master.name', read_only=True)
    administrative_area_master_name = serializers.CharField(
        source='administrative_area_master.name', read_only=True,
    )
    city_master_name = serializers.CharField(source='city_master.name', read_only=True)
    locality_master_name = serializers.CharField(source='locality_master.name', read_only=True)
    development_master_name = serializers.CharField(source='development_master.name', read_only=True)

    class Meta:
        model = PropertyAddress
        exclude = ('company',)
        read_only_fields = ('created_at', 'updated_at')


class PropertyDevelopmentSerializer(CleanModelSerializer):
    locality_name = serializers.CharField(source='locality.name', read_only=True)
    parent_name = serializers.CharField(source='parent.name', read_only=True)

    def validate(self, attrs):
        from apps.integrations.services.geography_sync import normalize_name

        attrs['normalized_name'] = normalize_name(attrs.get('name', getattr(self.instance, 'name', '')))
        return attrs

    class Meta:
        model = PropertyDevelopment
        exclude = ('company',)
        read_only_fields = ('normalized_name', 'created_at', 'updated_at')


class PropertyMediaSerializer(CleanModelSerializer):
    class Meta:
        model = PropertyMedia
        exclude = ('company',)
        read_only_fields = ('created_at',)


class PropertySerializer(CleanModelSerializer):
    property_type = CompanyPropertyTypeField()
    property_type_name = serializers.CharField(source='property_type.name', read_only=True)
    address = PropertyAddressSerializer(read_only=True)
    media = PropertyMediaSerializer(many=True, read_only=True)
    parent_title = serializers.CharField(source='parent.title', read_only=True)
    child_count = serializers.IntegerField(read_only=True)
    party_associations = PropertyPartyAssociationSerializer(many=True, read_only=True)

    class Meta:
        model = Property
        exclude = ('company',)
        read_only_fields = ('is_archived', 'archived_at', 'created_at', 'updated_at')


class ListingSerializer(CleanModelSerializer):
    property_title = serializers.CharField(source='property.title', read_only=True)

    class Meta:
        model = Listing
        exclude = ('company',)
        read_only_fields = ('is_archived', 'archived_at', 'created_at', 'updated_at')
