from django.contrib import admin
from .models import MessageEmbedding, MessageAnalysis


@admin.register(MessageEmbedding)
class MessageEmbeddingAdmin(admin.ModelAdmin):
    list_display = ['message', 'embedding_model', 'created_at']
    list_filter = ['embedding_model']


@admin.register(MessageAnalysis)
class MessageAnalysisAdmin(admin.ModelAdmin):
    list_display = ['message', 'intent', 'sentiment', 'urgency_score', 'lead_score', 'created_at']
    list_filter = ['intent', 'sentiment', 'language']
    search_fields = ['message__message_text']
