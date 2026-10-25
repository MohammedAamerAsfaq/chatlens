from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.real_estate.models import ClassificationStatus, RealEstateOpportunity
from apps.real_estate.services.extraction_projection import project_extraction


@transaction.atomic
def create_manual_opportunity(*, company, user, validated_data):
    items = _json_safe(validated_data.pop('items'))
    opportunity = RealEstateOpportunity(
        company=company,
        classification_status=ClassificationStatus.CLASSIFIED,
        confidence=1,
        matching_complete=False,
        assigned_to=validated_data.pop('assigned_to', None) or user,
        first_seen_at=validated_data.pop('received_at', None) or timezone.now(),
        **validated_data,
    )
    opportunity.full_clean()
    opportunity.save()
    project_extraction(opportunity, {
        'summary': opportunity.summary,
        'confidence': 1,
        'properties': items,
    })
    return opportunity


def _json_safe(value):
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, Decimal):
        return str(value)
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    return value
