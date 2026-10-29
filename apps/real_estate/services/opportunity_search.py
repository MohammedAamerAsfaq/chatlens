"""Hybrid semantic and structured search over Real Estate opportunities."""

from decimal import Decimal

from pgvector.django import CosineDistance

from apps.ai_providers.manager import ai_manager
from apps.real_estate.models import ActivityType, ClassificationStatus, EmbeddingStatus
from apps.real_estate.services.opportunity_search_query import (
    normalize as _normalize,
    parse_constraints,
    tokens as _tokens,
)


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
        _rank(row, constraints)
    rows = [row for row in rows if row.search_score >= RELEVANCE_THRESHOLDS[relevance]]
    rows.sort(key=lambda row: (-row.search_score, -row.first_seen_at.timestamp(), -row.pk))
    return _group(rows) if group_duplicates else rows


def _validate(activity_type, relevance):
    if activity_type not in {value for value, _label in ActivityType.choices}:
        raise ValueError('A valid Real Estate activity type is required.')
    if relevance not in RELEVANCE_THRESHOLDS:
        raise ValueError('Relevance must be all, possible, or strong.')


def _rank(row, constraints):
    semantic = max(0.0, min(1.0, 1.0 - float(row.search_distance)))
    items = list(row.items.all())
    reasons, bonus, penalty = [], 0.0, 0.0
    haystack = _normalize(' '.join([
        row.summary or '', row.original_message or '',
        *[f'{item.title} {item.location_raw} {item.property_type_label}' for item in items],
    ]))
    overlap = len(constraints.tokens & set(_tokens(haystack))) / max(1, len(constraints.tokens))
    if overlap:
        bonus += min(0.12, overlap * 0.12)
        reasons.append('query terms')
    bonus, penalty = _structured_score(items, constraints, reasons, bonus, penalty)
    row.search_score = round(max(0.0, min(1.0, semantic + bonus - penalty)), 4)
    row.search_relevance = _tier(row.search_score)
    row.search_reasons = reasons or ['semantic similarity']
    row.duplicate_count = 1
    row.duplicate_opportunity_ids = []


def _structured_score(items, constraints, reasons, bonus, penalty):
    if constraints.property_type_ids:
        matched = any(item.property_type_id in constraints.property_type_ids for item in items)
        bonus, penalty = _apply(matched, bonus, penalty, 0.10, 0.06, 'property type', reasons)
    if constraints.bedrooms_min is not None or constraints.bedrooms_max is not None:
        matched = any(_ranges_overlap(
            constraints.bedrooms_min, constraints.bedrooms_max,
            item.bedrooms_min, item.bedrooms_max,
        ) for item in items)
        bonus, penalty = _apply(matched, bonus, penalty, 0.12, 0.10, 'bedrooms', reasons)
    if constraints.amount_min is not None or constraints.amount_max is not None:
        matched = any(_amount_ranges_overlap(
            constraints.amount_min, constraints.amount_max,
            item.amount_min, item.amount_max,
        ) for item in items)
        bonus, penalty = _apply(matched, bonus, penalty, 0.16, 0.10, 'price/budget', reasons)
    locations = {
        _normalize(value) for item in items
        for value in [item.location_raw, *(item.locations or [])] if len(_normalize(value)) >= 4
    }
    if any(location in constraints.normalized for location in locations):
        bonus += 0.14
        reasons.append('location')
    return bonus, penalty


def _apply(matched, bonus, penalty, reward, cost, label, reasons):
    if matched:
        reasons.append(label)
        return bonus + reward, penalty
    return bonus, penalty + cost


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


def _tier(score):
    return 'strong' if score >= 0.55 else ('possible' if score >= 0.35 else 'weak')


def _ranges_overlap(left_min, left_max, right_min, right_max):
    left_min = left_min if left_min is not None else left_max
    left_max = left_max if left_max is not None else left_min
    right_min = right_min if right_min is not None else right_max
    right_max = right_max if right_max is not None else right_min
    return (
        left_min is not None and right_min is not None
        and left_min <= right_max and right_min <= left_max
    )


def _amount_ranges_overlap(left_min, left_max, right_min, right_max):
    left_min = left_min if left_min is not None else left_max
    left_max = left_max if left_max is not None else left_min
    right_min = right_min if right_min is not None else right_max
    right_max = right_max if right_max is not None else right_min
    if left_min is None or right_min is None:
        return False
    tolerance = max(left_max, right_max) * Decimal('0.02')
    return left_min - tolerance <= right_max and right_min - tolerance <= left_max
