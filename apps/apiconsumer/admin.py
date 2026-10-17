from django.contrib import admin

from .models import ApiKey, ApiKeyUsageLog, WebhookDeliveryAttempt, WebhookSubscription


@admin.register(ApiKey)
class ApiKeyAdmin(admin.ModelAdmin):
    list_display = ('name', 'key_prefix', 'company', 'status', 'scopes', 'last_used_at', 'created_at')
    list_filter = ('status', 'company')
    search_fields = ('name', 'key_prefix')
    readonly_fields = ('secret_hash', 'key_prefix', 'created_at', 'last_used_at', 'revoked_at')


@admin.register(ApiKeyUsageLog)
class ApiKeyUsageLogAdmin(admin.ModelAdmin):
    list_display = ('company', 'api_key', 'method', 'path', 'status_code', 'created_at')
    list_filter = ('company', 'method', 'status_code')


@admin.register(WebhookSubscription)
class WebhookSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('company', 'target_url', 'event_types', 'is_active', 'created_at')
    list_filter = ('company', 'is_active')
    readonly_fields = ('secret',)


@admin.register(WebhookDeliveryAttempt)
class WebhookDeliveryAttemptAdmin(admin.ModelAdmin):
    list_display = ('subscription', 'event_type', 'attempt_number', 'response_status', 'succeeded', 'created_at')
    list_filter = ('succeeded', 'event_type')
