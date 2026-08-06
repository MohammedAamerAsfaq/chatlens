from django.contrib import admin

from apps.trading.models import InquiryProduct, NonInventoryProduct, NonInventoryProductMention


@admin.register(InquiryProduct)
class InquiryProductAdmin(admin.ModelAdmin):
    list_display = [
        'canonical_name',
        'inquiry_type',
        'decision_status',
        'match_status',
        'match_source',
        'product',
        'contact',
        'account',
        'first_seen_at',
    ]
    list_filter = [
        'company',
        'inquiry_type',
        'decision_status',
        'match_status',
        'match_source',
        'embedding_status',
    ]
    search_fields = [
        'canonical_name',
        'normalized_name',
        'original_text',
        'match_reason',
        'contact__display_name',
        'contact__phone_number',
        'product__name',
    ]
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = [
        'company',
        'inquiry',
        'source_message',
        'account',
        'contact',
        'company_contact',
        'product',
    ]


@admin.register(NonInventoryProduct)
class NonInventoryProductAdmin(admin.ModelAdmin):
    list_display = [
        'canonical_name',
        'brand',
        'status',
        'mention_count',
        'buy_mention_count',
        'sell_mention_count',
        'promoted_product',
        'last_seen_at',
    ]
    list_filter = [
        'company',
        'status',
        'brand',
        'embedding_status',
    ]
    search_fields = [
        'canonical_name',
        'normalized_name',
        'normalized_key',
        'brand',
        'embedding_error',
    ]
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = [
        'company',
        'promoted_product',
        'merged_into',
    ]


@admin.register(NonInventoryProductMention)
class NonInventoryProductMentionAdmin(admin.ModelAdmin):
    list_display = [
        'canonical_name_from_ai',
        'inquiry_type',
        'non_inventory_product',
        'match_source',
        'match_confidence',
        'account',
        'contact',
        'message_time',
    ]
    list_filter = [
        'company',
        'inquiry_type',
        'match_source',
    ]
    search_fields = [
        'canonical_name_from_ai',
        'normalized_name_from_ai',
        'raw_text',
        'brand_from_ai',
        'match_reason',
        'contact__display_name',
        'contact__phone_number',
    ]
    readonly_fields = ['created_at']
    raw_id_fields = [
        'company',
        'non_inventory_product',
        'inquiry',
        'inquiry_product',
        'source_message',
        'account',
        'contact',
        'company_contact',
    ]
