from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.real_estate.api_base import CompanyOwnedViewSet
from apps.real_estate.models import (
    Listing, OpportunityItem, Property, PropertyCandidate, PropertyRequirement,
    RealEstateOpportunity,
)
from apps.real_estate.serializers import (
    ListingSerializer, OpportunityItemSerializer, OpportunitySerializer,
    PropertyCandidateSerializer, PropertyRequirementSerializer,
)
from apps.real_estate.services.candidate_service import merge_candidate, promote_candidate, reject_candidate
from apps.real_estate.services.opportunity_item_service import (
    create_property_from_item, link_item, unlink_item,
)


class OpportunityViewSet(CompanyOwnedViewSet):
    queryset = RealEstateOpportunity.objects.select_related(
        'account', 'contact', 'assigned_to', 'source_chat',
        'requirement', 'property_candidate', 'property_candidate__property_type',
    ).prefetch_related('items__property_type', 'items__property', 'items__linked_by')
    serializer_class = OpportunitySerializer
    read_permission = 'real_estate.opportunities.view'
    write_permission = 'real_estate.opportunities.update'
    scope_filter_field = 'assigned_to_id'
    account_scope_field = 'account'
    http_method_names = ['get', 'put', 'patch', 'head', 'options']

    def get_queryset(self):
        qs = super().get_queryset()
        for param in ('activity_type', 'classification_status', 'status'):
            if value := self.request.query_params.get(param):
                qs = qs.filter(**{param: value})
        if search := self.request.query_params.get('search'):
            qs = qs.filter(
                Q(summary__icontains=search)
                | Q(original_message__icontains=search)
                | Q(contact__display_name__icontains=search)
                | Q(contact__push_name__icontains=search)
                | Q(contact__phone_number__icontains=search)
                | Q(source_chat__name__icontains=search)
                | Q(items__title__icontains=search)
                | Q(items__location_raw__icontains=search)
                | Q(items__property__title__icontains=search)
            ).distinct()
        return qs


class OpportunityItemViewSet(CompanyOwnedViewSet):
    queryset = OpportunityItem.objects.select_related(
        'opportunity', 'property_type', 'property', 'linked_by',
    )
    serializer_class = OpportunityItemSerializer
    read_permission = 'real_estate.opportunities.view'
    write_permission = 'real_estate.opportunities.update'
    scope_filter_field = 'opportunity__assigned_to_id'
    account_scope_field = 'opportunity__account'
    http_method_names = ['get', 'patch', 'post', 'head', 'options']

    def create(self, request, *args, **kwargs):
        return Response(
            {'detail': 'Opportunity items are created only by extraction.'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    @action(detail=True, methods=['post'])
    def link(self, request, pk=None):
        item = self.get_object()
        property_record = Property.objects.filter(
            company=self.active_company(), pk=request.data.get('property_id'), is_archived=False,
        ).first()
        if not property_record:
            raise ValidationError({'property_id': 'A valid company property is required.'})
        try:
            item = link_item(item, property_record, request.user)
        except DjangoValidationError as exc:
            raise ValidationError(_validation_detail(exc)) from exc
        return Response(self.get_serializer(item).data)

    @action(detail=True, methods=['post'])
    def unlink(self, request, pk=None):
        return Response(self.get_serializer(unlink_item(self.get_object())).data)

    @action(detail=True, methods=['post'], url_path='create-property')
    def create_property(self, request, pk=None):
        try:
            item, property_record = create_property_from_item(self.get_object(), request.user)
        except DjangoValidationError as exc:
            raise ValidationError(_validation_detail(exc)) from exc
        return Response({
            'item': self.get_serializer(item).data,
            'property_id': property_record.pk,
        }, status=status.HTTP_201_CREATED)


class RequirementViewSet(CompanyOwnedViewSet):
    queryset = PropertyRequirement.objects.select_related('opportunity')
    serializer_class = PropertyRequirementSerializer
    read_permission = 'real_estate.opportunities.view'
    write_permission = 'real_estate.opportunities.update'
    scope_filter_field = 'opportunity__assigned_to_id'
    account_scope_field = 'opportunity__account'

    def get_queryset(self):
        qs = super().get_queryset()
        if value := self.request.query_params.get('review_status'):
            qs = qs.filter(review_status=value)
        return qs


class CandidateViewSet(CompanyOwnedViewSet):
    queryset = PropertyCandidate.objects.select_related(
        'opportunity', 'property_type', 'promoted_property', 'promoted_listing', 'reviewed_by',
    )
    serializer_class = PropertyCandidateSerializer
    read_permission = 'real_estate.opportunities.view'
    write_permission = 'real_estate.opportunities.update'
    scope_filter_field = 'opportunity__assigned_to_id'
    account_scope_field = 'opportunity__account'
    http_method_names = ['get', 'put', 'patch', 'post', 'head', 'options']

    def permission_code_for(self, request):
        if self.action in {'promote', 'merge'}:
            return 'real_estate.listings.manage'
        return super().permission_code_for(request)

    def get_queryset(self):
        qs = super().get_queryset()
        if value := self.request.query_params.get('review_status'):
            qs = qs.filter(review_status=value)
        if value := self.request.query_params.get('activity_type'):
            qs = qs.filter(opportunity__activity_type=value)
        if value := self.request.query_params.get('tracked'):
            qs = qs.filter(is_tracked=value.lower() == 'true')
        if search := self.request.query_params.get('search'):
            qs = qs.filter(Q(title__icontains=search) | Q(location_raw__icontains=search))
        return qs

    def create(self, request, *args, **kwargs):
        return Response({'detail': 'Candidates are created only by extraction.'}, status=status.HTTP_405_METHOD_NOT_ALLOWED)

    @action(detail=True, methods=['post'])
    def promote(self, request, pk=None):
        candidate = self.get_object()
        try:
            property_record, listing = promote_candidate(
                candidate,
                request.user,
                request.data.get('property'),
                request.data.get('listing'),
            )
        except DjangoValidationError as exc:
            raise ValidationError(_validation_detail(exc)) from exc
        return Response({
            'candidate': PropertyCandidateSerializer(candidate).data,
            'property_id': property_record.pk,
            'listing': ListingSerializer(listing).data,
        }, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def merge(self, request, pk=None):
        candidate = self.get_object()
        listing = Listing.objects.filter(
            company=self.active_company(), pk=request.data.get('listing_id'), is_archived=False,
        ).first()
        if not listing:
            raise ValidationError({'listing_id': 'A valid company listing is required.'})
        try:
            merge_candidate(candidate, listing, request.user)
        except DjangoValidationError as exc:
            raise ValidationError(_validation_detail(exc)) from exc
        return Response(PropertyCandidateSerializer(candidate).data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        candidate = self.get_object()
        try:
            reject_candidate(candidate, request.user)
        except DjangoValidationError as exc:
            raise ValidationError(_validation_detail(exc)) from exc
        return Response(PropertyCandidateSerializer(candidate).data)


def _validation_detail(exc):
    return getattr(exc, 'message_dict', None) or {'non_field_errors': exc.messages}
