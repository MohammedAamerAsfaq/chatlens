from rest_framework import serializers
from .models import Product, MessageClassification, Inquiry, InquiryMessage


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Product
        fields = ['id', 'name', 'brand', 'category', 'sku', 'aliases', 'is_active',
                  'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class MessageClassificationSerializer(serializers.ModelSerializer):
    class Meta:
        model  = MessageClassification
        fields = ['id', 'message', 'tags', 'products', 'is_inquiry', 'inquiry_type',
                  'ai_summary', 'classified_at']
        read_only_fields = fields


class InquiryMessageSerializer(serializers.ModelSerializer):
    message_text  = serializers.CharField(source='message.message_text', read_only=True)
    message_time  = serializers.DateTimeField(source='message.message_time', read_only=True)
    chat_name     = serializers.SerializerMethodField()
    chat_type     = serializers.CharField(source='message.chat.chat_type', read_only=True)
    sender_number = serializers.CharField(source='message.sender_number', read_only=True)
    push_name     = serializers.CharField(source='message.push_name', read_only=True)

    class Meta:
        model  = InquiryMessage
        fields = ['id', 'message', 'message_text', 'message_time',
                  'chat_name', 'chat_type', 'sender_number', 'push_name', 'added_at']
        read_only_fields = fields

    def get_chat_name(self, obj):
        chat = obj.message.chat
        return chat.name or chat.wa_chat_id


class InquirySerializer(serializers.ModelSerializer):
    contact_name   = serializers.SerializerMethodField()
    contact_phone  = serializers.SerializerMethodField()
    age_seconds    = serializers.SerializerMethodField()
    source_chat_id = serializers.SerializerMethodField()

    class Meta:
        model  = Inquiry
        fields = [
            'id', 'account', 'contact', 'contact_name', 'contact_phone',
            'inquiry_type', 'status', 'products', 'summary', 'remarks',
            'dedup_key', 'source_type', 'source_chat_id', 'first_seen_at', 'closed_at',
            'age_seconds', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'account', 'contact', 'contact_name', 'contact_phone',
            'inquiry_type', 'products', 'summary', 'dedup_key', 'source_type',
            'source_chat_id', 'first_seen_at', 'age_seconds', 'created_at', 'updated_at',
        ]

    def get_contact_name(self, obj):
        if not obj.contact:
            return ''
        return (obj.contact.display_name or obj.contact.push_name
                or obj.contact.phone_number or obj.contact.wa_contact_id)

    def get_contact_phone(self, obj):
        if not obj.contact:
            return ''
        return obj.contact.phone_number or ''

    def get_age_seconds(self, obj):
        from django.utils.timezone import now
        return int((now() - obj.first_seen_at).total_seconds())

    def get_source_chat_id(self, obj):
        link = obj.inquiry_messages.select_related('message').first()
        return link.message.chat_id if link else None


class InquiryDetailSerializer(InquirySerializer):
    messages = serializers.SerializerMethodField()

    class Meta(InquirySerializer.Meta):
        fields = InquirySerializer.Meta.fields + ['messages']

    def get_messages(self, obj):
        qs = (
            obj.inquiry_messages
            .select_related('message', 'message__chat', 'message__contact')
            .order_by('message__message_time')
        )
        return InquiryMessageSerializer(qs, many=True).data
