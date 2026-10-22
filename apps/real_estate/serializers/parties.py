from rest_framework import serializers

from apps.real_estate.models import Party, PropertyPartyAssociation
from .base import CleanModelSerializer


class PartySerializer(CleanModelSerializer):
    display_name = serializers.CharField(read_only=True)

    class Meta:
        model = Party
        exclude = ('company',)
        read_only_fields = ('created_at', 'updated_at')


class PropertyPartyAssociationSerializer(CleanModelSerializer):
    party_name = serializers.CharField(source='party.display_name', read_only=True)
    party_phone = serializers.CharField(source='party.phone', read_only=True)
    property_title = serializers.CharField(source='property.title', read_only=True)
    relationship_label = serializers.CharField(source='get_relationship_type_display', read_only=True)

    class Meta:
        model = PropertyPartyAssociation
        exclude = ('company',)
        read_only_fields = ('created_at', 'updated_at')
