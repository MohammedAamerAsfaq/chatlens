from django.contrib import admin

from apps.clientpulse.models import (
    ClientActivity, ClientNote, ClientProfile, ClientPulseSettings,
    ClientReminder, ClientReminderNotification, ClientTag, ClientTagAssignment,
    ContactConsent, ContactMergeCandidate,
)


@admin.register(ContactMergeCandidate)
class ContactMergeCandidateAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'company', 'left_contact', 'right_contact', 'status', 'confidence', 'created_at',
    )
    list_filter = ('company', 'status')
    search_fields = (
        'left_contact__display_name', 'right_contact__display_name', 'company__name',
    )
    readonly_fields = ('created_at', 'updated_at')


@admin.register(ClientProfile)
class ClientProfileAdmin(admin.ModelAdmin):
    list_display = ('contact', 'company', 'lifecycle_stage', 'owner', 'priority', 'status')
    list_filter = ('company', 'lifecycle_stage', 'priority', 'status')
    search_fields = ('contact__display_name', 'contact__legal_name')


admin.site.register(ClientTag)
admin.site.register(ClientTagAssignment)
admin.site.register(ClientNote)
admin.site.register(ContactConsent)
admin.site.register(ClientPulseSettings)


@admin.register(ClientReminder)
class ClientReminderAdmin(admin.ModelAdmin):
    list_display = ('title', 'company', 'profile', 'assigned_to', 'due_at', 'status', 'priority')
    list_filter = ('company', 'status', 'priority', 'recurrence_type')
    search_fields = ('title', 'profile__contact__display_name')


@admin.register(ClientReminderNotification)
class ClientReminderNotificationAdmin(admin.ModelAdmin):
    list_display = ('reminder', 'recipient', 'delivered_at', 'read_at', 'dismissed_at')
    list_filter = ('company',)


@admin.register(ClientActivity)
class ClientActivityAdmin(admin.ModelAdmin):
    list_display = ('title', 'company', 'profile', 'activity_type', 'occurred_at')
    list_filter = ('company', 'activity_type')
    readonly_fields = [field.name for field in ClientActivity._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
