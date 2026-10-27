from decimal import Decimal

from django.db import transaction
from django.utils import timezone


@transaction.atomic
def create_manual_inquiry(*, company, validated_data):
    from apps.trading.models import Inquiry, InquiryStatus

    items = _json_safe(validated_data.pop('items'))
    return Inquiry.objects.create(
        company=company,
        account=validated_data['account'],
        contact=validated_data.get('contact'),
        inquiry_type=validated_data['inquiry_type'],
        status=validated_data.get('status') or InquiryStatus.OPEN,
        products=items,
        summary=validated_data['summary'],
        remarks=validated_data.get('remarks', ''),
        dedup_key='',
        source_type='direct',
        first_seen_at=validated_data.get('received_at') or timezone.now(),
        classification_version='v1',
        product_match_status=Inquiry.CLASSIFICATION_MATCH_NOT_REQUIRED,
    )


def _json_safe(value):
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, Decimal):
        return float(value)
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    return value
