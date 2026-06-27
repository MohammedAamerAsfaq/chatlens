from django.contrib import admin
from .models import AIProviderConfig


@admin.register(AIProviderConfig)
class AIProviderConfigAdmin(admin.ModelAdmin):
    list_display = ['display_name', 'provider', 'capability', 'model', 'is_active', 'updated_at']
    list_filter = ['provider', 'capability', 'is_active']
    readonly_fields = ['created_at', 'updated_at']
