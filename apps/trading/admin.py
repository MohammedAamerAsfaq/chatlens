from django.contrib import admin

from apps.trading.models import InquiryProduct


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
