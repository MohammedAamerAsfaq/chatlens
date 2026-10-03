from django.contrib import admin

from .models import (
    AccountEndpoint,
    CommunicationAccount,
    Company,
    CompanyContact,
    CompanyContactIdentity,
    CompanyMembership,
    CompanyRole,
    CompanyRolePermission,
    MembershipRoleAssignment,
    PermissionDefinition,
    AuthorizationAuditEvent,
    ConnectionProvider,
    UserCompanyPreference,
)


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ('name', 'company_type', 'industry_type', 'ai_parsing_enabled', 'is_active', 'valid_until')
    search_fields = ('name', 'slug')
    list_filter = ('company_type', 'industry_type', 'ai_parsing_enabled', 'is_active')


@admin.register(CompanyMembership)
class CompanyMembershipAdmin(admin.ModelAdmin):
    list_display = ('company', 'user', 'role', 'is_active', 'joined_at')
    search_fields = ('company__name', 'user__username', 'user__email')
    list_filter = ('role', 'is_active')


@admin.register(UserCompanyPreference)
class UserCompanyPreferenceAdmin(admin.ModelAdmin):
    list_display = ('user', 'company', 'ui_theme', 'updated_at')
    search_fields = ('user__username', 'company__name')
    list_filter = ('ui_theme',)


@admin.register(PermissionDefinition)
class PermissionDefinitionAdmin(admin.ModelAdmin):
    list_display = ('code', 'area', 'supports_scope', 'is_sensitive', 'is_active')
    search_fields = ('code', 'label')
    list_filter = ('area', 'supports_scope', 'is_sensitive', 'is_active')


@admin.register(CompanyRole)
class CompanyRoleAdmin(admin.ModelAdmin):
    list_display = ('name', 'company', 'key', 'is_system_role', 'is_owner_role', 'is_active')
    search_fields = ('name', 'key', 'company__name')
    list_filter = ('is_system_role', 'is_owner_role', 'is_active')


admin.site.register(CompanyRolePermission)
admin.site.register(MembershipRoleAssignment)
admin.site.register(AuthorizationAuditEvent)


@admin.register(ConnectionProvider)
class ConnectionProviderAdmin(admin.ModelAdmin):
    list_display = ('name', 'key', 'channel', 'provider_type', 'is_active', 'is_default_for_channel')
    search_fields = ('name', 'key')
    list_filter = ('channel', 'provider_type', 'is_active', 'is_default_for_channel')


@admin.register(CommunicationAccount)
class CommunicationAccountAdmin(admin.ModelAdmin):
    list_display = ('name', 'company', 'channel', 'provider', 'is_active')
    search_fields = ('name', 'company__name', 'external_account_id')
    list_filter = ('channel', 'is_active', 'provider')


@admin.register(AccountEndpoint)
class AccountEndpointAdmin(admin.ModelAdmin):
    list_display = ('value', 'endpoint_type', 'communication_account', 'is_primary', 'is_active')
    search_fields = ('value', 'communication_account__name', 'communication_account__company__name')
    list_filter = ('endpoint_type', 'is_primary', 'is_active')


class CompanyContactIdentityInline(admin.TabularInline):
    model = CompanyContactIdentity
    extra = 0
    exclude = ('company', 'normalized_value', 'source_reference')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(CompanyContact)
class CompanyContactAdmin(admin.ModelAdmin):
    list_display = ('display_name', 'company', 'contact_type', 'category', 'is_active')
    search_fields = ('display_name', 'legal_name', 'company__name')
    list_filter = ('contact_type', 'category', 'is_active')
    inlines = [CompanyContactIdentityInline]
