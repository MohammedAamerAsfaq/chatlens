"""Explainable structured scoring for Real Estate opportunity search."""

from decimal import Decimal

from apps.real_estate.services.opportunity_search_query import normalize, tokens
from apps.real_estate.services.opportunity_search_attributes import score_attribute_constraints


def rank_opportunity(row, constraints):
    semantic = max(0.0, min(1.0, 1.0 - float(row.search_distance)))
    items = list(row.items.all())
    reasons, adjustments, bonus, penalty = [], [], 0.0, 0.0
    haystack = normalize(' '.join([
        row.summary or '', row.original_message or '',
        *[f'{item.title} {item.location_raw} {item.property_type_label}' for item in items],
    ]))
    overlap = len(constraints.tokens & set(tokens(haystack))) / max(1, len(constraints.tokens))
    if overlap:
        bonus += min(0.12, overlap * 0.12)
        reasons.append('query terms')
    bonus, penalty, excluded = _structured_score(
        items, constraints, reasons, adjustments, bonus, penalty,
    )
    row.search_score = round(max(0.0, min(1.0, semantic + bonus - penalty)), 4)
    row.search_relevance = _tier(row.search_score)
    row.search_reasons = reasons or ['semantic similarity']
    row.search_penalty = round(penalty, 4)
    row.search_adjustments = adjustments
    row.search_excluded = excluded
    row.duplicate_count = 1
    row.duplicate_opportunity_ids = []


def _structured_score(items, constraints, reasons, adjustments, bonus, penalty):
    excluded = False
    if constraints.property_type_ids:
        known = {item.property_type_id for item in items if item.property_type_id}
        if known & set(constraints.property_type_ids):
            bonus += 0.10
            reasons.append('property type')
        elif known & set(constraints.related_property_type_ids):
            penalty = _penalize(penalty, adjustments, 0.03, 'Related property type')
        elif known:
            excluded = True
        else:
            penalty = _penalize(penalty, adjustments, 0.06, 'Property type unavailable')
    bedroom_result = _score_bedrooms(items, constraints, reasons, adjustments, penalty)
    penalty, bedroom_excluded = bedroom_result
    excluded = excluded or bedroom_excluded
    bonus, penalty = _score_amount(items, constraints, reasons, adjustments, bonus, penalty)
    location_bonus, location_penalty, location_excluded = _score_location(
        items, constraints, reasons, adjustments,
    )
    attribute_bonus, attribute_penalty = score_attribute_constraints(
        items, constraints.attributes, reasons, adjustments,
    )
    return (
        bonus + location_bonus + attribute_bonus,
        penalty + location_penalty + attribute_penalty,
        excluded or location_excluded,
    )


def _score_bedrooms(items, constraints, reasons, adjustments, penalty):
    if constraints.bedrooms_min is None and constraints.bedrooms_max is None:
        return penalty, False
    ranges = _ranges(items, 'bedrooms')
    if any(_overlap(
        constraints.bedrooms_min, constraints.bedrooms_max, low, high,
    ) for low, high in ranges):
        reasons.append('bedrooms')
        return penalty, False
    if not ranges:
        return _penalize(penalty, adjustments, 0.08, 'Bedroom count unavailable'), False
    gap = min(_range_gap(
        constraints.bedrooms_min, constraints.bedrooms_max, low, high,
    ) for low, high in ranges)
    if gap <= Decimal('1'):
        return _penalize(penalty, adjustments, 0.06, 'Nearest bedroom count'), False
    return penalty, True


def _score_amount(items, constraints, reasons, adjustments, bonus, penalty):
    if constraints.amount_min is None and constraints.amount_max is None:
        return bonus, penalty
    ranges = _ranges(items, 'amount')
    matched = any(_amount_overlap(
        constraints.amount_min, constraints.amount_max, low, high,
    ) for low, high in ranges)
    if matched:
        reasons.append('price/budget')
        return bonus + 0.16, penalty
    label = 'Price/budget unavailable' if not ranges else 'Price/budget outside range'
    return bonus, _penalize(penalty, adjustments, 0.10, label)


def _score_location(items, constraints, reasons, adjustments):
    if not constraints.locations:
        return 0, 0, False
    values = {
        normalize(value) for item in items
        for value in [item.location_raw, *(item.locations or [])] if normalize(value)
    }
    requested = {term for location in constraints.locations for term in location.get('terms', ())}
    if any(left == right or left in right or right in left for left in values for right in requested):
        reasons.append('location')
        return 0.14, 0, False
    if values:
        return 0, 0, True
    return 0, _penalize(0, adjustments, 0.08, 'Location unavailable'), False


def _ranges(items, prefix):
    return [
        (getattr(item, f'{prefix}_min'), getattr(item, f'{prefix}_max')) for item in items
        if getattr(item, f'{prefix}_min') is not None or getattr(item, f'{prefix}_max') is not None
    ]


def _penalize(total, adjustments, amount, reason):
    adjustments.append({'reason': reason, 'penalty': amount})
    return total + amount


def _range_gap(left_min, left_max, right_min, right_max):
    left_min, left_max = _bounds(left_min, left_max)
    right_min, right_max = _bounds(right_min, right_max)
    if left_max < right_min:
        return right_min - left_max
    if right_max < left_min:
        return left_min - right_max
    return Decimal('0')


def _overlap(left_min, left_max, right_min, right_max):
    left_min, left_max = _bounds(left_min, left_max)
    right_min, right_max = _bounds(right_min, right_max)
    return left_min is not None and right_min is not None and left_min <= right_max and right_min <= left_max


def _amount_overlap(left_min, left_max, right_min, right_max):
    left_min, left_max = _bounds(left_min, left_max)
    right_min, right_max = _bounds(right_min, right_max)
    if left_min is None or right_min is None:
        return False
    tolerance = max(left_max, right_max) * Decimal('0.02')
    return left_min - tolerance <= right_max and right_min - tolerance <= left_max


def _bounds(minimum, maximum):
    return minimum if minimum is not None else maximum, maximum if maximum is not None else minimum


def _tier(score):
    return 'strong' if score >= 0.55 else ('possible' if score >= 0.35 else 'weak')
