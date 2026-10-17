from rest_framework import serializers

from apps.trading.models import Inquiry, Product
from apps.whatsapp_bridge.models import OutboundMessage, WhatsAppChat, WhatsAppContact, WhatsAppMessage

from .models import WebhookDeliveryAttempt, WebhookSubscription


class ContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = WhatsAppContact
        fields = [
            'id', 'display_name', 'push_name', 'phone_number', 'is_business',
            'category', 'created_at', 'updated_at',
        ]


class ChatSerializer(serializers.ModelSerializer):
    class Meta:
        model = WhatsAppChat
        fields = ['id', 'wa_chat_id', 'chat_type', 'name', 'last_message_at', 'unread_count', 'is_archived']


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = WhatsAppMessage
        fields = [
            'id', 'chat', 'provider_message_id', 'sender_number', 'direction',
            'message_type', 'message_text', 'message_time', 'has_media',
        ]


class OutboundMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = OutboundMessage
        fields = [
            'id', 'destination_jid', 'status', 'status_reason', 'content_type',
            'provider_message_id', 'idempotency_key', 'requested_at', 'delivered_at',
            'read_at', 'finished_at',
        ]


class InquirySerializer(serializers.ModelSerializer):
    class Meta:
        model = Inquiry
        fields = [
            'id', 'contact', 'inquiry_type', 'status', 'products', 'summary', 'remarks',
            'source_type', 'first_seen_at', 'closed_at', 'created_at', 'updated_at',
        ]


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = [
            'id', 'name', 'brand', 'category', 'sku', 'is_active', 'tracking',
            'qty', 'sale_price', 'currency', 'created_at', 'updated_at',
        ]


class SendMessageSerializer(serializers.Serializer):
    whatsapp_account_id = serializers.IntegerField()
    destination_jid = serializers.CharField(max_length=255)
    text = serializers.CharField(max_length=10000, allow_blank=True, required=False, default='')
    idempotency_key = serializers.CharField(max_length=255, required=False, allow_null=True)
    confirm_new_chat = serializers.BooleanField(required=False, default=False)


class WebhookSubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = WebhookSubscription
        fields = ['id', 'target_url', 'event_types', 'is_active', 'created_at', 'updated_at']


class WebhookSubscriptionCreatedSerializer(WebhookSubscriptionSerializer):
    class Meta(WebhookSubscriptionSerializer.Meta):
        fields = WebhookSubscriptionSerializer.Meta.fields + ['secret']


class WebhookDeliveryAttemptSerializer(serializers.ModelSerializer):
    class Meta:
        model = WebhookDeliveryAttempt
        fields = ['id', 'event_type', 'attempt_number', 'response_status', 'succeeded', 'created_at']
