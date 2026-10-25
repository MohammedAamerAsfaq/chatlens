from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.real_estate.models import (
    ActivityType, AreaUnit, InquiryMedium, MarketScope, OwnershipEligibility,
    Property, RealEstateOpportunity, TenureType,
)


class ManualOpportunityItemSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255)
    property_type = serializers.CharField(max_length=100)
    locations = serializers.ListField(
        child=serializers.CharField(max_length=255), required=False, default=list,
    )
    reference_code = serializers.CharField(max_length=100, required=False, allow_blank=True)
    bedrooms_min = serializers.DecimalField(max_digits=5, decimal_places=1, required=False, allow_null=True)
    bedrooms_max = serializers.DecimalField(max_digits=5, decimal_places=1, required=False, allow_null=True)
    bathrooms_min = serializers.DecimalField(max_digits=5, decimal_places=1, required=False, allow_null=True)
    bathrooms_max = serializers.DecimalField(max_digits=5, decimal_places=1, required=False, allow_null=True)
    area_min = serializers.DecimalField(max_digits=14, decimal_places=2, required=False, allow_null=True)
    area_max = serializers.DecimalField(max_digits=14, decimal_places=2, required=False, allow_null=True)
    area_unit = serializers.ChoiceField(choices=AreaUnit.choices, default=AreaUnit.SQUARE_FEET)
    amount_min = serializers.DecimalField(max_digits=16, decimal_places=2, required=False, allow_null=True)
    amount_max = serializers.DecimalField(max_digits=16, decimal_places=2, required=False, allow_null=True)
    currency = serializers.CharField(max_length=3, default='AED')
    furnishing = serializers.ChoiceField(choices=Property.FURNISHING_CHOICES, default='unknown')
    ownership_eligibility = serializers.ChoiceField(
        choices=OwnershipEligibility.choices, default=OwnershipEligibility.ALL,
    )
    tenure_type = serializers.ChoiceField(
        choices=[('', 'Not specified'), *TenureType.choices], required=False, allow_blank=True,
    )
    timeframe = serializers.CharField(max_length=255, required=False, allow_blank=True)
    required_amenities = serializers.ListField(
        child=serializers.CharField(max_length=100), required=False, default=list,
    )
    preferred_amenities = serializers.ListField(
        child=serializers.CharField(max_length=100), required=False, default=list,
    )
    free_form_constraints = serializers.CharField(required=False, allow_blank=True)
    description = serializers.CharField(required=False, allow_blank=True)
    available_from = serializers.DateField(required=False, allow_null=True)
    attributes = serializers.DictField(required=False, default=dict)


class ManualOpportunitySerializer(serializers.Serializer):
    activity_type = serializers.ChoiceField(choices=ActivityType.choices)
    inquiry_medium = serializers.PrimaryKeyRelatedField(queryset=InquiryMedium.objects.none())
    source_party_name = serializers.CharField(max_length=255)
    source_contact_detail = serializers.CharField(max_length=255, required=False, allow_blank=True)
    source_reference = serializers.CharField(max_length=255, required=False, allow_blank=True)
    received_at = serializers.DateTimeField(required=False, allow_null=True)
    market_scope = serializers.ChoiceField(choices=MarketScope.choices, default=MarketScope.LOCAL)
    status = serializers.ChoiceField(choices=RealEstateOpportunity.STATUS_CHOICES, default='new')
    assigned_to = serializers.PrimaryKeyRelatedField(
        queryset=get_user_model().objects.none(), required=False, allow_null=True,
    )
    summary = serializers.CharField()
    original_message = serializers.CharField(required=False, allow_blank=True)
    items = ManualOpportunityItemSerializer(many=True, allow_empty=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        company = self.context.get('company')
        if not company:
            return
        self.fields['inquiry_medium'].queryset = InquiryMedium.objects.filter(
            company=company, is_active=True,
        )
        self.fields['assigned_to'].queryset = get_user_model().objects.filter(
            company_memberships__company=company,
            company_memberships__is_active=True,
        ).distinct()

    def validate_items(self, items):
        activity = self.initial_data.get('activity_type')
        amount_key = 'budget' if activity in ActivityType.requirement_values() else 'price'
        normalized = []
        for item in items:
            item = dict(item)
            for low, high in (
                ('bedrooms_min', 'bedrooms_max'), ('bathrooms_min', 'bathrooms_max'),
                ('area_min', 'area_max'), ('amount_min', 'amount_max'),
            ):
                if item.get(low) is not None and item.get(high) is not None and item[low] > item[high]:
                    raise serializers.ValidationError({high: f'Must be greater than or equal to {low}.'})
            minimum = item.pop('amount_min', None)
            maximum = item.pop('amount_max', None)
            if minimum is not None or maximum is not None:
                item[amount_key] = {
                    'min': minimum,
                    'max': maximum,
                    'amount': minimum,
                    'currency': item.get('currency', 'AED'),
                }
            normalized.append(item)
        return normalized
