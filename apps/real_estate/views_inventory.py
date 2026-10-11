from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.real_estate.api_base import CompanyOwnedViewSet
from apps.real_estate.models import Listing, Property, PropertyAddress, PropertyMedia
from apps.real_estate.serializers import (
    ListingSerializer, PropertyAddressSerializer, PropertyMediaSerializer, PropertySerializer,
)
from apps.real_estate.services.inventory_export import property_export_response
from apps.real_estate.services.inventory_import import import_rows, parse_csv_upload, preview_rows


class PropertyViewSet(CompanyOwnedViewSet):
    queryset = Property.objects.select_related('assigned_to').prefetch_related('media')
    serializer_class = PropertySerializer
    read_permission = 'real_estate.properties.view'
    write_permission = 'real_estate.properties.manage'

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.query_params.get('archived') != 'true':
            qs = qs.filter(is_archived=False)
        if value := self.request.query_params.get('property_type'):
            qs = qs.filter(property_type=value)
        if value := self.request.query_params.get('status'):
            qs = qs.filter(availability_status=value)
        if search := self.request.query_params.get('search'):
            qs = qs.filter(Q(title__icontains=search) | Q(reference_code__icontains=search) | Q(project_name__icontains=search))
        allowed = {'title', 'property_type', 'bedrooms', 'built_up_area', 'availability_status', 'updated_at'}
        ordering = self.request.query_params.get('ordering', '-updated_at')
        if ordering.lstrip('-') in allowed:
            qs = qs.order_by(ordering)
        return qs

    def perform_destroy(self, instance):
        archived_at = timezone.now()
        with transaction.atomic():
            instance.listings.filter(is_archived=False).update(
                is_archived=True, archived_at=archived_at, status='closed', updated_at=archived_at,
            )
            instance.is_archived = True
            instance.archived_at = archived_at
            instance.availability_status = 'inactive'
            instance.save(update_fields=['is_archived', 'archived_at', 'availability_status', 'updated_at'])

    @action(detail=False, methods=['post'], url_path='import-preview')
    def import_preview(self, request):
        rows = parse_csv_upload(request.FILES.get('file'))
        preview = preview_rows(self.active_company(), rows)
        return Response({'rows': preview, 'count': len(preview)})

    @action(detail=False, methods=['post'], url_path='bulk-import')
    def bulk_import(self, request):
        rows = request.data.get('rows')
        if not isinstance(rows, list) or not rows:
            raise ValidationError({'rows': 'Provide at least one reviewed row.'})
        result = import_rows(self.active_company(), rows)
        return Response(result, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'])
    def export(self, request):
        return property_export_response(self.get_queryset())


class PropertyAddressViewSet(CompanyOwnedViewSet):
    queryset = PropertyAddress.objects.select_related('property')
    serializer_class = PropertyAddressSerializer
    read_permission = 'real_estate.properties.view'
    write_permission = 'real_estate.properties.manage'


class PropertyMediaViewSet(CompanyOwnedViewSet):
    queryset = PropertyMedia.objects.select_related('property')
    serializer_class = PropertyMediaSerializer
    read_permission = 'real_estate.properties.view'
    write_permission = 'real_estate.properties.manage'


class ListingViewSet(CompanyOwnedViewSet):
    queryset = Listing.objects.select_related('property', 'assigned_agent', 'source_contact')
    serializer_class = ListingSerializer
    read_permission = 'real_estate.listings.view'
    write_permission = 'real_estate.listings.manage'

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.query_params.get('archived') != 'true':
            qs = qs.filter(is_archived=False)
        for param, field in (('type', 'listing_type'), ('status', 'status'), ('property', 'property_id')):
            if value := self.request.query_params.get(param):
                qs = qs.filter(**{field: value})
        if search := self.request.query_params.get('search'):
            qs = qs.filter(Q(property__title__icontains=search) | Q(property__reference_code__icontains=search))
        ordering = self.request.query_params.get('ordering', '-updated_at')
        ordering = ordering.replace('property_title', 'property__title')
        allowed = {'property__title', 'listing_type', 'asking_price', 'status', 'is_verified', 'updated_at'}
        if ordering.lstrip('-') in allowed:
            qs = qs.order_by(ordering)
        return qs

    def perform_destroy(self, instance):
        instance.is_archived = True
        instance.archived_at = timezone.now()
        instance.status = 'closed'
        instance.save(update_fields=['is_archived', 'archived_at', 'status', 'updated_at'])
