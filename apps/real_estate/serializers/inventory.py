from rest_framework import serializers

from apps.real_estate.models import Listing, Property, PropertyAddress, PropertyMedia, PropertyType
from .base import CleanModelSerializer, CompanyPropertyTypeField


class PropertyTypeSerializer(CleanModelSerializer):
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
    class Meta:
        model = PropertyAddress
        exclude = ('company',)
        read_only_fields = ('created_at', 'updated_at')


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
