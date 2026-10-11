from rest_framework import serializers

from apps.real_estate.models import PropertyCandidate, PropertyRequirement, RealEstateOpportunity
from .base import CleanModelSerializer


class OpportunitySerializer(CleanModelSerializer):
    class Meta:
        model = RealEstateOpportunity
        exclude = ('company',)
        read_only_fields = (
            'source_message', 'account', 'contact', 'company_contact', 'source_chat',
            'activity_type', 'classification_status', 'summary', 'original_message',
            'confidence', 'matching_complete', 'deduplication_key', 'first_seen_at',
            'created_at', 'updated_at',
        )


class PropertyRequirementSerializer(CleanModelSerializer):
    activity_type = serializers.CharField(source='opportunity.activity_type', read_only=True)

    class Meta:
        model = PropertyRequirement
        exclude = ('company',)
        read_only_fields = ('raw_extraction', 'extraction_confidence', 'created_at', 'updated_at')


class PropertyCandidateSerializer(CleanModelSerializer):
    activity_type = serializers.CharField(source='opportunity.activity_type', read_only=True)

    class Meta:
        model = PropertyCandidate
        exclude = ('company',)
        read_only_fields = (
            'opportunity', 'raw_extraction', 'review_status', 'promoted_property',
            'promoted_listing', 'reviewed_by', 'reviewed_at', 'created_at', 'updated_at',
        )
