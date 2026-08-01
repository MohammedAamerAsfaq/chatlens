from rest_framework import serializers
from .models import (
    Product, ProductAlias, ProductAttribute, MessageClassification, Inquiry, InquiryMessage,
    InquiryProduct, AiParsingLog, BuyingInquiry, SupplierQuote,
    AutomationRule, AutomationRuleSource, AutomatedPriceCapture,
)


class ProductSerializer(serializers.ModelSerializer):
    # Read-only convenience list for display/search — managed for real via the
    # dedicated /products/{id}/aliases/ endpoints (ProductAliasSerializer below),
    # never written through this serializer.
    aliases = serializers.SerializerMethodField()
    # Same convenience-list pattern as aliases — managed via /products/{id}/attributes/
    # (ProductAttributeSerializer below), never written through this serializer.
    attributes = serializers.SerializerMethodField()
    # Per-row embedding visibility for the product table — same signal as
    # /products/embedding-status/'s aggregate counts, just broken out per product so a
    # specific silently-failed background embed (see backfill-embeddings) can be spotted
    # without cross-referencing anything.
    has_embedding          = serializers.SerializerMethodField()
    alias_embedding_status = serializers.SerializerMethodField()

    class Meta:
        model  = Product
        fields = ['id', 'name', 'brand', 'category', 'sku', 'aliases', 'attributes', 'is_active',
                  'qty', 'cost_price', 'sale_price', 'currency',
                  'has_embedding', 'alias_embedding_status',
                  'created_at', 'updated_at']
        read_only_fields = ['id', 'aliases', 'attributes', 'has_embedding', 'alias_embedding_status',
                             'created_at', 'updated_at']

    def get_aliases(self, obj):
        return [a.alias for a in obj.alias_set.all()]

    def get_attributes(self, obj):
        return ProductAttributeSerializer(obj.attribute_set.all(), many=True).data

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


class ProductAttributeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductAttribute
        fields = ['id', 'product', 'key', 'value', 'created_at', 'updated_at']
        read_only_fields = ['id', 'product', 'created_at', 'updated_at']


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
        roles = set(obj.contact.role_tags.values_list('role', flat=True))
        if {'supplier', 'customer'}.issubset(roles):
            return 'both'
        if 'supplier' in roles:
            return 'supplier'
        if 'customer' in roles:
            return 'customer'
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


class InquiryProductSerializer(serializers.ModelSerializer):
    account_name = serializers.SerializerMethodField()
    contact_name = serializers.SerializerMethodField()
    contact_phone = serializers.SerializerMethodField()
    company_contact_name = serializers.SerializerMethodField()
    product_name = serializers.SerializerMethodField()
    source_message_text = serializers.CharField(source='source_message.message_text', read_only=True)
    source_message_time = serializers.DateTimeField(source='source_message.message_time', read_only=True)
    source_chat_id = serializers.IntegerField(source='source_message.chat_id', read_only=True)
    inquiry_summary = serializers.CharField(source='inquiry.summary', read_only=True)

    class Meta:
        model = InquiryProduct
        fields = [
            'id', 'company', 'inquiry', 'source_message', 'source_message_text',
            'source_message_time', 'source_chat_id', 'account', 'account_name',
            'contact', 'contact_name', 'contact_phone', 'company_contact',
            'company_contact_name', 'product', 'product_name', 'inquiry_type',
            'source_product_index', 'canonical_name', 'normalized_name', 'original_text',
            'quantity', 'price', 'currency', 'decision_status', 'match_status',
            'match_type', 'match_source', 'match_reason', 'embedding_status',
            'embedding_model', 'embedding_error', 'first_seen_at', 'created_at',
            'updated_at', 'inquiry_summary',
        ]
        read_only_fields = fields

    def get_account_name(self, obj):
        if not obj.account:
            return ''
        return obj.account.display_name or obj.account.phone_number or f'Account {obj.account_id}'

    def get_contact_name(self, obj):
        if not obj.contact:
            return ''
        return (
            obj.contact.display_name
            or obj.contact.push_name
            or obj.contact.phone_number
            or obj.contact.wa_contact_id
        )

    def get_contact_phone(self, obj):
        return obj.contact.phone_number if obj.contact else ''

    def get_company_contact_name(self, obj):
        if not obj.company_contact:
            return ''
        return obj.company_contact.display_name or obj.company_contact.legal_name or ''

    def get_product_name(self, obj):
        if not obj.product:
            return ''
        return f'{obj.product.brand} {obj.product.name}'.strip()


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


def _contact_label(contact) -> str:
    """WhatsApp's own name for this contact (push_name) leads, with the locally
    saved/edited name (display_name) alongside in brackets when it differs —
    e.g. "Laeeq Bhai Dubai (Laeeq Ahmed)". Falls back to phone/wa_contact_id when
    push_name is missing."""
    whatsapp_name = contact.push_name or contact.phone_number or contact.wa_contact_id
    saved_name = contact.display_name
    if saved_name and saved_name != whatsapp_name:
        return f'{whatsapp_name} ({saved_name})'
    return whatsapp_name


def _account_label(account) -> str:
    return account.display_name or account.phone_number or f'Account {account.id}'


class AutomationRuleSourceSerializer(serializers.ModelSerializer):
    contact_name = serializers.SerializerMethodField()
    group_name   = serializers.SerializerMethodField()
    # Contacts/groups with the same name can exist on different linked WhatsApp
    # accounts — shown separately for contact vs. group (not one shared field) so a
    # contact_in_group source visibly shows if they were mismatched across accounts,
    # which the picker doesn't currently prevent at the data-entry step.
    contact_account_name = serializers.SerializerMethodField()
    group_account_name   = serializers.SerializerMethodField()

    class Meta:
        model = AutomationRuleSource
        fields = [
            'id', 'source_type', 'contact', 'contact_name', 'contact_account_name',
            'group', 'group_name', 'group_account_name',
        ]
        read_only_fields = ['id', 'contact_name', 'contact_account_name', 'group_name', 'group_account_name']

    def get_contact_name(self, obj):
        return _contact_label(obj.contact) if obj.contact else None

    def get_group_name(self, obj):
        return obj.group.name if obj.group else None

    def get_contact_account_name(self, obj):
        return _account_label(obj.contact.account) if obj.contact else None

    def get_group_account_name(self, obj):
        return _account_label(obj.group.account) if obj.group else None


class AutomationRuleSerializer(serializers.ModelSerializer):
    # Sources are managed via the nested list here on read, but writes go through
    # AutomationRuleViewSet's own create/update (which replaces the whole set
    # atomically) — plain ModelSerializer nested-write semantics are the wrong fit
    # for "replace this rule's entire source list every save."
    sources = AutomationRuleSourceSerializer(many=True, read_only=True)

    class Meta:
        model = AutomationRule
        fields = [
            'id', 'name', 'is_active', 'trigger_heading', 'trigger_ai_detect',
            'action_mode', 'sources', 'last_triggered_at', 'trigger_count',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'sources', 'last_triggered_at', 'trigger_count', 'created_at', 'updated_at']


class AutomatedPriceCaptureSerializer(serializers.ModelSerializer):
    rule_name    = serializers.CharField(source='rule.name', default=None, read_only=True)
    source_name  = serializers.SerializerMethodField()
    source_kind  = serializers.SerializerMethodField()
    group_name   = serializers.SerializerMethodField()
    message_text = serializers.CharField(source='message.message_text', read_only=True)
    message_time = serializers.DateTimeField(source='message.message_time', read_only=True)

    class Meta:
        model = AutomatedPriceCapture
        fields = [
            'id', 'rule', 'rule_name', 'message', 'source_name', 'source_kind', 'group_name',
            'message_text', 'message_time', 'items', 'status', 'created_at', 'applied_at',
        ]
        read_only_fields = fields

    def get_source_name(self, obj):
        contact = obj.message.contact
        return _contact_label(contact) if contact else (obj.message.sender_number or None)

    def get_source_kind(self, obj):
        from apps.whatsapp_bridge.models import ChatType
        chat = obj.message.chat
        return 'group' if (chat and chat.chat_type == ChatType.GROUP) else 'direct'

    def get_group_name(self, obj):
        from apps.whatsapp_bridge.models import ChatType
        chat = obj.message.chat
        if chat and chat.chat_type == ChatType.GROUP:
            return chat.name or chat.wa_chat_id
        return None
