"""Semantic search over the demand and supply projections of opportunities."""

from pgvector.django import CosineDistance

from apps.ai_providers.manager import ai_manager
from apps.real_estate.models import ActivityType, ClassificationStatus, EmbeddingStatus


def search_opportunities(queryset, *, company, activity_type, query):
    """Return one activity lane, ranked by its canonical projection embedding."""
    valid_activities = {value for value, _label in ActivityType.choices}
    if activity_type not in valid_activities:
        raise ValueError('A valid Real Estate activity type is required.')

    queryset = queryset.filter(
        activity_type=activity_type,
        classification_status=ClassificationStatus.CLASSIFIED,
    )
    query = (query or '').strip()
    if not query:
        return queryset

    vector = ai_manager.embed(query, company=company)
    if activity_type in ActivityType.requirement_values():
        return queryset.filter(
            requirement__embedding_record__status=EmbeddingStatus.EMBEDDED,
            requirement__embedding_record__embedding__isnull=False,
        ).annotate(
            search_distance=CosineDistance(
                'requirement__embedding_record__embedding', vector,
            ),
        ).order_by('search_distance', '-first_seen_at', '-id')

    return queryset.filter(
        property_candidate__embedding_record__status=EmbeddingStatus.EMBEDDED,
        property_candidate__embedding_record__embedding__isnull=False,
    ).annotate(
        search_distance=CosineDistance(
            'property_candidate__embedding_record__embedding', vector,
        ),
    ).order_by('search_distance', '-first_seen_at', '-id')
