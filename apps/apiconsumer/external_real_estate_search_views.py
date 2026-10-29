"""Company-scoped semantic opportunity search for external API consumers."""

from rest_framework import generics
from rest_framework.exceptions import ValidationError

from apps.real_estate.models import RealEstateOpportunity
from apps.real_estate.serializers import OpportunitySerializer
from apps.real_estate.services.opportunity_search import search_opportunities
from apps.real_estate.services.opportunity_search_input import prepare_opportunity_search

from .external_views import ExternalApiMixin
from .models import ApiKey


class RealEstateOpportunitySearchView(ExternalApiMixin, generics.GenericAPIView):
    """Search one Real Estate activity lane owned by the API key's company."""

    required_scope = ApiKey.SCOPE_DATA_READ
    serializer_class = OpportunitySerializer

    def get_queryset(self):
        queryset = RealEstateOpportunity.objects.filter(
            company=self.request.auth.company,
        ).select_related(
            'source_message', 'account', 'contact', 'assigned_to', 'source_chat',
            'inquiry_medium', 'requirement', 'property_candidate',
            'property_candidate__property_type',
        ).prefetch_related(
            'items__property_type', 'items__property', 'items__linked_by',
        )
        if status := self.request.query_params.get('status'):
            queryset = queryset.filter(status=status)
        return queryset

    def get(self, request):
        company = request.auth.company
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
            message = str(exc).lower()
            field = 'activity_type' if 'activity type' in message else (
                'search_mode' if 'search mode' in message else ('relevance' if 'relevance' in message else 'q')
            )
            raise ValidationError({field: str(exc)}) from exc
        except Exception as exc:
            raise ValidationError({'q': f'Unable to run semantic search: {exc}'}) from exc

        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page, many=True)
        response = self.get_paginated_response(serializer.data)
        response.data['search_mode'] = search_plan.mode
        response.data['search_interpretation'] = search_plan.interpretation
        return response
