from rest_framework import serializers

from apps.real_estate.models import (
    OpportunityItem, PropertyCandidate, PropertyRequirement, RealEstateOpportunity,
)
from .base import CleanModelSerializer, CompanyPropertyTypeField


class PropertyRequirementSerializer(CleanModelSerializer):
    activity_type = serializers.CharField(source='opportunity.activity_type', read_only=True)

    class Meta:
        model = PropertyRequirement
        exclude = ('company',)
        read_only_fields = ('raw_extraction', 'extraction_confidence', 'created_at', 'updated_at')


class PropertyCandidateSerializer(CleanModelSerializer):
    activity_type = serializers.CharField(source='opportunity.activity_type', read_only=True)
    property_type = CompanyPropertyTypeField(required=False, allow_null=True)
    property_type_name = serializers.CharField(source='property_type.name', read_only=True)

    class Meta:
        model = PropertyCandidate
        exclude = ('company',)
        read_only_fields = (
            'opportunity', 'raw_extraction', 'review_status', 'promoted_property',
            'promoted_listing', 'reviewed_by', 'reviewed_at', 'created_at', 'updated_at',
        )


class OpportunityItemSerializer(CleanModelSerializer):
    property_type = CompanyPropertyTypeField(required=False, allow_null=True)
    property_type_name = serializers.CharField(source='property_type.name', read_only=True)
    property_title = serializers.CharField(source='property.title', read_only=True)
    linked_by_name = serializers.SerializerMethodField()

    @staticmethod
    def get_linked_by_name(obj):
        if not obj.linked_by:
            return ''
        return obj.linked_by.get_full_name() or obj.linked_by.get_username()

    class Meta:
        model = OpportunityItem
        exclude = ('company',)
        read_only_fields = (
            'opportunity', 'sequence', 'item_kind', 'raw_extraction',
            'property', 'match_status', 'match_confidence', 'link_method',
            'linked_by', 'linked_at', 'legacy_requirement', 'legacy_candidate',
            'created_at', 'updated_at',
        )


class OpportunitySerializer(CleanModelSerializer):
    items = OpportunityItemSerializer(many=True, read_only=True)
    requirement = PropertyRequirementSerializer(read_only=True)
    property_candidate = PropertyCandidateSerializer(read_only=True)
    contact_name = serializers.SerializerMethodField()
    contact_phone = serializers.SerializerMethodField()
    account_name = serializers.CharField(source='account.display_name', read_only=True)
    inquiry_medium_name = serializers.CharField(source='inquiry_medium.name', read_only=True)
    source_chat_name = serializers.CharField(source='source_chat.name', read_only=True)
    assigned_to_name = serializers.SerializerMethodField()
    # Needed (alongside the already-present source_chat/source_message FK ids) to deep-link
    # into the original WhatsApp message the same way the Trading inquiries board does -
    # selectChat() uses this to load the right page of messages around the target one.
    source_message_time = serializers.SerializerMethodField()
    search_score = serializers.SerializerMethodField()

    @staticmethod
    def get_contact_name(obj):
        contact = obj.contact
        if not contact:
            return obj.source_party_name
        return contact.display_name or contact.push_name or contact.phone_number or contact.wa_contact_id

    @staticmethod
    def get_contact_phone(obj):
        return obj.contact.phone_number if obj.contact else obj.source_contact_detail

    @staticmethod
    def get_assigned_to_name(obj):
        if not obj.assigned_to:
            return ''
        return obj.assigned_to.get_full_name() or obj.assigned_to.get_username()

    @staticmethod
    def get_source_message_time(obj):
        return obj.source_message.message_time.isoformat() if obj.source_message_id else None

    @staticmethod
    def get_search_score(obj):
        distance = getattr(obj, 'search_distance', None)
        if distance is None:
            return None
        return round(max(0.0, min(1.0, 1.0 - float(distance))), 4)

    class Meta:
        model = RealEstateOpportunity
        exclude = ('company',)
        read_only_fields = (
            'source_message', 'account', 'contact', 'company_contact', 'source_chat',
            'inquiry_medium', 'source_party_name', 'source_contact_detail', 'source_reference',
            'activity_type', 'classification_status', 'summary', 'original_message',
            'confidence', 'matching_complete', 'deduplication_key', 'first_seen_at',
            'created_at', 'updated_at',
        )
