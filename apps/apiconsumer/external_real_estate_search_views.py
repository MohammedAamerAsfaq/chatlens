"""Company-scoped semantic opportunity search for external API consumers."""

from rest_framework import generics
from rest_framework.exceptions import ValidationError

from apps.real_estate.models import RealEstateOpportunity
from apps.real_estate.serializers import OpportunitySerializer
from apps.real_estate.services.opportunity_search import search_opportunities

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
        try:
            queryset = search_opportunities(
                self.get_queryset(),
                company=request.auth.company,
                activity_type=request.query_params.get('activity_type', ''),
                query=request.query_params.get('q', ''),
                relevance=request.query_params.get('relevance', 'possible'),
                group_duplicates=request.query_params.get('group_duplicates', '').lower() == 'true',
            )
        except ValueError as exc:
            field = 'activity_type' if 'activity type' in str(exc).lower() else 'relevance'
            raise ValidationError({field: str(exc)}) from exc
        except Exception as exc:
            raise ValidationError({'q': f'Unable to run semantic search: {exc}'}) from exc

        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)
