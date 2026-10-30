from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.real_estate.api_base import CompanyOwnedViewSet
from apps.real_estate.models import (
    Listing, OpportunityItem, Property, PropertyAddress, PropertyDevelopment,
    PropertyMedia, PropertyType,
)
from apps.real_estate.serializers import (
    ListingSerializer, PropertyAddressSerializer, PropertyDevelopmentSerializer,
    PropertyMediaSerializer, PropertySerializer,
    PropertyTypeSerializer,
)
from apps.real_estate.services.inventory_export import property_export_response
from apps.real_estate.services.inventory_import import import_rows, parse_csv_upload, preview_rows
from apps.real_estate.services.mock_source_preview import preview_workbooks


class PropertyTypeViewSet(CompanyOwnedViewSet):
    queryset = PropertyType.objects.select_related('parent').prefetch_related('field_definitions')
    serializer_class = PropertyTypeSerializer
    read_permission = 'real_estate.properties.view'
    write_permission = 'real_estate.properties.manage'

    def get_queryset(self):
        from apps.real_estate.services.property_types import seed_default_property_types

        seed_default_property_types(self.active_company())
        qs = super().get_queryset()
        if self.request.query_params.get('include_inactive') != 'true':
            qs = qs.filter(is_active=True)
        return qs

    def perform_destroy(self, instance):
        if instance.code == 'other':
            raise ValidationError({'property_type': 'The fallback Other type cannot be deactivated.'})
        instance.is_active = False
        instance.save(update_fields=['is_active', 'updated_at'])


class PropertyViewSet(CompanyOwnedViewSet):
    queryset = Property.objects.select_related(
        'assigned_to', 'property_type', 'parent', 'address', 'address__country_master',
        'address__administrative_area_master', 'address__city_master',
        'address__locality_master', 'address__development_master',
    ).prefetch_related('media', 'party_associations__party').annotate(
        child_count=Count('children', distinct=True),
    )
    serializer_class = PropertySerializer
    read_permission = 'real_estate.properties.view'
    write_permission = 'real_estate.properties.manage'

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.query_params.get('archived') != 'true':
            qs = qs.filter(is_archived=False)
        if value := self.request.query_params.get('property_type'):
            qs = qs.filter(property_type__code=value)
        if value := self.request.query_params.get('status'):
            qs = qs.filter(availability_status=value)
        if value := self.request.query_params.get('inventory_type'):
            qs = qs.filter(is_tracked=True) if value == 'tracked' else qs.filter(inventory_source_type=value)
        if value := self.request.query_params.get('ownership_eligibility'):
            qs = qs.filter(ownership_eligibility=value)
        if value := self.request.query_params.get('tenure_type'):
            qs = qs.filter(tenure_type=value)
        if search := self.request.query_params.get('search'):
            qs = qs.filter(
                Q(title__icontains=search) | Q(reference_code__icontains=search)
                | Q(project_name__icontains=search) | Q(parent__title__icontains=search)
                | Q(party_associations__party__first_name__icontains=search)
                | Q(party_associations__party__last_name__icontains=search)
                | Q(party_associations__party__organization_name__icontains=search)
            ).distinct()
        allowed = {
            'title', 'property_type', 'bedrooms', 'built_up_area',
            'availability_status', 'inventory_source_type', 'updated_at',
        }
        ordering = self.request.query_params.get('ordering', '-updated_at')
        if ordering.lstrip('-') in allowed:
            prefix = '-' if ordering.startswith('-') else ''
            field = 'property_type__name' if ordering.lstrip('-') == 'property_type' else ordering.lstrip('-')
            qs = qs.order_by(f'{prefix}{field}')
        return qs

    @action(detail=False, methods=['get'], url_path='hierarchy-options')
    def hierarchy_options(self, request):
        rows = super().get_queryset().filter(is_archived=False).order_by('title', 'id').values(
            'id', 'title', 'reference_code', 'parent_id',
        )
        return Response(list(rows))

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

    @action(detail=False, methods=['post'], url_path='mock-source-preview')
    def mock_source_preview(self, request):
        result = preview_workbooks(
            self.active_company(),
            request.FILES.getlist('files'),
            request.data.get('record_limit', 10),
        )
        return Response(result)

    @action(detail=False, methods=['post'], url_path='bulk-import')
    def bulk_import(self, request):
        rows = request.data.get('rows')
        if not isinstance(rows, list) or not rows:
            raise ValidationError({'rows': 'Provide at least one reviewed row.'})
        result = import_rows(self.active_company(), rows)
        return Response(result, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'], url_path='review-import-rows')
    def review_import_rows(self, request):
        rows = request.data.get('rows')
        if not isinstance(rows, list) or not rows:
            raise ValidationError({'rows': 'Provide at least one row to validate.'})
        reviewed = preview_rows(self.active_company(), rows)
        return Response({'rows': reviewed, 'count': len(reviewed)})

    @action(detail=False, methods=['get'])
    def export(self, request):
        return property_export_response(self.get_queryset())

    @action(detail=False, methods=['get'], url_path='embedding-status')
    def embedding_status(self, request):
        from apps.real_estate.services.embedding_dispatch import embedding_status

        return Response(embedding_status(self.active_company()))

    @action(detail=False, methods=['post'], url_path='backfill-embeddings')
    def backfill_embeddings(self, request):
        from apps.ai_providers.models import AIProviderConfig
        from apps.real_estate.services.embedding_dispatch import enqueue_backfill

        company = self.active_company()
        if not AIProviderConfig.objects.filter(
            company=company,
            capability=AIProviderConfig.CAPABILITY_EMBEDDING,
            is_active=True,
        ).exists():
            raise ValidationError({
                'embedding_provider': 'Configure an active company-owned embedding provider first.',
            })
        return Response(enqueue_backfill(company), status=status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=['get'], url_path='market-activity')
    def market_activity(self, request, pk=None):
        property_record = self.get_object()
        items = OpportunityItem.objects.filter(
            company=self.active_company(), property=property_record,
        ).select_related('opportunity', 'opportunity__contact', 'opportunity__source_chat')
        counts = {
            row['opportunity__activity_type']: row['total']
            for row in items.values('opportunity__activity_type').annotate(total=Count('id'))
        }
        recent = [{
            'item_id': item.id,
            'opportunity_id': item.opportunity_id,
            'activity_type': item.opportunity.activity_type,
            'party': _opportunity_party(item.opportunity),
            'summary': item.opportunity.summary,
            'match_status': item.match_status,
            'first_seen_at': item.opportunity.first_seen_at,
        } for item in items.order_by('-opportunity__first_seen_at')[:50]]
        return Response({'counts': counts, 'total': items.count(), 'recent': recent})


class PropertyAddressViewSet(CompanyOwnedViewSet):
    queryset = PropertyAddress.objects.select_related(
        'property', 'country_master', 'administrative_area_master', 'city_master',
        'locality_master', 'development_master',
    )
    serializer_class = PropertyAddressSerializer
    read_permission = 'real_estate.properties.view'
    write_permission = 'real_estate.properties.manage'


class PropertyDevelopmentViewSet(CompanyOwnedViewSet):
    queryset = PropertyDevelopment.objects.select_related('locality', 'parent')
    serializer_class = PropertyDevelopmentSerializer
    read_permission = 'real_estate.properties.view'
    write_permission = 'real_estate.properties.manage'

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.request.query_params.get('include_inactive') != 'true':
            queryset = queryset.filter(is_active=True)
        if value := self.request.query_params.get('locality_id'):
            queryset = queryset.filter(locality_id=value)
        if value := self.request.query_params.get('type'):
            queryset = queryset.filter(development_type=value)
        if search := self.request.query_params.get('search'):
            queryset = queryset.filter(
                Q(name__icontains=search) | Q(normalized_name__icontains=search)
                | Q(developer_name__icontains=search)
            )
        return queryset

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=['is_active', 'updated_at'])


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


def _opportunity_party(opportunity):
    contact = opportunity.contact
    if contact:
        return contact.display_name or contact.push_name or contact.phone_number
    return opportunity.source_chat.name if opportunity.source_chat else 'Unknown party'
