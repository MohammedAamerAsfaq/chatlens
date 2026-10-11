from rest_framework import serializers

from apps.real_estate.models import Listing, Property, PropertyAddress, PropertyMedia
from .base import CleanModelSerializer


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
