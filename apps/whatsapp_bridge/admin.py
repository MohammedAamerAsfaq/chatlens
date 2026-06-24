from django.contrib import admin
from .models import WhatsAppAccount, WhatsAppContact, WhatsAppChat, WhatsAppMessage, SyncLog


@admin.register(WhatsAppAccount)
class WhatsAppAccountAdmin(admin.ModelAdmin):
    list_display = ['display_name', 'phone_number', 'session_status', 'owner', 'is_active', 'created_at']
    list_filter = ['session_status', 'is_active']
    search_fields = ['display_name', 'phone_number', 'worker_session_id']


@admin.register(WhatsAppContact)
class WhatsAppContactAdmin(admin.ModelAdmin):
    list_display = ['display_name', 'phone_number', 'account', 'is_business', 'created_at']
    list_filter = ['is_business']
    search_fields = ['display_name', 'phone_number', 'wa_contact_id']


@admin.register(WhatsAppChat)
class WhatsAppChatAdmin(admin.ModelAdmin):
    list_display = ['name', 'chat_type', 'account', 'last_message_at', 'unread_count']
    list_filter = ['chat_type', 'is_archived']
    search_fields = ['name', 'wa_chat_id']


@admin.register(WhatsAppMessage)
class WhatsAppMessageAdmin(admin.ModelAdmin):
    list_display = ['message_time', 'direction', 'message_type', 'sender_number', 'account']
    list_filter = ['direction', 'message_type', 'has_media']
    search_fields = ['message_text', 'sender_number', 'provider_message_id']
    date_hierarchy = 'message_time'


@admin.register(SyncLog)
class SyncLogAdmin(admin.ModelAdmin):
    list_display = ['event_type', 'status', 'account', 'created_at']
    list_filter = ['event_type', 'status']
