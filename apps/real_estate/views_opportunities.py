from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from django.utils.dateparse import parse_date
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.real_estate.api_base import CompanyOwnedViewSet
from apps.real_estate.models import (
    InquiryMedium, Listing, OpportunityItem, Property, PropertyCandidate, PropertyRequirement,
    RealEstateOpportunity,
)
from apps.real_estate.serializers import (
    AreaInquirySerializer, InquiryMediumSerializer, ListingSerializer, ManualOpportunitySerializer,
    OpportunityItemSerializer, OpportunitySerializer,
    PropertyCandidateSerializer, PropertyRequirementSerializer,
)
from apps.real_estate.services.area_map import area_map_report, place_waiting_areas
from apps.real_estate.services.location_service import (
    BACKFILL_PRIORITY, clear_location, enqueue_location, locate_opportunity, merge_areas, set_manual_location,
)
from apps.real_estate.services.candidate_service import merge_candidate, promote_candidate, reject_candidate
from apps.real_estate.services.opportunity_item_service import (
    create_property_from_item, link_item, unlink_item,
)
from apps.real_estate.services.inquiry_media import seed_default_inquiry_media
from apps.real_estate.services.manual_opportunities import create_manual_opportunity
from apps.real_estate.services.opportunity_search import ALL_ACTIVITY_TYPES, search_opportunities
from apps.real_estate.services.opportunity_search_input import prepare_opportunity_search
from apps.real_estate.services.opportunity_counterparts import counterpart_activity, counterpart_search_plan

# Grid column -> model field the Area Map inquiries grid may sort by.
AREA_INQUIRY_ORDERING = {
    'first_seen_at': 'first_seen_at',
    'activity_type': 'activity_type',
    'status': 'status',
    'source_chat_name': 'source_chat__name',
}


class OpportunityViewSet(CompanyOwnedViewSet):
    queryset = RealEstateOpportunity.objects.select_related(
        'account', 'contact', 'assigned_to', 'source_chat', 'inquiry_medium',
        'requirement', 'property_candidate', 'property_candidate__property_type',
    ).prefetch_related('items__property_type', 'items__property', 'items__linked_by', 'items__geo_area_location')
    serializer_class = OpportunitySerializer
    read_permission = 'real_estate.opportunities.view'
    write_permission = 'real_estate.opportunities.update'
    scope_filter_field = 'assigned_to_id'
    account_scope_field = 'account'
    http_method_names = ['get', 'post', 'put', 'patch', 'head', 'options']

    def get_queryset(self):
        qs = super().get_queryset()
        for param in ('activity_type', 'classification_status', 'status'):
            value = self.request.query_params.get(param)
            if value and not (param == 'activity_type' and value == ALL_ACTIVITY_TYPES):
                qs = qs.filter(**{param: value})
        if search := self.request.query_params.get('search'):
            qs = qs.filter(
                Q(summary__icontains=search)
                | Q(original_message__icontains=search)
                | Q(contact__display_name__icontains=search)
                | Q(contact__push_name__icontains=search)
                | Q(contact__phone_number__icontains=search)
                | Q(source_chat__name__icontains=search)
                | Q(source_party_name__icontains=search)
                | Q(source_contact_detail__icontains=search)
                | Q(source_reference__icontains=search)
                | Q(items__title__icontains=search)
                | Q(items__location_raw__icontains=search)
                | Q(items__property__title__icontains=search)
            ).distinct()
        return qs

    def create(self, request, *args, **kwargs):
        return Response(
            {'detail': 'Use the manual endpoint to create an opportunity.'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    @action(detail=False, methods=['post'], url_path='manual')
    def manual(self, request):
        company = self.active_company()
        serializer = ManualOpportunitySerializer(
            data=request.data, context={'request': request, 'company': company},
        )
        serializer.is_valid(raise_exception=True)
        opportunity = create_manual_opportunity(
            company=company, user=request.user, validated_data=serializer.validated_data,
        )
        enqueue_location(opportunity)
        return Response(
            OpportunitySerializer(opportunity, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=['get'], url_path='search')
    def search(self, request):
        company = self.active_company()
        query = request.query_params.get('q', '')
        try:
            search_plan = prepare_opportunity_search(
                company=company,
                activity_type=request.query_params.get('activity_type', ''),
                query=query,
                mode=request.query_params.get('search_mode', 'hybrid'),
            )
            queryset = search_opportunities(
                self.get_queryset(),
                company=company,
                activity_type=request.query_params.get('activity_type', ''),
                query=query,
                relevance=request.query_params.get('relevance', 'possible'),
                group_duplicates=request.query_params.get('group_duplicates', '').lower() == 'true',
                search_plan=search_plan,
            )
        except ValueError as exc:
            field = _search_error_field(exc)
            raise ValidationError({field: str(exc)}) from exc
        except Exception as exc:
            raise ValidationError({'q': f'Unable to run semantic search: {exc}'}) from exc
        return self._search_response(queryset, search_plan)

    @action(detail=True, methods=['get'], url_path='counterparts')
    def counterparts(self, request, pk=None):
        """The other side of this opportunity (sellers for a buyer, buyers for a seller,
        landlords for a leasing inquiry, tenants for a leasing offer), ranked by the same
        hybrid search as Opportunity Search using this opportunity's property details."""
        opportunity = self.get_object()
        company = self.active_company()
        try:
            activity_type = counterpart_activity(opportunity)
            search_plan = counterpart_search_plan(opportunity)
            queryset = search_opportunities(
                self.get_queryset().exclude(pk=opportunity.pk),
                company=company,
                activity_type=activity_type,
                query=search_plan.embedding_query,
                relevance=request.query_params.get('relevance', 'possible'),
                group_duplicates=request.query_params.get('group_duplicates', '').lower() == 'true',
                search_plan=search_plan,
            )
        except ValueError as exc:
            field = 'relevance' if 'relevance' in str(exc).lower() else 'non_field_errors'
            raise ValidationError({field: str(exc)}) from exc
        except Exception as exc:
            raise ValidationError({'non_field_errors': f'Unable to run semantic search: {exc}'}) from exc
        return self._search_response(queryset, search_plan)

    @action(detail=False, methods=['get'], url_path='area-map')
    def area_map(self, request):
        """Inquiries per area (from the Location AI step) with each area's map position."""
        try:
            return Response(area_map_report(self.active_company(), self._area_map_queryset()))
        except ValueError as exc:
            raise ValidationError({'non_field_errors': str(exc)}) from exc

    @action(detail=False, methods=['get'], url_path='area-map/inquiries')
    def area_map_inquiries(self, request):
        """The inquiries behind the area map, one page at a time, with the map's filters
        (activity, status, dates) plus search, ordering and area=<AreaLocation id>, which
        gives exactly the inquiries counted in that area's bubble."""
        qs = self._area_map_queryset()
        if area := request.query_params.get('area'):
            try:
                area_id = int(area)
            except ValueError as exc:
                raise ValidationError({'area': 'Choose an area from the map.'}) from exc
            qs = qs.filter(pk__in=OpportunityItem.objects.filter(
                geo_area_location_id=area_id, geo_status=OpportunityItem.GEO_LOCATED,
            ).values('opportunity_id'))
        ordering = request.query_params.get('ordering') or '-first_seen_at'
        field = AREA_INQUIRY_ORDERING.get(ordering.lstrip('-'))
        if not field:
            raise ValidationError({'ordering': f'Sort by one of: {", ".join(AREA_INQUIRY_ORDERING)}.'})
        prefix = '-' if ordering.startswith('-') else ''
        qs = qs.order_by(f'{prefix}{field}', f'{prefix}id')
        page = self.paginate_queryset(qs)
        return self.get_paginated_response(AreaInquirySerializer(page, many=True).data)

    @action(detail=False, methods=['post'], url_path='area-map/place')
    def area_map_place(self, request):
        """Place the areas still waiting for a map position on Google Maps (paid, capped)."""
        company = self.active_company()
        opportunities = self._area_map_queryset()
        try:
            notice = place_waiting_areas(company, opportunities)
            report = area_map_report(company, opportunities)
        except ValueError as exc:
            raise ValidationError({'non_field_errors': str(exc)}) from exc
        report['notice'] = notice
        return Response(report)

    @action(detail=False, methods=['post'], url_path='area-map/merge')
    def area_map_merge(self, request):
        """Merge one area into another (e.g. "Creek Harbour" into "Dubai Creek Harbour")."""
        company = self.active_company()
        try:
            source, target = int(request.data.get('source')), int(request.data.get('target'))
        except (TypeError, ValueError) as exc:
            raise ValidationError({'non_field_errors': 'Choose the area to merge and the area to merge it into.'}) from exc
        try:
            moved = merge_areas(company, source, target)
            report = area_map_report(company, self._area_map_queryset())
        except ValueError as exc:
            raise ValidationError({'non_field_errors': str(exc)}) from exc
        report['merged'] = moved
        return Response(report)

    @action(detail=False, methods=['post'], url_path='area-map/locate')
    def area_map_locate(self, request):
        """Backfill: queue the Location AI step for these inquiries. scope=unlocated (not
        located yet or failed) or all (also re-check located ones, e.g. after changing the
        Real Estate Location instructions)."""
        scope = request.data.get('scope', 'unlocated')
        if scope not in ('unlocated', 'all'):
            raise ValidationError({'scope': 'Use unlocated or all.'})
        items = OpportunityItem.objects.filter(opportunity__in=self._area_map_queryset())
        if scope == 'unlocated':
            items = items.filter(geo_status__in=[OpportunityItem.GEO_PENDING, OpportunityItem.GEO_ERROR])
        items = items.exclude(geo_source=OpportunityItem.GEO_SOURCE_MANUAL)
        ids = items.values_list('opportunity_id', flat=True).distinct()
        queued = 0
        for opportunity in RealEstateOpportunity.objects.filter(pk__in=ids).select_related('company').iterator():
            if enqueue_location(opportunity, priority=BACKFILL_PRIORITY):
                queued += 1
        try:
            report = area_map_report(self.active_company(), self._area_map_queryset())
        except ValueError as exc:
            raise ValidationError({'non_field_errors': str(exc)}) from exc
        report['queued'] = queued
        return Response(report)

    @action(detail=True, methods=['post'], url_path='locate')
    def locate(self, request, pk=None):
        """Find this inquiry's location with the Location AI now (replaces locations set by hand)."""
        opportunity = self.get_object()
        if not opportunity.items.exists():
            raise ValidationError({'non_field_errors': 'This inquiry has no property details to locate.'})
        try:
            locate_opportunity(opportunity, include_manual=True)
        except Exception as exc:
            raise ValidationError({'non_field_errors': f'The location AI failed: {exc}'}) from exc
        return Response(self.get_serializer(self.get_object()).data)

    @action(detail=True, methods=['post'], url_path='location')
    def location(self, request, pk=None):
        """Set (action=set, with area, sub_area, city) or clear (action=clear) one property's
        location by hand."""
        opportunity = self.get_object()
        item = opportunity.items.filter(pk=request.data.get('item')).first()
        if not item:
            raise ValidationError({'item': 'Choose a property of this inquiry.'})
        mode = request.data.get('action')
        try:
            if mode == 'set':
                set_manual_location(
                    item, area=request.data.get('area'), sub_area=request.data.get('sub_area'),
                    city=request.data.get('city'), user=request.user,
                )
            elif mode == 'clear':
                clear_location(item, user=request.user)
            else:
                raise ValidationError({'action': 'Use set or clear.'})
        except ValueError as exc:
            raise ValidationError({'area': str(exc)}) from exc
        return Response(self.get_serializer(self.get_object()).data)

    def _area_map_queryset(self):
        qs = self.get_queryset()
        params = self.request.query_params
        for name, lookup in (('date_from', 'first_seen_at__date__gte'), ('date_to', 'first_seen_at__date__lte')):
            if value := params.get(name):
                parsed = parse_date(value)
                if not parsed:
                    raise ValidationError({name: 'Use a date like 2026-11-24.'})
                qs = qs.filter(**{lookup: parsed})
        return qs

    def _search_response(self, queryset, search_plan):
        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page, many=True)
        response = self.get_paginated_response(serializer.data)
        response.data['search_mode'] = search_plan.mode
        response.data['search_interpretation'] = search_plan.interpretation
        response.data['search_corrections'] = list(search_plan.constraints.corrections)
        return response


class InquiryMediumViewSet(CompanyOwnedViewSet):
    queryset = InquiryMedium.objects.all()
    serializer_class = InquiryMediumSerializer
    read_permission = 'real_estate.opportunities.view'
    write_permission = 'real_estate.opportunities.update'
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']

    def get_queryset(self):
        seed_default_inquiry_media(self.active_company())
        queryset = super().get_queryset()
        if self.request.query_params.get('include_inactive', '').lower() != 'true':
            queryset = queryset.filter(is_active=True)
        return queryset

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=['is_active', 'updated_at'])


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


def _search_error_field(exc):
    message = str(exc).lower()
    if 'activity type' in message:
        return 'activity_type'
    if 'search mode' in message:
        return 'search_mode'
    if 'relevance' in message:
        return 'relevance'
    return 'q'
