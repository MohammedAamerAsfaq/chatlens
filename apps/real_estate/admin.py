from django.contrib import admin

from apps.real_estate.models import (
    Listing,
    ListingEmbedding,
    Property,
    Party,
    PropertyPartyAssociation,
    PropertyType,
    PropertyTypeFieldDefinition,
    PropertyAddress,
    PropertyDevelopment,
    PropertyEmbedding,
    OpportunityItem, PropertyCandidate,
    CandidateEmbedding,
    PropertyMedia,
    PropertyRequirement,
    RequirementEmbedding,
    RealEstateAgentCallLog,
    RealEstateMockSourceRecord,
    RealEstateOpportunity,
    RealEstateParseLog,
    RealEstatePromptConfig,
    RealEstateSettings,
)


@admin.register(PropertyType)
class PropertyTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'company', 'category', 'sort_order', 'is_active')
    list_filter = ('company', 'category', 'is_active')
    search_fields = ('name', 'code', 'description')


@admin.register(PropertyTypeFieldDefinition)
class PropertyTypeFieldDefinitionAdmin(admin.ModelAdmin):
    list_display = ('property_type', 'code', 'label', 'data_type', 'company', 'is_active')
    list_filter = ('company', 'data_type', 'is_active')
    search_fields = ('property_type__name', 'code', 'label')


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'company', 'title', 'property_type', 'inventory_source_type',
        'is_tracked', 'availability_status', 'is_archived', 'updated_at',
    )
    list_filter = (
        'company', 'property_type', 'inventory_source_type', 'is_tracked',
        'availability_status', 'is_archived',
    )
    search_fields = ('title', 'reference_code', 'project_name', 'developer')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Party)
class PartyAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'display_name', 'party_kind', 'phone', 'email', 'is_active')
    list_filter = ('company', 'party_kind', 'is_active')
    search_fields = ('first_name', 'middle_name', 'last_name', 'organization_name', 'phone', 'email')


@admin.register(PropertyPartyAssociation)
class PropertyPartyAssociationAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'property', 'party', 'relationship_type', 'is_active')
    list_filter = ('company', 'relationship_type', 'is_active')
    search_fields = ('property__title', 'party__first_name', 'party__last_name', 'party__organization_name')


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'property', 'listing_type', 'asking_price', 'currency', 'status', 'is_verified')
    list_filter = ('company', 'listing_type', 'status', 'is_verified', 'is_archived')
    search_fields = ('property__title', 'property__reference_code')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(PropertyRequirement)
class PropertyRequirementAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'opportunity', 'budget_min', 'budget_max', 'currency', 'review_status')
    list_filter = ('company', 'review_status', 'currency')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(PropertyCandidate)
class PropertyCandidateAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'title', 'property_type', 'asking_price', 'review_status', 'updated_at')
    list_filter = ('company', 'property_type', 'review_status')
    search_fields = ('title', 'location_raw', 'description')
    readonly_fields = ('created_at', 'updated_at', 'reviewed_at')


admin.site.register(PropertyAddress)


@admin.register(PropertyDevelopment)
class PropertyDevelopmentAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'development_type', 'company', 'locality', 'parent',
        'is_verified', 'is_active',
    )
    list_filter = ('company', 'development_type', 'is_verified', 'is_active')
    search_fields = ('name', 'developer_name')
admin.site.register(PropertyMedia)


@admin.register(RealEstateOpportunity)
class RealEstateOpportunityAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'company', 'activity_type', 'classification_status', 'status',
        'assigned_to', 'first_seen_at',
    )
    list_filter = ('company', 'activity_type', 'classification_status', 'status')
    search_fields = ('summary', 'original_message', 'deduplication_key')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(OpportunityItem)
class OpportunityItemAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'company', 'opportunity', 'item_kind', 'property_type',
        'match_status', 'property', 'updated_at',
    )
    list_filter = ('company', 'item_kind', 'match_status', 'link_method')
    search_fields = ('title', 'location_raw', 'opportunity__summary')
    readonly_fields = ('created_at', 'updated_at', 'linked_at')


@admin.register(RealEstatePromptConfig)
class RealEstatePromptConfigAdmin(admin.ModelAdmin):
    list_display = ('company', 'key', 'label', 'agent_config', 'kiwi_router', 'updated_at')
    list_filter = ('company', 'key')


admin.site.register(RealEstateSettings)


@admin.register(RealEstateParseLog)
class RealEstateParseLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'message', 'status', 'gate_decision', 'updated_at')
    list_filter = ('company', 'status', 'gate_mode', 'gate_decision')
    search_fields = ('message__message_text', 'error')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(RealEstateAgentCallLog)
class RealEstateAgentCallLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'purpose', 'provider', 'model', 'success', 'duration_ms', 'created_at')
    list_filter = ('company', 'purpose', 'provider', 'success')
    readonly_fields = ('created_at',)


class RealEstateEmbeddingAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'status', 'embedding_model', 'updated_at')
    list_filter = ('company', 'status', 'embedding_model')
    readonly_fields = ('embedding', 'metadata', 'created_at', 'updated_at')


admin.site.register(PropertyEmbedding, RealEstateEmbeddingAdmin)
admin.site.register(ListingEmbedding, RealEstateEmbeddingAdmin)
admin.site.register(RequirementEmbedding, RealEstateEmbeddingAdmin)
admin.site.register(CandidateEmbedding, RealEstateEmbeddingAdmin)


@admin.register(RealEstateMockSourceRecord)
class RealEstateMockSourceRecordAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'company', 'source_file_name', 'source_sheet_name',
        'source_row_number', 'row_kind', 'processing_status', 'imported_at',
    )
    list_filter = ('company', 'row_kind', 'processing_status', 'source_file_name')
    search_fields = ('source_file_name', 'source_sheet_name', 'processing_notes')
    readonly_fields = (
        'company', 'import_run_id', 'source_file_name', 'source_file_checksum',
        'source_sheet_name', 'source_sheet_index', 'source_row_number', 'row_kind',
        'raw_values', 'display_values', 'row_checksum', 'imported_at',
    )
