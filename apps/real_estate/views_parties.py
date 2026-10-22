from django.db.models import Q

from apps.real_estate.api_base import CompanyOwnedViewSet
from apps.real_estate.models import Party, PropertyPartyAssociation
from apps.real_estate.serializers import PartySerializer, PropertyPartyAssociationSerializer


class PartyViewSet(CompanyOwnedViewSet):
    queryset = Party.objects.all()
    serializer_class = PartySerializer
    read_permission = 'real_estate.properties.view'
    write_permission = 'real_estate.properties.manage'

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.request.query_params.get('include_inactive') != 'true':
            queryset = queryset.filter(is_active=True)
        if search := self.request.query_params.get('search'):
            queryset = queryset.filter(
                Q(first_name__icontains=search) | Q(middle_name__icontains=search)
                | Q(last_name__icontains=search) | Q(organization_name__icontains=search)
                | Q(phone__icontains=search) | Q(email__icontains=search)
            )
        return queryset

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=['is_active', 'updated_at'])


class PropertyPartyAssociationViewSet(CompanyOwnedViewSet):
    queryset = PropertyPartyAssociation.objects.select_related('property', 'party')
    serializer_class = PropertyPartyAssociationSerializer
    read_permission = 'real_estate.properties.view'
    write_permission = 'real_estate.properties.manage'

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.request.query_params.get('include_inactive') != 'true':
            queryset = queryset.filter(is_active=True)
        for parameter, field in (
            ('property', 'property_id'), ('party', 'party_id'),
            ('relationship_type', 'relationship_type'),
        ):
            if value := self.request.query_params.get(parameter):
                queryset = queryset.filter(**{field: value})
        return queryset
