from django.contrib import admin

from apps.real_estate.models import (
    Listing,
    Property,
    PropertyAddress,
    PropertyCandidate,
    PropertyMedia,
    PropertyRequirement,
    RealEstateAgentCallLog,
    RealEstateOpportunity,
    RealEstateParseLog,
    RealEstatePromptConfig,
    RealEstateSettings,
)


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'title', 'property_type', 'availability_status', 'is_archived', 'updated_at')
    list_filter = ('company', 'property_type', 'availability_status', 'is_archived')
    search_fields = ('title', 'reference_code', 'project_name', 'developer')
    readonly_fields = ('created_at', 'updated_at')


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
