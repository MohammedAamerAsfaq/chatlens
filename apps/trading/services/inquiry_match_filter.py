"""Filter inquiries by how their product lines matched the inventory catalog.

Each Inquiry.products line carries the AI's match verdict: product_id plus match_type
"exact" or "near". A line counts as exact exactly when the Trading board renders it as an
exact match: a linked product that is not flagged "near". That includes lines a human
corrected or entered by hand, and older lines stored before match_type existed.

An inquiry qualifies for a filter when at least one of its lines does, so an inquiry with
both an exact and a near line appears under both. Unmatched lines never qualify.
"""

from django.db.models import BooleanField
from django.db.models.expressions import RawSQL

from apps.trading.models import Inquiry


MATCH_FILTER_ALL = 'all'
MATCH_FILTER_EXACT = 'exact'
MATCH_FILTER_NEAR = 'near'
MATCH_FILTERS = (MATCH_FILTER_ALL, MATCH_FILTER_EXACT, MATCH_FILTER_NEAR)

_LINE_CONDITIONS = {
    MATCH_FILTER_EXACT: "COALESCE(line->>'match_type', '') <> 'near'",
    MATCH_FILTER_NEAR: "line->>'match_type' = 'near'",
}


def filter_inquiries_by_match(queryset, match_filter):
    """Narrow an Inquiry queryset to the given match filter; 'all' leaves it unchanged."""
    if match_filter not in MATCH_FILTERS:
        raise ValueError(f'Unsupported match filter: {match_filter}')
    if match_filter == MATCH_FILTER_ALL:
        return queryset
    products = f'"{Inquiry._meta.db_table}"."products"'
    sql = (
        'EXISTS (SELECT 1 FROM jsonb_array_elements('
        f"CASE WHEN jsonb_typeof({products}) = 'array' THEN {products} ELSE '[]'::jsonb END"
        ") AS line WHERE line->>'product_id' IS NOT NULL AND "
        f'{_LINE_CONDITIONS[match_filter]})'
    )
    return queryset.annotate(
        has_match_filter_line=RawSQL(sql, [], output_field=BooleanField()),
    ).filter(has_match_filter_line=True)
