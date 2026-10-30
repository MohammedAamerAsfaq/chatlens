from rest_framework.exceptions import ValidationError

from apps.real_estate.api_base import CompanyOwnedViewSet
from apps.real_estate.models import PropertyAttributeDefinition
from apps.real_estate.serializers import (
    PropertyAttributeDefinitionSerializer, PropertyAttributeDefinitionWriteSerializer,
)
from apps.real_estate.services.property_attribute_catalog import seed_attribute_catalog


class PropertyAttributeDefinitionViewSet(CompanyOwnedViewSet):
    queryset = PropertyAttributeDefinition.objects.prefetch_related('aliases', 'options__aliases')
    read_permission = 'real_estate.properties.view'
    write_permission = 'real_estate.properties.manage'

    def get_serializer_class(self):
        if self.request.method in {'POST', 'PUT', 'PATCH'}:
            return PropertyAttributeDefinitionWriteSerializer
        return PropertyAttributeDefinitionSerializer

    def get_queryset(self):
        seed_attribute_catalog(self.active_company())
        queryset = super().get_queryset()
        if self.request.query_params.get('include_inactive') != 'true':
            queryset = queryset.filter(is_active=True)
        return queryset

    def perform_destroy(self, instance):
        if instance.is_system:
            raise ValidationError({'attribute': 'System attributes cannot be deactivated.'})
        instance.is_active = False
        instance.save(update_fields=['is_active'])
