"""Hybrid semantic and structured search over Real Estate opportunities."""

from pgvector.django import CosineDistance

from apps.ai_providers.manager import ai_manager
from apps.real_estate.models import ActivityType, ClassificationStatus, EmbeddingStatus
from apps.real_estate.services.opportunity_search_query import (
    normalize as _normalize,
    parse_constraints,
)
from apps.real_estate.services.opportunity_search_scoring import rank_opportunity


RELEVANCE_THRESHOLDS = {'all': 0.0, 'possible': 0.35, 'strong': 0.55}


def search_opportunities(
    queryset, *, company, activity_type, query, relevance='possible', group_duplicates=False,
    search_plan=None,
):
    """Return a lane ranked by vectors plus explicit property constraints."""
    _validate(activity_type, relevance)
    queryset = queryset.filter(
        activity_type=activity_type,
        classification_status=ClassificationStatus.CLASSIFIED,
    )
    query = (query or '').strip()
    if not query:
        return queryset

    embedding_query = search_plan.embedding_query if search_plan else query
    vector = ai_manager.embed(embedding_query, company=company)
    is_requirement = activity_type in ActivityType.requirement_values()
    embedding_field = (
        'requirement__embedding_record__embedding'
        if is_requirement else 'property_candidate__embedding_record__embedding'
    )
    status_field = (
        'requirement__embedding_record__status'
        if is_requirement else 'property_candidate__embedding_record__status'
    )
    rows = list(queryset.filter(
        **{status_field: EmbeddingStatus.EMBEDDED, f'{embedding_field}__isnull': False},
    ).annotate(search_distance=CosineDistance(embedding_field, vector)))
    constraints = search_plan.constraints if search_plan else parse_constraints(query, company)
    for row in rows:
        rank_opportunity(row, constraints)
    rows = [
        row for row in rows
        if not row.search_excluded and row.search_score >= RELEVANCE_THRESHOLDS[relevance]
    ]
    rows.sort(key=lambda row: (-row.search_score, -row.first_seen_at.timestamp(), -row.pk))
    return _group(rows) if group_duplicates else rows


def _validate(activity_type, relevance):
    if activity_type not in {value for value, _label in ActivityType.choices}:
        raise ValueError('A valid Real Estate activity type is required.')
    if relevance not in RELEVANCE_THRESHOLDS:
        raise ValueError('Relevance must be all, possible, or strong.')


def _group(rows):
    grouped, by_key = [], {}
    for row in rows:
        key = _row_fingerprint(row)
        if not key or key not in by_key:
            grouped.append(row)
            if key:
                by_key[key] = row
            continue
        primary = by_key[key]
        primary.duplicate_count += 1
        primary.duplicate_opportunity_ids.append(row.pk)
    return grouped


def _row_fingerprint(row):
    items = list(row.items.all())
    if not items:
        return ''
    values = []
    for item in items:
        amount = item.amount_min or item.amount_max
        values.append((
            item.property_type_id or 0, _normalize(item.location_raw),
            str(item.bedrooms_min or ''), str(amount or ''), item.currency,
        ))
    return repr(sorted(values))
