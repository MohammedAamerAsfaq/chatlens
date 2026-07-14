from rest_framework import serializers
from .models import (
    Product, ProductAlias, MessageClassification, Inquiry, InquiryMessage, AiParsingLog,
    BuyingInquiry, SupplierQuote,
)


class ProductSerializer(serializers.ModelSerializer):
    # Read-only convenience list for display/search — managed for real via the
    # dedicated /products/{id}/aliases/ endpoints (ProductAliasSerializer below),
    # never written through this serializer.
    aliases = serializers.SerializerMethodField()
    # Per-row embedding visibility for the product table — same signal as
    # /products/embedding-status/'s aggregate counts, just broken out per product so a
    # specific silently-failed background embed (see backfill-embeddings) can be spotted
    # without cross-referencing anything.
    has_embedding          = serializers.SerializerMethodField()
    alias_embedding_status = serializers.SerializerMethodField()

    class Meta:
        model  = Product
        fields = ['id', 'name', 'brand', 'category', 'sku', 'aliases', 'is_active',
                  'qty', 'cost_price', 'sale_price', 'currency',
                  'has_embedding', 'alias_embedding_status',
                  'created_at', 'updated_at']
        read_only_fields = ['id', 'aliases', 'has_embedding', 'alias_embedding_status',
                             'created_at', 'updated_at']

    def get_aliases(self, obj):
        return [a.alias for a in obj.alias_set.all()]

    def get_has_embedding(self, obj):
        emb = getattr(obj, 'embedding', None)
        return bool(emb and emb.embedding is not None)

    def get_alias_embedding_status(self, obj):
        aliases = list(obj.alias_set.all())
        embedded = sum(
            1 for a in aliases
            if (emb := getattr(a, 'embedding', None)) and emb.embedding is not None
        )
        return {'embedded': embedded, 'total': len(aliases)}


class ProductAliasSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductAlias
        fields = ['id', 'product', 'alias', 'created_at']
        read_only_fields = ['id', 'product', 'created_at']


class MessageClassificationSerializer(serializers.ModelSerializer):
    class Meta:
        model  = MessageClassification
        fields = ['id', 'message', 'tags', 'products', 'is_inquiry', 'inquiry_type',
                  'ai_summary', 'classified_at']
        read_only_fields = fields


class AiParsingLogSerializer(serializers.ModelSerializer):
    account_name  = serializers.SerializerMethodField()
    chat_name     = serializers.SerializerMethodField()
    message_time  = serializers.DateTimeField(source='message.message_time', read_only=True)
    direction     = serializers.CharField(source='message.direction', read_only=True)

    class Meta:
        model  = AiParsingLog
        fields = ['id', 'message', 'account', 'account_name', 'chat', 'chat_name',
                  'status', 'skip_reason', 'message_preview', 'message_time',
                  'direction', 'created_at']
        read_only_fields = fields

    def get_account_name(self, obj):
        a = obj.account
        return a.display_name or a.phone_number or f'Account {a.pk}'

    def get_chat_name(self, obj):
        if not obj.chat:
            return ''
        return obj.chat.name or obj.chat.wa_chat_id


class InquiryMessageSerializer(serializers.ModelSerializer):
    message_text  = serializers.CharField(source='message.message_text', read_only=True)
    message_time  = serializers.DateTimeField(source='message.message_time', read_only=True)
    chat_id       = serializers.IntegerField(source='message.chat_id', read_only=True)
    chat_name     = serializers.SerializerMethodField()
    chat_type     = serializers.CharField(source='message.chat.chat_type', read_only=True)
    sender_number = serializers.CharField(source='message.sender_number', read_only=True)
    push_name     = serializers.CharField(source='message.push_name', read_only=True)

    class Meta:
        model  = InquiryMessage
        fields = ['id', 'message', 'message_text', 'message_time',
                  'chat_id', 'chat_name', 'chat_type', 'sender_number', 'push_name', 'added_at']
        read_only_fields = fields

    def get_chat_name(self, obj):
        chat = obj.message.chat
        return chat.name or chat.wa_chat_id


class InquirySerializer(serializers.ModelSerializer):
    contact_name   = serializers.SerializerMethodField()
    contact_phone  = serializers.SerializerMethodField()
    contact_category = serializers.SerializerMethodField()
    account_name   = serializers.SerializerMethodField()
    age_seconds    = serializers.SerializerMethodField()
    source_chat_id      = serializers.SerializerMethodField()
    source_message_id   = serializers.SerializerMethodField()
    source_message_time = serializers.SerializerMethodField()
    source_message_text = serializers.SerializerMethodField()

    class Meta:
        model  = Inquiry
        fields = [
            'id', 'account', 'account_name', 'contact', 'contact_name', 'contact_phone',
            'contact_category', 'suggested_contact_category',
            'inquiry_type', 'status', 'products', 'summary', 'remarks',
            'dedup_key', 'source_type', 'source_chat_id', 'source_message_id',
            'source_message_time', 'source_message_text', 'first_seen_at', 'closed_at',
            'classification_rating', 'age_seconds', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'account', 'account_name', 'contact', 'contact_name', 'contact_phone',
            'contact_category', 'suggested_contact_category',
            'inquiry_type', 'products', 'summary', 'dedup_key', 'source_type',
            'source_chat_id', 'source_message_id', 'source_message_time', 'source_message_text',
            'first_seen_at', 'age_seconds', 'created_at', 'updated_at',
        ]

    def get_account_name(self, obj):
        a = obj.account
        return a.display_name or a.phone_number or f'Account {a.pk}'

    def get_contact_name(self, obj):
        if not obj.contact:
            return ''
        return (obj.contact.display_name or obj.contact.push_name
                or obj.contact.phone_number or obj.contact.wa_contact_id)

    def get_contact_phone(self, obj):
        if not obj.contact:
            return ''
        return obj.contact.phone_number or ''

    def get_contact_category(self, obj):
        if not obj.contact:
            return ''
        return obj.contact.category or ''

    def get_age_seconds(self, obj):
        from django.utils.timezone import now
        return int((now() - obj.first_seen_at).total_seconds())

    def _first_message(self, obj):
        if not hasattr(obj, '_cached_first_msg'):
            obj._cached_first_msg = (
                obj.inquiry_messages.select_related('message')
                .order_by('message__message_time').first()
            )
        return obj._cached_first_msg

    def get_source_chat_id(self, obj):
        link = self._first_message(obj)
        return link.message.chat_id if link else None

    def get_source_message_id(self, obj):
        link = self._first_message(obj)
        return link.message.id if link else None

    def get_source_message_time(self, obj):
        link = self._first_message(obj)
        return link.message.message_time.isoformat() if link else None

    def get_source_message_text(self, obj):
        link = self._first_message(obj)
        return link.message.message_text if link else ''


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


class SupplierQuoteSerializer(serializers.ModelSerializer):
    supplier_name  = serializers.SerializerMethodField()
    supplier_phone = serializers.CharField(source='supplier.phone_number', read_only=True)

    class Meta:
        model = SupplierQuote
        fields = [
            'id', 'buying_inquiry', 'supplier', 'supplier_name', 'supplier_phone',
            'status', 'asked_at', 'quoted_price', 'quoted_currency', 'quote_note',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'buying_inquiry', 'supplier_name', 'supplier_phone', 'created_at', 'updated_at']

    def get_supplier_name(self, obj):
        c = obj.supplier
        return c.display_name or c.push_name or c.phone_number or c.wa_contact_id


class BuyingInquirySerializer(serializers.ModelSerializer):
    account_name    = serializers.SerializerMethodField()
    supplier_quotes = SupplierQuoteSerializer(many=True, read_only=True)

    class Meta:
        model = BuyingInquiry
        fields = [
            'id', 'account', 'account_name', 'product_name', 'quantity', 'notes',
            'status', 'supplier_quotes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'account_name', 'supplier_quotes', 'created_at', 'updated_at']

    def get_account_name(self, obj):
        a = obj.account
        return a.display_name or a.phone_number or f'Account {a.pk}'
