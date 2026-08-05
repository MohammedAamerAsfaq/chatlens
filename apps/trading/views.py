import json
import logging
import threading
from django.db import connection as _db_conn
from django.db.models import Count, Max, Min, Q
from django.utils.timezone import now, make_aware
from datetime import timedelta, date as _date, datetime as _datetime, time as _time
from rest_framework import viewsets, mixins, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.tenancy.services.access import (
    default_company_for_user,
    scope_queryset_to_visible_accounts,
    scope_queryset_to_visible_companies,
    visible_accounts_queryset,
)
from .models import Product, ProductAlias, ProductAttribute, MessageClassification, Inquiry, InquiryProduct, InquiryStatus, PromptConfig, PRODUCT_EXTRACTION_DEFAULT, INQUIRY_CLASSIFICATION_DEFAULT, INQUIRY_EXTRACTION_V2_DEFAULT, INQUIRY_MATCH_DECISION_V2_DEFAULT, INVENTORY_UPDATE_DEFAULT, PRICE_LIST_FORMAT_DEFAULT, QTY_COST_UPDATE_DEFAULT, SALE_PRICE_UPDATE_DEFAULT, MATCH_VERIFICATION_DEFAULT, AgentCallLog, AiParsingLog, AiParseV2Log, BuyingInquiry, SupplierQuote, AutomationRule, AutomationRuleSource, AutomatedPriceCapture
from .serializers import (
    ProductSerializer,
    ProductAliasSerializer,
    ProductAttributeSerializer,
    MessageClassificationSerializer,
    InquirySerializer,
    InquiryDetailSerializer,
    InquiryProductSerializer,
    AiParsingLogSerializer,
    AiParseV2LogSerializer,
    BuyingInquirySerializer,
    SupplierQuoteSerializer,
    AutomationRuleSerializer,
    AutomatedPriceCaptureSerializer,
)
from .services.product_cache import invalidate as invalidate_product_cache

logger = logging.getLogger(__name__)


def _visible_account_or_none(user, account_id):
    if not account_id:
        return None
    return visible_accounts_queryset(user).filter(pk=account_id).first()


def _visible_product_or_none(user, product_id):
    if not product_id:
        return None
    return scope_queryset_to_visible_companies(
        Product.objects.all(),
        user,
        company_field='company',
    ).filter(pk=product_id).first()


def _visible_rule_queryset(user, qs=None):
    qs = qs if qs is not None else AutomationRule.objects.all()
    if user.is_superuser:
        return qs
    visible_account_ids = visible_accounts_queryset(user).values('pk')
    return qs.filter(
        Q(sources__contact__account__in=visible_account_ids) |
        Q(sources__group__account__in=visible_account_ids)
    ).distinct()


def _resolve_date_range(request):
    """(start, end) timezone-aware datetimes for the requested date_from/date_to query
    params (YYYY-MM-DD, inclusive on both ends). Defaults to "today" (a single day) when
    neither is given — preserves the existing behavior for callers that don't pass them,
    e.g. the Trading Dashboard's stat chips, which must keep showing today-only numbers.
    """
    date_from = request.query_params.get('date_from')
    date_to   = request.query_params.get('date_to')

    if date_from:
        start = make_aware(_datetime.combine(_date.fromisoformat(date_from), _time.min))
    else:
        start = now().replace(hour=0, minute=0, second=0, microsecond=0)

    if date_to:
        end = make_aware(_datetime.combine(_date.fromisoformat(date_to), _time.min)) + timedelta(days=1)
    else:
        end = start + timedelta(days=1)

    return start, end


def _embed_product_in_background(product_id: int):
    """Fire-and-forget embedding after a product create/update — same pattern as live
    message embedding in ingestion_service.py. Never blocks the save request; a failure
    here (provider hiccup) is logged and otherwise invisible, never surfaced to the user
    editing the product, since the classification prompt still works off plain text
    regardless of whether this embedding exists yet."""
    def _run():
        try:
            from apps.message_intelligence.services.embedding_service import embed_product
            embed_product(product_id)
        except Exception:
            logger.warning('Background product embedding failed for product_id=%s', product_id, exc_info=True)
        finally:
            _db_conn.close()

    threading.Thread(target=_run, daemon=True).start()


def _embed_products_batch_in_background(product_ids: list):
    """Same as _embed_product_in_background but for a batch (bulk import) — one
    background thread, one provider-side batch call, instead of N individual threads."""
    if not product_ids:
        return

    def _run():
        try:
            from apps.message_intelligence.services.embedding_service import embed_products_batch
            embed_products_batch(product_ids)
        except Exception:
            logger.warning('Background batch product embedding failed for %d product(s)', len(product_ids), exc_info=True)
        finally:
            _db_conn.close()

    threading.Thread(target=_run, daemon=True).start()


def _embed_alias_in_background(alias_id: int):
    """Same pattern as _embed_product_in_background, for a single new/edited alias."""
    def _run():
        try:
            from apps.message_intelligence.services.embedding_service import embed_product_alias
            embed_product_alias(alias_id)
        except Exception:
            logger.warning('Background alias embedding failed for alias_id=%s', alias_id, exc_info=True)
        finally:
            _db_conn.close()

    threading.Thread(target=_run, daemon=True).start()


def _embed_aliases_batch_in_background(alias_ids: list):
    """Same as _embed_alias_in_background but for a batch (bulk import)."""
    if not alias_ids:
        return

    def _run():
        try:
            from apps.message_intelligence.services.embedding_service import embed_product_aliases_batch
            embed_product_aliases_batch(alias_ids)
        except Exception:
            logger.warning('Background batch alias embedding failed for %d alias(es)', len(alias_ids), exc_info=True)
        finally:
            _db_conn.close()

    threading.Thread(target=_run, daemon=True).start()


class ProductViewSet(viewsets.ModelViewSet):
    serializer_class   = ProductSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = scope_queryset_to_visible_companies(
            Product.objects.all().select_related('embedding').prefetch_related('alias_set__embedding', 'attribute_set'),
            self.request.user,
            company_field='company',
        )
        active = self.request.query_params.get('active')
        if active == 'true':
            qs = qs.filter(is_active=True)
        elif active == 'false':
            qs = qs.filter(is_active=False)
        return qs

    def perform_create(self, serializer):
        company = default_company_for_user(self.request.user)
        product = serializer.save(company=company)
        invalidate_product_cache()
        _embed_product_in_background(product.pk)

    def perform_update(self, serializer):
        product = serializer.save()
        invalidate_product_cache()
        _embed_product_in_background(product.pk)

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=['is_active', 'updated_at'])
        invalidate_product_cache()

    @action(detail=False, methods=['post'], url_path='parse-text')
    def parse_text(self, request):
        """Extract product names from free-form price list text using AI."""
        from apps.ai_providers.manager import ai_manager

        from apps.trading.models import PromptConfig, PRODUCT_EXTRACTION_DEFAULT

        text = (request.data.get('text') or '').strip()
        if not text:
            return Response({'error': 'text is required'}, status=status.HTTP_400_BAD_REQUEST)

        system_prompt = PromptConfig.get_body(
            PromptConfig.KEY_PRODUCT_EXTRACTION,
            PRODUCT_EXTRACTION_DEFAULT,
            company=default_company_for_user(request.user),
        )

        messages = [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user',   'content': text},
        ]
        try:
            from apps.trading.services.agent_logger import call_agent
            raw = call_agent(
                PromptConfig.KEY_PRODUCT_EXTRACTION,
                messages,
                temperature=0,
            )
            cleaned = raw.strip()
            if cleaned.startswith('```'):
                cleaned = cleaned.split('\n', 1)[-1].rsplit('```', 1)[0]
            products = json.loads(cleaned)
            if not isinstance(products, list):
                raise ValueError('AI did not return a list')
            return Response({'products': products})
        except Exception as exc:
            logger.exception('parse_text | failed')
            return Response({'error': str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'], url_path='bulk-create')
    def bulk_create(self, request):
        """Create multiple products; skips names that already exist (case-insensitive)."""
        items = request.data.get('products') or []
        created, skipped = [], []
        new_alias_ids = []
        for item in items:
            name = (item.get('name') or '').strip()
            if not name:
                continue
            if self.get_queryset().filter(name__iexact=name).exists():
                skipped.append(name)
                continue
            p = Product.objects.create(
                company=default_company_for_user(request.user),
                name=name,
                brand=(item.get('brand') or '').strip(),
                category=(item.get('category') or '').strip(),
                sku=(item.get('sku') or '').strip(),
            )
            seen = set()
            for raw in (item.get('aliases') or []):
                alias_text = (raw or '').strip()
                key = alias_text.lower()
                if not alias_text or key in seen:
                    continue
                seen.add(key)
                new_alias_ids.append(ProductAlias.objects.create(product=p, alias=alias_text).pk)
            created.append(ProductSerializer(p).data)
        if created:
            invalidate_product_cache()
            _embed_products_batch_in_background([p['id'] for p in created])
            _embed_aliases_batch_in_background(new_alias_ids)
        return Response({'created': created, 'skipped': skipped})

    @action(detail=True, methods=['get', 'post'], url_path='aliases')
    def aliases(self, request, pk=None):
        """List or add aliases for one product. Each addition gets its own embedding
        (see ProductAliasEmbedding) — this is the CRUD surface the frontend's alias
        chip input in the product form talks to; it's independent of the main
        product PATCH/PUT, so adding an alias never requires re-saving the product."""
        product = self.get_object()
        if request.method == 'GET':
            return Response(ProductAliasSerializer(product.alias_set.all(), many=True).data)

        alias_text = (request.data.get('alias') or '').strip()
        if not alias_text:
            return Response({'detail': 'alias is required'}, status=status.HTTP_400_BAD_REQUEST)
        if product.alias_set.filter(alias__iexact=alias_text).exists():
            return Response({'detail': 'This alias already exists for this product'}, status=status.HTTP_400_BAD_REQUEST)

        obj = ProductAlias.objects.create(product=product, alias=alias_text)
        invalidate_product_cache()
        _embed_alias_in_background(obj.pk)
        return Response(ProductAliasSerializer(obj).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['delete'], url_path=r'aliases/(?P<alias_id>\d+)')
    def delete_alias(self, request, pk=None, alias_id=None):
        product = self.get_object()
        deleted, _ = product.alias_set.filter(pk=alias_id).delete()
        if not deleted:
            return Response({'detail': 'Alias not found'}, status=status.HTTP_404_NOT_FOUND)
        invalidate_product_cache()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['get', 'post'], url_path='attributes')
    def attributes(self, request, pk=None):
        """List or add hot key/value attributes for one product — arbitrary per-product
        details (color, warranty, etc.) that don't warrant their own column on Product."""
        product = self.get_object()
        if request.method == 'GET':
            return Response(ProductAttributeSerializer(product.attribute_set.all(), many=True).data)

        key   = (request.data.get('key') or '').strip()
        value = (request.data.get('value') or '').strip()
        if not key:
            return Response({'detail': 'key is required'}, status=status.HTTP_400_BAD_REQUEST)
        if product.attribute_set.filter(key__iexact=key).exists():
            return Response({'detail': 'This key already exists for this product'}, status=status.HTTP_400_BAD_REQUEST)

        obj = ProductAttribute.objects.create(product=product, key=key, value=value)
        return Response(ProductAttributeSerializer(obj).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['patch', 'delete'], url_path=r'attributes/(?P<attribute_id>\d+)')
    def edit_attribute(self, request, pk=None, attribute_id=None):
        product = self.get_object()
        try:
            attr = product.attribute_set.get(pk=attribute_id)
        except ProductAttribute.DoesNotExist:
            return Response({'detail': 'Attribute not found'}, status=status.HTTP_404_NOT_FOUND)

        if request.method == 'DELETE':
            attr.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

        key   = request.data.get('key')
        value = request.data.get('value')
        update_fields = ['updated_at']
        if key is not None:
            key = key.strip()
            if not key:
                return Response({'detail': 'key cannot be empty'}, status=status.HTTP_400_BAD_REQUEST)
            if product.attribute_set.filter(key__iexact=key).exclude(pk=attr.pk).exists():
                return Response({'detail': 'This key already exists for this product'}, status=status.HTTP_400_BAD_REQUEST)
            attr.key = key
            update_fields.append('key')
        if value is not None:
            attr.value = value.strip()
            update_fields.append('value')
        attr.save(update_fields=update_fields)
        return Response(ProductAttributeSerializer(attr).data)

    @action(detail=False, methods=['post'], url_path='parse-inventory')
    def parse_inventory(self, request):
        """
        Send one or two free-form text blocks to the AI to extract inventory updates.
        cost_text: product names + qty + cost prices
        sale_text: product names + sale prices (optional)
        Returns [{product_id, canonical_name, qty, cost_price, sale_price, currency}].
        """
        cost_text = (request.data.get('cost_text') or '').strip()
        sale_text = (request.data.get('sale_text') or '').strip()

        if not cost_text and not sale_text:
            return Response({'error': 'Provide at least cost_text or sale_text.'}, status=status.HTTP_400_BAD_REQUEST)

        from apps.trading.services.product_cache import get_product_prompt_block
        from apps.trading.services.agent_logger import call_agent

        product_block = get_product_prompt_block(company=default_company_for_user(request.user))
        system_prompt = PromptConfig.get_body(
            PromptConfig.KEY_INVENTORY_UPDATE,
            INVENTORY_UPDATE_DEFAULT,
            company=default_company_for_user(request.user),
        ).replace('{product_block}', product_block)

        parts = []
        if cost_text:
            parts.append(f'STOCK & COST:\n{cost_text}')
        if sale_text:
            parts.append(f'SALE PRICE:\n{sale_text}')
        user_text = '\n---\n'.join(parts)

        try:
            raw = call_agent(
                PromptConfig.KEY_INVENTORY_UPDATE,
                [
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user',   'content': user_text},
                ],
                temperature=0,
            )
            cleaned = raw.strip()
            if cleaned.startswith('```'):
                cleaned = cleaned.split('\n', 1)[-1].rsplit('```', 1)[0]
            items = json.loads(cleaned)
            if not isinstance(items, list):
                raise ValueError('AI did not return a list')
            return Response({'items': items})
        except Exception as exc:
            logger.exception('parse_inventory | failed')
            return Response({'error': str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'], url_path='bulk-update-inventory')
    def bulk_update_inventory(self, request):
        """
        Apply inventory updates: set qty, cost_price, sale_price, currency on matched products.
        Items with product_id are matched by PK; items without are matched by name (iexact).
        """
        items = request.data.get('items') or []
        updated, skipped = [], []

        for item in items:
            product_id = item.get('product_id')
            name       = (item.get('canonical_name') or '').strip()
            qty        = item.get('qty')
            cost_price = item.get('cost_price')
            sale_price = item.get('sale_price')
            currency   = (item.get('currency') or 'USD').strip()

            product = None
            if product_id:
                product = _visible_product_or_none(request.user, product_id)
            if not product and name:
                product = self.get_queryset().filter(name__iexact=name, is_active=True).first()

            if not product:
                skipped.append(name or str(product_id))
                continue

            update_fields = ['updated_at']
            if qty is not None:
                product.qty = int(qty)
                update_fields.append('qty')
            if cost_price is not None:
                product.cost_price = cost_price
                update_fields.append('cost_price')
            if sale_price is not None:
                product.sale_price = sale_price
                update_fields.append('sale_price')
            if currency:
                product.currency = currency
                update_fields.append('currency')

            product.save(update_fields=update_fields)
            updated.append(ProductSerializer(product).data)

        if updated:
            invalidate_product_cache()
        return Response({'updated': updated, 'skipped': skipped})

    @action(detail=False, methods=['get'], url_path='price-list')
    def price_list(self, request):
        """Return the current AI-formatted price list (empty body if never generated)."""
        from apps.trading.models import FormattedPriceList

        obj = FormattedPriceList.get_current(company=default_company_for_user(request.user))
        return Response({
            'body':         obj.body if obj else '',
            'generated_at': obj.generated_at.isoformat() if obj and obj.generated_at else None,
        })

    @action(detail=False, methods=['post'], url_path='regenerate-price-list')
    def regenerate_price_list(self, request):
        """Re-run the AI formatting prompt against the current in-stock, priced catalog."""
        from apps.trading.services.price_list_service import generate_price_list

        try:
            obj = generate_price_list(default_company_for_user(request.user))
        except Exception as exc:
            logger.exception('regenerate_price_list | failed')
            return Response({'error': str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({
            'body':         obj.body,
            'generated_at': obj.generated_at.isoformat() if obj.generated_at else None,
        })

    @action(detail=False, methods=['get'], url_path='search-embeddings')
    def search_embeddings(self, request):
        """Embedding-based product search — multi-vector (product name + every alias,
        §6.8.1), so a query in any word order or phrasing can match. Two callers as of
        this writing: the trading dashboard's "Auto" match-fix button (only called
        client-side after a direct name/alias search over the loaded catalog comes up
        empty, and never applies a match on its own — just narrows candidates for a
        human to confirm) and the Products page's standalone "Smart Search" box (a
        dedicated search feature, not a matching aid). `top_k` defaults to 5 to match
        the original caller's behavior unchanged; pass a higher value for a fuller
        result list.
        """
        from apps.message_intelligence.services.embedding_service import find_similar_products

        query = request.query_params.get('q', '').strip()
        if not query:
            return Response({'results': []})

        try:
            top_k = int(request.query_params.get('top_k', 5))
        except (TypeError, ValueError):
            top_k = 5
        top_k = max(1, min(top_k, 20))

        try:
            hits = find_similar_products(query, top_k=top_k)
        except Exception as exc:
            logger.warning(f'search_embeddings | query={query!r} failed: {exc}')
            return Response({'detail': 'Embedding search unavailable'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        visible_product_ids = set(self.get_queryset().values_list('id', flat=True))
        results = [
            {'product': ProductSerializer(hit.product).data, 'distance': round(float(hit.distance), 4)}
            for hit in hits
            if hit.product_id in visible_product_ids
        ]
        return Response({'results': results})

    @action(detail=False, methods=['get'], url_path='search-v2-candidates')
    def search_v2_candidates(self, request):
        """Diagnostic search that uses the same candidate retrieval and attribute
        reranking path as V2 pass 2 candidate selection.
        """
        import json
        from apps.trading.services.classification_service import _find_v2_candidates
        from apps.tenancy.services.access import default_company_for_user

        query = request.query_params.get('q', '').strip()
        if not query:
            return Response({'results': []})

        brand = request.query_params.get('brand', '').strip()
        try:
            top_k = int(request.query_params.get('top_k', 10))
        except (TypeError, ValueError):
            top_k = 10
        top_k = max(1, min(top_k, 20))

        raw_attributes = request.query_params.get('attributes', '').strip()
        attributes = {}
        if raw_attributes:
            try:
                parsed = json.loads(raw_attributes)
            except json.JSONDecodeError as exc:
                return Response({'detail': f'attributes must be valid JSON: {exc}'}, status=status.HTTP_400_BAD_REQUEST)
            if not isinstance(parsed, dict):
                return Response({'detail': 'attributes must be a JSON object'}, status=status.HTTP_400_BAD_REQUEST)
            attributes = parsed

        try:
            candidates = _find_v2_candidates(
                query,
                default_company_for_user(request.user),
                top_k=top_k,
                brand=brand,
                attributes=attributes,
            )
        except Exception as exc:
            logger.warning('search_v2_candidates | query=%r failed: %s', query, exc)
            return Response({'detail': 'V2 candidate search unavailable'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        return Response({
            'query': query,
            'brand': brand,
            'attributes': attributes,
            'results': candidates,
        })

    @action(detail=False, methods=['get'], url_path='embedding-status')
    def embedding_status(self, request):
        """Counts of embedded vs. missing for products and their aliases — the only
        durable signal for a background embedding job that failed (a provider hiccup,
        rate limit, etc.). Those failures only ever land in a console warning with
        nothing persisted, so "missing an embedding" is itself the record; this and
        backfill-embeddings below are how that gets noticed and fixed instead of
        silently sitting broken forever."""
        from apps.message_intelligence.models import ProductEmbedding, ProductAliasEmbedding

        visible_products = scope_queryset_to_visible_companies(
            Product.objects.filter(is_active=True),
            request.user,
            company_field='company',
        )
        visible_aliases = scope_queryset_to_visible_companies(
            ProductAlias.objects.filter(product__is_active=True),
            request.user,
            company_field='product__company',
        )

        product_total = visible_products.count()
        product_embedded = ProductEmbedding.objects.filter(
            product__in=visible_products, embedding__isnull=False,
        ).count()

        alias_total = visible_aliases.count()
        alias_embedded = ProductAliasEmbedding.objects.filter(
            alias__in=visible_aliases, embedding__isnull=False,
        ).count()

        return Response({
            'products': {'total': product_total, 'embedded': product_embedded, 'missing': product_total - product_embedded},
            'aliases':  {'total': alias_total, 'embedded': alias_embedded, 'missing': alias_total - alias_embedded},
        })

    @action(detail=False, methods=['post'], url_path='backfill-embeddings')
    def backfill_embeddings(self, request):
        """Re-attempt embedding for every active product/alias that doesn't have one yet.
        Synchronous (not fire-and-forget) — this is an explicit, user-initiated action on
        a small catalog, so it's more useful to wait a second and report real counts than
        to say "queued" and leave the same invisibility problem this exists to fix."""
        from apps.message_intelligence.services.embedding_service import (
            embed_products_batch, embed_product_aliases_batch,
        )
        from apps.message_intelligence.models import ProductEmbedding, ProductAliasEmbedding

        visible_products = scope_queryset_to_visible_companies(
            Product.objects.filter(is_active=True),
            request.user,
            company_field='company',
        )
        visible_aliases = scope_queryset_to_visible_companies(
            ProductAlias.objects.filter(product__is_active=True),
            request.user,
            company_field='product__company',
        )

        missing_product_ids = list(
            visible_products
            .exclude(id__in=ProductEmbedding.objects.filter(embedding__isnull=False).values('product_id'))
            .values_list('id', flat=True)
        )
        missing_alias_ids = list(
            visible_aliases
            .exclude(id__in=ProductAliasEmbedding.objects.filter(embedding__isnull=False).values('alias_id'))
            .values_list('id', flat=True)
        )

        product_result = embed_products_batch(missing_product_ids) if missing_product_ids else \
            {'total': 0, 'embedded': 0, 'skipped': 0, 'errors': 0}
        alias_result = embed_product_aliases_batch(missing_alias_ids) if missing_alias_ids else \
            {'total': 0, 'embedded': 0, 'skipped': 0, 'errors': 0}

        return Response({'products': product_result, 'aliases': alias_result})

    @action(detail=False, methods=['get'], url_path='stats')
    def stats(self, request):
        start, end = _resolve_date_range(request)
        account_id = request.query_params.get('account')

        qs = Inquiry.objects.filter(first_seen_at__gte=start, first_seen_at__lt=end)
        qs = scope_queryset_to_visible_companies(qs, request.user, company_field='company')
        if account_id:
            visible_account = _visible_account_or_none(request.user, account_id)
            qs = qs.filter(account=visible_account) if visible_account else qs.none()

        product_ids = list(
            scope_queryset_to_visible_companies(
                Product.objects.filter(is_active=True),
                request.user,
                company_field='company',
            ).values_list('id', 'name', 'brand')
        )
        results = []
        for pk, name, brand in product_ids:
            wtb = qs.filter(inquiry_type='buy',
                            products__contains=[{'product_id': pk}]).count()
            wts = qs.filter(inquiry_type='sell',
                            products__contains=[{'product_id': pk}]).count()
            deals = qs.filter(status=InquiryStatus.DEAL_DONE,
                              products__contains=[{'product_id': pk}]).count()
            if wtb + wts + deals:
                results.append({
                    'product_id': pk,
                    'name': f'{brand} {name}'.strip(),
                    'wtb': wtb,
                    'wts': wts,
                    'deals': deals,
                })
        results.sort(key=lambda r: -(r['wtb'] + r['wts']))
        return Response(results)


class InquiryViewSet(viewsets.GenericViewSet,
                     mixins.ListModelMixin,
                     mixins.RetrieveModelMixin,
                     mixins.UpdateModelMixin):
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return InquiryDetailSerializer
        return InquirySerializer

    def get_queryset(self):
        qs = scope_queryset_to_visible_companies(
            Inquiry.objects.select_related('account', 'contact').prefetch_related('contact__role_tags').order_by('-first_seen_at'),
            self.request.user,
            company_field='company',
        )
        p = self.request.query_params

        if account_id := p.get('account'):
            visible_account = _visible_account_or_none(self.request.user, account_id)
            qs = qs.filter(account=visible_account) if visible_account else qs.none()
        if status := p.get('status'):
            qs = qs.filter(status=status)
        if inquiry_type := p.get('type'):
            qs = qs.filter(inquiry_type=inquiry_type)
        if source := p.get('source'):
            qs = qs.filter(source_type=source)
        if date := p.get('date'):
            try:
                from datetime import date as dt
                d = dt.fromisoformat(date)
                qs = qs.filter(first_seen_at__date=d)
            except ValueError:
                pass

        return qs

    def partial_update(self, request, *args, **kwargs):
        inquiry = self.get_object()
        status_val = request.data.get('status')
        remarks    = request.data.get('remarks')
        rating     = request.data.get('classification_rating')

        update_fields = ['updated_at']
        if status_val and status_val in InquiryStatus.values:
            inquiry.status = status_val
            update_fields.append('status')
            if status_val in (InquiryStatus.CLOSED, InquiryStatus.DEAL_DONE):
                inquiry.closed_at = now()
                update_fields.append('closed_at')
        if remarks is not None:
            inquiry.remarks = remarks
            update_fields.append('remarks')
        if rating is not None:
            try:
                rating = int(rating)
            except (TypeError, ValueError):
                return Response({'detail': 'classification_rating must be an integer 1-5'}, status=status.HTTP_400_BAD_REQUEST)
            if rating not in (1, 2, 3, 4, 5):
                return Response({'detail': 'classification_rating must be an integer 1-5'}, status=status.HTTP_400_BAD_REQUEST)
            inquiry.classification_rating = rating
            update_fields.append('classification_rating')

        inquiry.save(update_fields=update_fields)
        return Response(InquiryDetailSerializer(inquiry).data)

    @action(detail=True, methods=['get'], url_path='product-lines')
    def product_lines(self, request, pk=None):
        inquiry = self.get_object()
        products = inquiry.products or []
        trace_rows = {
            row.source_product_index: row
            for row in inquiry.tracked_products.select_related('product').all()
            if row.source_product_index is not None
        }

        rows = []
        for index, line in enumerate(products):
            if not isinstance(line, dict):
                rows.append({
                    'index': index,
                    'valid': False,
                    'error': 'Product line is not an object.',
                    'raw': line,
                })
                continue

            product = None
            product_id = line.get('product_id')
            if product_id:
                product = Product.objects.filter(pk=product_id, company=inquiry.company).first()
            if not product and line.get('canonical_name'):
                product = Product.objects.filter(
                    company=inquiry.company,
                    is_active=True,
                    name__iexact=str(line.get('canonical_name')).strip(),
                ).first()

            trace = trace_rows.get(index)
            rows.append({
                'index': index,
                'valid': True,
                'canonical_name': line.get('canonical_name') or '',
                'brand': line.get('brand') or '',
                'attributes': line.get('attributes') or {},
                'quantity': line.get('quantity'),
                'price': line.get('price'),
                'currency': line.get('currency') or '',
                'match_type': line.get('match_type') or '',
                'product_id': product.pk if product else None,
                'product_name': f'{product.brand} {product.name}'.strip() if product else '',
                'has_inventory_mapping': bool(product),
                'inquiry_product_id': trace.pk if trace else None,
                'decision_status': trace.decision_status if trace else '',
                'match_status': trace.match_status if trace else '',
                'can_create_product': not product and trace is None,
            })

        return Response({
            'inquiry': InquiryDetailSerializer(inquiry).data,
            'products': rows,
        })

    @action(detail=True, methods=['post'], url_path=r'product-lines/(?P<line_index>[^/.]+)/create-product')
    def create_product_from_line(self, request, pk=None, line_index=None):
        inquiry = self.get_object()
        try:
            from apps.trading.services.inquiry_product_service import create_manual_product_from_inquiry_line
            product, trace = create_manual_product_from_inquiry_line(
                inquiry,
                int(line_index),
                created_by=request.user,
                overrides={
                    'name': request.data.get('name'),
                    'brand': request.data.get('brand'),
                    'category': request.data.get('category'),
                    'sku': request.data.get('sku'),
                    'currency': request.data.get('currency'),
                },
            )
            invalidate_product_cache()
            _embed_product_in_background(product.pk)
        except Exception as exc:
            logger.exception(
                'InquiryViewSet.create_product_from_line | failed | inquiry_id=%s | index=%s',
                inquiry.pk,
                line_index,
            )
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        inquiry.refresh_from_db()
        return Response({
            'product': ProductSerializer(product).data,
            'inquiry_product': InquiryProductSerializer(trace).data,
            'inquiry': InquiryDetailSerializer(inquiry).data,
        }, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path=r'product-lines/(?P<line_index>[^/.]+)/create-inquiry')
    def create_inquiry_product_from_line(self, request, pk=None, line_index=None):
        inquiry = self.get_object()
        try:
            from apps.trading.services.inquiry_product_service import create_manual_inquiry_product_from_matched_line
            trace = create_manual_inquiry_product_from_matched_line(
                inquiry,
                int(line_index),
                created_by=request.user,
            )
        except Exception as exc:
            logger.exception(
                'InquiryViewSet.create_inquiry_product_from_line | failed | inquiry_id=%s | index=%s',
                inquiry.pk,
                line_index,
            )
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        inquiry.refresh_from_db()
        return Response({
            'inquiry_product': InquiryProductSerializer(trace).data,
            'inquiry': InquiryDetailSerializer(inquiry).data,
        }, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='correct-match')
    def correct_match(self, request, pk=None):
        """Manually override the AI's product match for one line item — for when a
        'closest match only' pick was actually exact. `products` is a plain JSONField
        list with no per-item id, so the frontend addresses a line by its array index.
        """
        inquiry = self.get_object()
        index = request.data.get('index')
        product_id = request.data.get('product_id')
        if index is None or product_id is None:
            return Response({'detail': 'index and product_id are required'}, status=status.HTTP_400_BAD_REQUEST)

        products = inquiry.products or []
        try:
            index = int(index)
            line = products[index]
        except (ValueError, TypeError, IndexError):
            return Response({'detail': 'invalid index'}, status=status.HTTP_400_BAD_REQUEST)

        product = _visible_product_or_none(request.user, product_id)
        if not product:
            return Response({'detail': 'product not found'}, status=status.HTTP_400_BAD_REQUEST)

        line['product_id'] = product.id
        line['match_type'] = 'exact'
        line['manually_corrected'] = True
        inquiry.products = products
        inquiry.save(update_fields=['products', 'updated_at'])
        return Response(InquiryDetailSerializer(inquiry).data)

    @action(detail=True, methods=['post'], url_path='verify-match')
    def verify_match(self, request, pk=None):
        """Manually ask the configured AI agent to audit one stock suggestion.

        This is intentionally read-only: it reports whether the shown stock suggestion
        matches the original message and AI summary, but never silently changes the
        stored inquiry product match.
        """
        inquiry = self.get_object()
        index = request.data.get('index')
        if index is None:
            return Response({'detail': 'index is required'}, status=status.HTTP_400_BAD_REQUEST)

        products = inquiry.products or []
        try:
            index = int(index)
            line = products[index]
        except (ValueError, TypeError, IndexError):
            return Response({'detail': 'invalid index'}, status=status.HTTP_400_BAD_REQUEST)
        if not isinstance(line, dict):
            return Response({'detail': 'invalid product line'}, status=status.HTTP_400_BAD_REQUEST)

        product_id = line.get('product_id')
        if not product_id:
            return Response({'detail': 'product line has no stock suggestion'}, status=status.HTTP_400_BAD_REQUEST)
        product = _visible_product_or_none(request.user, product_id)
        if not product:
            return Response({'detail': 'product not found'}, status=status.HTTP_400_BAD_REQUEST)
        if inquiry.company_id and product.company_id != inquiry.company_id:
            return Response({'detail': 'product does not belong to this inquiry company'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            from apps.trading.services.match_verification_service import verify_inquiry_match
            result = verify_inquiry_match(inquiry, line, product)
        except Exception:
            logger.exception(
                'InquiryViewSet.verify_match | failed | inquiry_id=%s | index=%s | product_id=%s',
                inquiry.pk,
                index,
                product_id,
            )
            return Response({'detail': 'match verification failed'}, status=status.HTTP_502_BAD_GATEWAY)

        return Response(result)

    @action(detail=False, methods=['post'], url_path='close-stale')
    def close_stale(self, request):
        """Bulk-close inquiries that have sat 'open' longer than a given age — the
        dashboard's "Close inquiries older than N hrs" housekeeping sweep. Only ever
        touches status=open records; anything already actioned (quoted, no_stock,
        closed, etc.) is left alone, so this can't undo someone else's status choice.
        """
        try:
            hours = float(request.data.get('hours'))
            if hours <= 0:
                raise ValueError
        except (TypeError, ValueError):
            return Response({'detail': 'hours must be a positive number'}, status=status.HTTP_400_BAD_REQUEST)

        cutoff = now() - timedelta(hours=hours)
        qs = Inquiry.objects.filter(status=InquiryStatus.OPEN, first_seen_at__lte=cutoff)
        qs = scope_queryset_to_visible_companies(qs, request.user, company_field='company')

        account_id = request.data.get('account')
        if account_id:
            visible_account = _visible_account_or_none(request.user, account_id)
            qs = qs.filter(account=visible_account) if visible_account else qs.none()

        closed_count = qs.update(status=InquiryStatus.CLOSED, closed_at=now())
        return Response({'closed': closed_count})

    @action(detail=False, methods=['get'], url_path='stats')
    def stats(self, request):
        start, end = _resolve_date_range(request)
        account_id = request.query_params.get('account')

        qs = Inquiry.objects.filter(first_seen_at__gte=start, first_seen_at__lt=end)
        qs = scope_queryset_to_visible_companies(qs, request.user, company_field='company')
        if account_id:
            visible_account = _visible_account_or_none(request.user, account_id)
            qs = qs.filter(account=visible_account) if visible_account else qs.none()

        missed_cutoff = now() - timedelta(minutes=60)

        totals = qs.aggregate(
            wtb_total  = Count('id', filter=Q(inquiry_type='buy')),
            wts_total  = Count('id', filter=Q(inquiry_type='sell')),
            open_count = Count('id', filter=Q(status=InquiryStatus.OPEN)),
            closed     = Count('id', filter=Q(status=InquiryStatus.CLOSED)),
            deal_done  = Count('id', filter=Q(status=InquiryStatus.DEAL_DONE)),
            missed     = Count('id', filter=Q(
                status=InquiryStatus.OPEN, first_seen_at__lte=missed_cutoff,
            )),
        )

        by_source = {
            src: {
                'wtb': qs.filter(source_type=src, inquiry_type='buy').count(),
                'wts': qs.filter(source_type=src, inquiry_type='sell').count(),
            }
            for src in ('direct', 'group', 'community')
        }

        # Hourly timeline for a single-day range; daily buckets for anything longer —
        # 24 hourly bars for a multi-week range would be either meaningless (all lumped
        # into "today") or absurdly wide (one bar per hour of every day), so the
        # granularity adapts to the selected range instead.
        timeline = []
        timeline_granularity = 'hourly' if (end - start) <= timedelta(days=1) else 'daily'
        if timeline_granularity == 'hourly':
            for hour in range(24):
                slot_start = start + timedelta(hours=hour)
                slot_end   = slot_start + timedelta(hours=1)
                if slot_start > now():
                    break
                row = qs.filter(first_seen_at__gte=slot_start, first_seen_at__lt=slot_end).aggregate(
                    wtb=Count('id', filter=Q(inquiry_type='buy')),
                    wts=Count('id', filter=Q(inquiry_type='sell')),
                )
                timeline.append({'hour': slot_start.strftime('%H:%M'), **row})
        else:
            day_start = start
            while day_start < end and day_start <= now():
                day_end = day_start + timedelta(days=1)
                row = qs.filter(first_seen_at__gte=day_start, first_seen_at__lt=day_end).aggregate(
                    wtb=Count('id', filter=Q(inquiry_type='buy')),
                    wts=Count('id', filter=Q(inquiry_type='sell')),
                )
                timeline.append({'hour': day_start.strftime('%b %d'), **row})
                day_start = day_end

        # Average response time (minutes) for closed/deal-done inquiries
        closed_qs = qs.filter(
            status__in=[InquiryStatus.CLOSED, InquiryStatus.DEAL_DONE],
            closed_at__isnull=False,
        )
        avg_response = None
        if closed_qs.exists():
            from django.db.models import Avg, ExpressionWrapper, DurationField, F as Fld
            avg_dur = closed_qs.aggregate(
                avg=Avg(ExpressionWrapper(
                    Fld('closed_at') - Fld('first_seen_at'),
                    output_field=DurationField(),
                ))
            )['avg']
            if avg_dur:
                avg_response = round(avg_dur.total_seconds() / 60, 1)

        deal_qs = qs.filter(status=InquiryStatus.DEAL_DONE, closed_at__isnull=False)
        avg_deal = None
        if deal_qs.exists():
            from django.db.models import Avg, ExpressionWrapper, DurationField, F as Fld
            avg_dur = deal_qs.aggregate(
                avg=Avg(ExpressionWrapper(
                    Fld('closed_at') - Fld('first_seen_at'),
                    output_field=DurationField(),
                ))
            )['avg']
            if avg_dur:
                avg_deal = round(avg_dur.total_seconds() / 60, 1)

        return Response({
            'today': {
                'wtb_total': totals['wtb_total'],
                'wts_total': totals['wts_total'],
                'open':      totals['open_count'],
                'closed':    totals['closed'],
                'deal_done': totals['deal_done'],
                'missed':    totals['missed'],
            },
            'by_source':            by_source,
            'avg_response_minutes': avg_response,
            'avg_deal_minutes':     avg_deal,
            'timeline':             timeline,
            'timeline_granularity': timeline_granularity,
            'range': {
                'date_from': start.date().isoformat(),
                'date_to':   (end - timedelta(days=1)).date().isoformat(),
            },
        })

    @action(detail=False, methods=['get'], url_path='open-feed')
    def open_feed(self, request):
        """
        Return today's inquiries for the live dashboard feed, optionally filtered by
        status/type/account. Supports explicit page/page_size paging and sort ordering.
        Legacy `limit` is still accepted as page 1/page_size for older clients.
        """
        account_id = request.query_params.get('account')
        status_val = request.query_params.get('status', InquiryStatus.OPEN)
        type_val   = request.query_params.get('type')
        sort_val   = request.query_params.get('sort', 'latest')

        try:
            page = int(request.query_params.get('page', 1))
            page_size = int(request.query_params.get('page_size', request.query_params.get('limit', 50)))
        except (TypeError, ValueError):
            raise ValidationError({'detail': 'page and page_size must be numeric.'})

        if page < 1:
            raise ValidationError({'detail': 'page must be 1 or greater.'})
        if page_size < 1:
            raise ValidationError({'detail': 'page_size must be 1 or greater.'})
        page_size = min(page_size, 200)

        sort_map = {
            'latest': '-first_seen_at',
            'oldest': 'first_seen_at',
            'recently_updated': '-updated_at',
            'least_recently_updated': 'updated_at',
        }
        if sort_val not in sort_map:
            raise ValidationError({'detail': f'Unsupported sort value: {sort_val}'})

        today = now().replace(hour=0, minute=0, second=0, microsecond=0)
        qs = Inquiry.objects.filter(first_seen_at__gte=today).select_related('account', 'contact')
        qs = scope_queryset_to_visible_companies(qs, request.user, company_field='company')

        if status_val and status_val != 'all':
            qs = qs.filter(status=status_val)
        if account_id:
            visible_account = _visible_account_or_none(request.user, account_id)
            qs = qs.filter(account=visible_account) if visible_account else qs.none()
        if type_val in ('buy', 'sell'):
            qs = qs.filter(inquiry_type=type_val)

        qs = qs.order_by(sort_map[sort_val], '-id')
        count = qs.count()
        offset = (page - 1) * page_size
        return Response({
            'count': count,
            'page': page,
            'page_size': page_size,
            'total_pages': (count + page_size - 1) // page_size if count else 1,
            'sort': sort_val,
            'results': InquirySerializer(qs[offset:offset + page_size], many=True).data,
        })

    @action(detail=False, methods=['get'], url_path='classification-activity')
    def classification_activity(self, request):
        """Summary of recent classification results — useful for diagnosing the pipeline."""
        from apps.trading.models import MessageClassification, InquiryMessage
        account_id = request.query_params.get('account')
        start, end = _resolve_date_range(request)

        qs = MessageClassification.objects.filter(classified_at__gte=start, classified_at__lt=end)
        qs = scope_queryset_to_visible_accounts(qs, request.user, account_field='message__account')
        if account_id:
            visible_account = _visible_account_or_none(request.user, account_id)
            qs = qs.filter(message__account=visible_account) if visible_account else qs.none()

        total      = qs.count()
        as_inquiry = qs.filter(is_inquiry=True).count()
        no_type    = qs.filter(is_inquiry=True, inquiry_type='').count()

        # Count how many inquiry-classified messages have no linked Inquiry record yet
        inquiry_mc_ids = list(
            qs.filter(is_inquiry=True).exclude(inquiry_type='')
            .values_list('message_id', flat=True)
        )
        linked_ids = set(
            InquiryMessage.objects.filter(message_id__in=inquiry_mc_ids)
            .values_list('message_id', flat=True)
        )
        pending = len([mid for mid in inquiry_mc_ids if mid not in linked_ids])

        # Last 10 classified with key fields
        recent = []
        for mc in qs.select_related('message').order_by('-classified_at')[:10]:
            recent.append({
                'id':            mc.pk,
                'message_id':    mc.message_id,
                'tags':          mc.tags,
                'is_inquiry':    mc.is_inquiry,
                'inquiry_type':  mc.inquiry_type,
                'summary':       mc.ai_summary,
                'classified_at': mc.classified_at.isoformat(),
            })

        return Response({
            'today': {
                'total':        total,
                'as_inquiry':   as_inquiry,
                'pending':      pending,
                'type_missing': no_type,
            },
            'recent': recent,
        })

    @action(detail=False, methods=['post'], url_path='retry-inquiries')
    def retry_inquiries(self, request):
        """
        Re-run process_inquiry for all MessageClassification records marked is_inquiry=True
        that have no linked Inquiry record. Fixes the gap when process_inquiry failed silently.
        """
        import traceback
        from apps.trading.models import MessageClassification, InquiryMessage
        from apps.trading.services.inquiry_service import process_inquiry

        account_id = request.data.get('account')

        # Find all inquiry classifications
        mc_qs = MessageClassification.objects.filter(
            is_inquiry=True,
        ).exclude(inquiry_type='').select_related(
            'message', 'message__account', 'message__chat', 'message__contact',
        )
        mc_qs = scope_queryset_to_visible_accounts(mc_qs, request.user, account_field='message__account')
        if account_id:
            visible_account = _visible_account_or_none(request.user, account_id)
            mc_qs = mc_qs.filter(message__account=visible_account) if visible_account else mc_qs.none()

        # Exclude those already linked to an Inquiry
        linked_message_ids = set(
            InquiryMessage.objects.filter(
                message_id__in=mc_qs.values_list('message_id', flat=True)
            ).values_list('message_id', flat=True)
        )

        created = errors = 0
        first_error = None
        for mc in mc_qs:
            if mc.message_id in linked_message_ids:
                continue
            try:
                process_inquiry(mc.message, mc)
                created += 1
            except Exception as exc:
                tb = traceback.format_exc()
                logger.exception(
                    'retry_inquiries | process_inquiry failed | mc_id=%s | message_id=%s',
                    mc.pk, mc.message_id,
                )
                if first_error is None:
                    first_error = f'{type(exc).__name__}: {exc}\n\n{tb}'
                errors += 1

        return Response({'created': created, 'errors': errors, 'first_error': first_error})

    @action(detail=False, methods=['post'], url_path='backfill-classify')
    def backfill_classify(self, request):
        """
        Classify recent inbound messages that have no classification yet.
        Restricted to messages < 24 h old — same policy as the live pipeline.
        Runs in background threads — returns immediately with a count of messages queued.
        """
        import threading
        from django.utils.timezone import now, timedelta
        from apps.whatsapp_bridge.models import WhatsAppMessage
        from apps.trading.models import MessageClassification

        limit      = min(int(request.data.get('limit', 10)), 50)
        account_id = request.data.get('account')
        cutoff     = now() - timedelta(hours=24)

        already_done = set(
            MessageClassification.objects.values_list('message_id', flat=True)
        )

        qs = (
            WhatsAppMessage.objects
            .filter(direction='inbound', message_time__gte=cutoff)
            .exclude(message_text='')
            .select_related('account', 'chat', 'contact')
            .order_by('-message_time')
        )
        qs = scope_queryset_to_visible_accounts(qs, request.user, account_field='account')
        if account_id:
            visible_account = _visible_account_or_none(request.user, account_id)
            qs = qs.filter(account=visible_account) if visible_account else qs.none()

        queued = 0
        for msg in qs[:200]:
            if msg.pk in already_done or queued >= limit:
                break
            # Spawn one thread per message — same pattern as ingestion pipeline
            def _run(m=msg):
                from django.db import connection
                try:
                    from apps.trading.services.classification_service import classify_message
                    classify_message(m)
                except Exception:
                    logger.exception('backfill_classify | failed | message_id=%s', m.pk)
                finally:
                    connection.close()
            threading.Thread(target=_run, daemon=True).start()
            queued += 1

        return Response({'queued': queued})


class InquiryProductViewSet(viewsets.GenericViewSet, mixins.ListModelMixin, mixins.RetrieveModelMixin):
    serializer_class = InquiryProductSerializer
    permission_classes = [IsAuthenticated]
    ordering_map = {
        'created_newest': ('-created_at', '-id'),
        'created_oldest': ('created_at', 'id'),
        'seen_newest': ('-first_seen_at', '-id'),
        'seen_oldest': ('first_seen_at', 'id'),
        'name_asc': ('canonical_name', 'id'),
        'name_desc': ('-canonical_name', '-id'),
        'decision': ('decision_status', '-created_at', '-id'),
        'match': ('match_status', '-created_at', '-id'),
    }

    def get_queryset(self):
        qs = (
            InquiryProduct.objects
            .select_related(
                'company',
                'inquiry',
                'source_message',
                'source_message__chat',
                'account',
                'contact',
                'company_contact',
                'product',
            )
        )
        qs = scope_queryset_to_visible_companies(qs, self.request.user, company_field='company')
        p = self.request.query_params

        if account_id := p.get('account'):
            visible_account = _visible_account_or_none(self.request.user, account_id)
            qs = qs.filter(account=visible_account) if visible_account else qs.none()
        if inquiry_type := p.get('type'):
            qs = qs.filter(inquiry_type=inquiry_type)
        if decision_status := p.get('decision_status'):
            qs = qs.filter(decision_status=decision_status)
        if match_status := p.get('match_status'):
            qs = qs.filter(match_status=match_status)
        if embedding_status := p.get('embedding_status'):
            qs = qs.filter(embedding_status=embedding_status)
        if product_state := p.get('product_state'):
            if product_state == 'mapped':
                qs = qs.filter(product__isnull=False)
            elif product_state == 'unmapped':
                qs = qs.filter(product__isnull=True)
        if date := p.get('date'):
            try:
                from datetime import date as dt
                d = dt.fromisoformat(date)
                qs = qs.filter(first_seen_at__date=d)
            except ValueError:
                pass
        search = (p.get('search') or '').strip()
        if search:
            qs = qs.filter(
                Q(canonical_name__icontains=search)
                | Q(normalized_name__icontains=search)
                | Q(original_text__icontains=search)
                | Q(product__name__icontains=search)
                | Q(product__brand__icontains=search)
                | Q(contact__display_name__icontains=search)
                | Q(contact__phone_number__icontains=search)
                | Q(source_message__message_text__icontains=search)
            )
        ordering = p.get('ordering') or 'created_newest'
        qs = qs.order_by(*self.ordering_map.get(ordering, self.ordering_map['created_newest']))
        return qs

    @action(detail=False, methods=['get'], url_path='search-embeddings')
    def search_embeddings(self, request):
        """Embedding-based search over extracted inquiry product lines.

        Mapped rows reuse inventory Product/ProductAlias embeddings. Unmapped rows use
        InquiryProduct.embedding because there is no inventory product yet.
        """
        from pgvector import Vector
        from apps.ai_providers.manager import ai_manager

        query = request.query_params.get('q', '').strip()
        if not query:
            return Response({'results': []})

        try:
            top_k = int(request.query_params.get('top_k', 10))
        except (TypeError, ValueError):
            top_k = 10
        top_k = max(1, min(top_k, 50))

        visible_ids = list(self.get_queryset().values_list('id', flat=True))
        if not visible_ids:
            return Response({'results': []})

        try:
            query_vec = ai_manager.embed(query)
            query_vec_text = Vector(query_vec).to_text()
            with _db_conn.cursor() as cursor:
                cursor.execute(
                    """
                    WITH scored AS (
                        SELECT ip.id AS inquiry_product_id, (pe.embedding <=> %(qv)s::vector) AS distance
                        FROM trading_inquiry_product ip
                        JOIN product_embedding pe ON pe.product_id = ip.product_id
                        JOIN trading_product p ON p.id = ip.product_id
                        WHERE ip.id = ANY(%(ids)s)
                          AND ip.product_id IS NOT NULL
                          AND pe.embedding IS NOT NULL
                          AND p.is_active = TRUE

                        UNION ALL

                        SELECT ip.id AS inquiry_product_id, (pae.embedding <=> %(qv)s::vector) AS distance
                        FROM trading_inquiry_product ip
                        JOIN trading_product_alias pa ON pa.product_id = ip.product_id
                        JOIN product_alias_embedding pae ON pae.alias_id = pa.id
                        JOIN trading_product p ON p.id = ip.product_id
                        WHERE ip.id = ANY(%(ids)s)
                          AND ip.product_id IS NOT NULL
                          AND pae.embedding IS NOT NULL
                          AND p.is_active = TRUE

                        UNION ALL

                        SELECT ip.id AS inquiry_product_id, (ip.embedding <=> %(qv)s::vector) AS distance
                        FROM trading_inquiry_product ip
                        WHERE ip.id = ANY(%(ids)s)
                          AND ip.product_id IS NULL
                          AND ip.embedding IS NOT NULL
                    )
                    SELECT inquiry_product_id, MIN(distance) AS best_distance
                    FROM scored
                    GROUP BY inquiry_product_id
                    ORDER BY best_distance ASC
                    LIMIT %(top_k)s
                    """,
                    {'qv': query_vec_text, 'ids': visible_ids, 'top_k': top_k},
                )
                rows = cursor.fetchall()
        except Exception as exc:
            logger.warning('inquiry_product_search_embeddings | query=%r failed: %s', query, exc)
            return Response({'detail': 'Embedding search unavailable'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        products_by_id = InquiryProduct.objects.filter(
            pk__in=[row_id for row_id, _ in rows],
        ).select_related(
            'company',
            'inquiry',
            'source_message',
            'source_message__chat',
            'account',
            'contact',
            'company_contact',
            'product',
        ).in_bulk()
        results = [
            {
                'inquiry_product': InquiryProductSerializer(products_by_id[row_id]).data,
                'distance': round(float(distance), 4),
            }
            for row_id, distance in rows
            if row_id in products_by_id
        ]
        return Response({'results': results})

    @action(detail=False, methods=['post'], url_path='backfill-embeddings')
    def backfill_embeddings(self, request):
        """Repair InquiryProduct embedding state for visible rows.

        Mapped rows are marked skipped because search uses inventory embeddings.
        Unmapped rows receive their own InquiryProduct embedding.
        """
        from apps.message_intelligence.services.embedding_service import embed_inquiry_products_batch
        from apps.trading.models import InquiryProductEmbeddingStatus

        try:
            limit = int(request.data.get('limit', 250))
        except (TypeError, ValueError):
            return Response({'detail': 'limit must be an integer'}, status=status.HTTP_400_BAD_REQUEST)
        if limit <= 0 or limit > 1000:
            return Response({'detail': 'limit must be between 1 and 1000'}, status=status.HTTP_400_BAD_REQUEST)

        qs = self.get_queryset()
        mapped_updated = qs.filter(product__isnull=False).exclude(
            embedding_status=InquiryProductEmbeddingStatus.SKIPPED,
        ).update(
            embedding=None,
            embedding_model='',
            embedding_metadata={'source': 'inventory_product_embedding'},
            embedding_status=InquiryProductEmbeddingStatus.SKIPPED,
            embedding_error='',
        )

        unmapped_ids = list(
            qs.filter(product__isnull=True)
            .exclude(embedding_status=InquiryProductEmbeddingStatus.EMBEDDED)
            .order_by('-created_at')
            .values_list('id', flat=True)[:limit]
        )
        result = embed_inquiry_products_batch(unmapped_ids) if unmapped_ids else {
            'total': 0,
            'embedded': 0,
            'skipped': 0,
            'errors': 0,
        }
        return Response({
            'mapped_marked_inventory_backed': mapped_updated,
            'unmapped': result,
        })


class MessageClassificationViewSet(viewsets.GenericViewSet, mixins.ListModelMixin):
    serializer_class   = MessageClassificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = MessageClassification.objects.order_by('-classified_at')
        qs = scope_queryset_to_visible_accounts(qs, self.request.user, account_field='message__account')
        if message_id := self.request.query_params.get('message'):
            qs = qs.filter(message_id=message_id)
        return qs


class PromptConfigViewSet(viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated]

    def list(self, request):
        """Return all prompt configs with their current body (or default if not saved yet)."""
        defaults = {
            PromptConfig.KEY_PRODUCT_EXTRACTION:     (PRODUCT_EXTRACTION_DEFAULT,     'Product Extraction (bulk import)'),
            PromptConfig.KEY_INQUIRY_CLASSIFICATION: (INQUIRY_CLASSIFICATION_DEFAULT, 'Inquiry Classification (live messages)'),
            PromptConfig.KEY_INQUIRY_CLASSIFICATION_V1: (INQUIRY_CLASSIFICATION_DEFAULT, 'Inquiry Classification V1 (live messages)'),
            PromptConfig.KEY_INQUIRY_EXTRACTION_V2:  (INQUIRY_EXTRACTION_V2_DEFAULT,  'Inquiry Extraction V2 (pass 1)'),
            PromptConfig.KEY_INQUIRY_MATCH_DECISION_V2: (INQUIRY_MATCH_DECISION_V2_DEFAULT, 'Inquiry Match Decision V2 (pass 2)'),
            PromptConfig.KEY_INVENTORY_UPDATE:       (INVENTORY_UPDATE_DEFAULT,       'Inventory Update (bulk qty + price)'),
            PromptConfig.KEY_PRICE_LIST_FORMAT:      (PRICE_LIST_FORMAT_DEFAULT,      'Price List Formatting (WhatsApp send)'),
            PromptConfig.KEY_QTY_COST_UPDATE:        (QTY_COST_UPDATE_DEFAULT,        'Qty & Cost Update (Product Price Update page)'),
            PromptConfig.KEY_SALE_PRICE_UPDATE:      (SALE_PRICE_UPDATE_DEFAULT,      'Sale Price Update (Product Price Update page)'),
            PromptConfig.KEY_MATCH_VERIFICATION:     (MATCH_VERIFICATION_DEFAULT,     'Inquiry Match Verification (manual review)'),
        }
        company = default_company_for_user(request.user)
        saved = {p.key: p for p in PromptConfig.objects.filter(company=company)}
        result = []
        for key, (default_body, label) in defaults.items():
            obj = saved.get(key)
            result.append({
                'key':        key,
                'label':      label,
                'body':       obj.body if obj else default_body,
                'is_default': obj is None,
                'updated_at': obj.updated_at.isoformat() if obj else None,
            })
        return Response(result)

    @action(detail=False, methods=['get', 'patch'], url_path='active-agent')
    def active_agent(self, request):
        """GET active agent config info + pricing. PATCH to update pricing."""
        from apps.ai_providers.models import AIProviderConfig as APC

        try:
            config = APC.objects.get(capability=APC.CAPABILITY_AGENT, is_active=True)
        except APC.DoesNotExist:
            return Response({'error': 'No active agent provider configured.'}, status=status.HTTP_404_NOT_FOUND)

        if request.method == 'PATCH':
            extra = config.extra_config or {}
            for field in ('input_price_per_1m', 'output_price_per_1m'):
                val = request.data.get(field)
                if val is not None:
                    try:
                        extra[field] = float(val)
                    except (TypeError, ValueError):
                        return Response({'error': f'Invalid value for {field}'}, status=status.HTTP_400_BAD_REQUEST)
            config.extra_config = extra
            config.save(update_fields=['extra_config', 'updated_at'])

        extra = config.extra_config or {}
        return Response({
            'display_name':         config.display_name,
            'provider':             config.provider,
            'model':                config.model,
            'input_price_per_1m':   extra.get('input_price_per_1m'),
            'output_price_per_1m':  extra.get('output_price_per_1m'),
        })

    def partial_update(self, request, pk=None):
        """Save (upsert) a prompt by key."""
        key  = pk
        body = (request.data.get('body') or '').strip()
        if not body:
            return Response({'error': 'body is required'}, status=status.HTTP_400_BAD_REQUEST)

        defaults_map = {
            PromptConfig.KEY_PRODUCT_EXTRACTION:     'Product Extraction (bulk import)',
            PromptConfig.KEY_INQUIRY_CLASSIFICATION: 'Inquiry Classification (live messages)',
            PromptConfig.KEY_INQUIRY_CLASSIFICATION_V1: 'Inquiry Classification V1 (live messages)',
            PromptConfig.KEY_INQUIRY_EXTRACTION_V2:  'Inquiry Extraction V2 (pass 1)',
            PromptConfig.KEY_INQUIRY_MATCH_DECISION_V2: 'Inquiry Match Decision V2 (pass 2)',
            PromptConfig.KEY_INVENTORY_UPDATE:       'Inventory Update (bulk qty + price)',
            PromptConfig.KEY_PRICE_LIST_FORMAT:      'Price List Formatting (WhatsApp send)',
            PromptConfig.KEY_QTY_COST_UPDATE:        'Qty & Cost Update (Product Price Update page)',
            PromptConfig.KEY_SALE_PRICE_UPDATE:      'Sale Price Update (Product Price Update page)',
            PromptConfig.KEY_MATCH_VERIFICATION:     'Inquiry Match Verification (manual review)',
        }
        label = defaults_map.get(key, key)
        company = default_company_for_user(request.user)
        obj, _ = PromptConfig.objects.update_or_create(
            company=company,
            key=key,
            defaults={'body': body, 'label': label},
        )
        return Response({
            'key':        obj.key,
            'label':      obj.label,
            'body':       obj.body,
            'is_default': False,
            'updated_at': obj.updated_at.isoformat(),
        })

    def destroy(self, request, pk=None):
        """Reset a prompt to its default by deleting the saved override."""
        PromptConfig.objects.filter(company=default_company_for_user(request.user), key=pk).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AgentCallLogViewSet(viewsets.GenericViewSet, mixins.ListModelMixin):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = AgentCallLog.objects.all()
        p  = self.request.query_params
        if purpose := p.get('purpose'):
            qs = qs.filter(purpose=purpose)
        if success := p.get('success'):
            qs = qs.filter(success=success == 'true')
        return qs[:200]

    def list(self, request, *args, **kwargs):
        from apps.ai_providers.manager import ai_manager
        qs = self.get_queryset()

        # Resolve pricing for cost calculation
        input_price = output_price = None
        try:
            config = ai_manager.active_config('agent')
            if config:
                extra = config.extra_config or {}
                input_price  = extra.get('input_price_per_1m')
                output_price = extra.get('output_price_per_1m')
        except Exception:
            pass

        rows = []
        for log in qs:
            input_cost = output_cost = None
            if input_price is not None:
                input_cost = round((log.input_tokens / 1_000_000) * input_price, 8)
            if output_price is not None:
                output_cost = round((log.output_tokens / 1_000_000) * output_price, 8)

            rows.append({
                'id':           log.pk,
                'purpose':      log.purpose,
                'provider':     log.provider,
                'model':        log.model,
                'input_tokens':  log.input_tokens,
                'output_tokens': log.output_tokens,
                'input_cost':   input_cost,
                'output_cost':  output_cost,
                'duration_ms':  log.duration_ms,
                'success':      log.success,
                'error':        log.error,
                'classification_version': log.classification_version,
                'wa_message_id': log.wa_message_id,
                'created_at':   log.created_at.isoformat(),
                'messages':     log.messages,
                'response':     log.response,
            })
        return Response(rows)


class AiParsingLogPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = 'page_size'
    max_page_size = 100
    page_query_param = 'page'


class AiParsingLogViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AiParsingLogSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = AiParsingLogPagination

    def get_queryset(self):
        qs = AiParsingLog.objects.select_related('account', 'chat', 'message').order_by('-created_at')
        qs = scope_queryset_to_visible_accounts(qs, self.request.user, account_field='account')
        p = self.request.query_params
        if account_id := p.get('account'):
            visible_account = _visible_account_or_none(self.request.user, account_id)
            qs = qs.filter(account=visible_account) if visible_account else qs.none()
        if status_ := p.get('status'):
            qs = qs.filter(status=status_)
        if reason := p.get('skip_reason'):
            qs = qs.filter(skip_reason=reason)
        return qs


class AiParseV2LogViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AiParseV2LogSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = AiParsingLogPagination

    def get_queryset(self):
        qs = (
            AiParseV2Log.objects
            .select_related('account', 'chat', 'message', 'classification')
            .order_by('-created_at')
        )
        qs = scope_queryset_to_visible_accounts(qs, self.request.user, account_field='account')
        p = self.request.query_params
        if account_id := p.get('account'):
            visible_account = _visible_account_or_none(self.request.user, account_id)
            qs = qs.filter(account=visible_account) if visible_account else qs.none()
        if status_ := p.get('status'):
            qs = qs.filter(status=status_)
        return qs


class BuyingInquiryViewSet(viewsets.ModelViewSet):
    serializer_class = BuyingInquirySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = (
            BuyingInquiry.objects
            .select_related('account')
            .prefetch_related('supplier_quotes__supplier')
            .order_by('-created_at')
        )
        qs = scope_queryset_to_visible_accounts(qs, self.request.user, account_field='account')
        p = self.request.query_params
        if account_id := p.get('account'):
            visible_account = _visible_account_or_none(self.request.user, account_id)
            qs = qs.filter(account=visible_account) if visible_account else qs.none()
        if status_ := p.get('status'):
            qs = qs.filter(status=status_)
        return qs

    def perform_create(self, serializer):
        from apps.whatsapp_bridge.models import WhatsAppContact
        account = _visible_account_or_none(self.request.user, self.request.data.get('account'))
        if not account:
            raise ValidationError({'account': 'A visible account is required to create a buying inquiry.'})
        inquiry = serializer.save(account=account)
        # Auto-populate a supplier card for every contact currently tagged 'supplier' or
        # 'both' on this account — the user can add/remove individual suppliers afterward.
        suppliers = WhatsAppContact.objects.filter(account=inquiry.account, role_tags__role='supplier').distinct()
        SupplierQuote.objects.bulk_create([
            SupplierQuote(buying_inquiry=inquiry, supplier=s) for s in suppliers
        ])

    @action(detail=True, methods=['post'], url_path='add-supplier')
    def add_supplier(self, request, pk=None):
        from apps.whatsapp_bridge.models import WhatsAppContact
        inquiry = self.get_object()
        supplier_id = request.data.get('supplier_id')
        if not supplier_id:
            return Response({'error': 'supplier_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            supplier = WhatsAppContact.objects.get(pk=supplier_id, account=inquiry.account)
        except WhatsAppContact.DoesNotExist:
            return Response({'error': 'Supplier not found for this account'}, status=status.HTTP_404_NOT_FOUND)
        quote, _ = SupplierQuote.objects.get_or_create(buying_inquiry=inquiry, supplier=supplier)
        return Response(SupplierQuoteSerializer(quote).data, status=status.HTTP_201_CREATED)


class SupplierQuoteViewSet(
    viewsets.GenericViewSet,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
):
    serializer_class = SupplierQuoteSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return scope_queryset_to_visible_accounts(
            SupplierQuote.objects.select_related('supplier', 'buying_inquiry'),
            self.request.user,
            account_field='buying_inquiry__account',
        )

    @action(detail=True, methods=['post'], url_path='ask')
    def ask(self, request, pk=None):
        quote = self.get_object()
        quote.status = 'asked'
        quote.asked_at = now()
        quote.save(update_fields=['status', 'asked_at', 'updated_at'])
        return Response(SupplierQuoteSerializer(quote).data)


class ReportViewSet(viewsets.ViewSet):
    """Cross-cutting reporting endpoints — not tied to one model's CRUD surface the
    way ProductViewSet/InquiryViewSet are, so it lives on its own instead of being
    bolted onto whichever viewset happens to own the most of the numbers."""
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'], url_path='summary')
    def summary(self, request):
        """
        Headline counts for the Reports > Summary page: messages received, inquiries
        created, WTB/WTS split, how many inquiries matched something in our own
        catalog, and how many only got a 'near' (not exact) match. Filtered by the
        same account + date_from/date_to params as every other report/stats endpoint.

        'Related to own stock' means at least one line item in the inquiry's
        `products` resolved to a real product_id — i.e. we actually carry that SKU —
        regardless of that product's *current* qty (qty could have changed since the
        inquiry was raised; the AI only ever offers qty>0 products as matches at
        classification time, so a resolved product_id already reflects "in stock
        then"). 'Near matches' means at least one line item was flagged match_type
        'near' (a plausible but not confident match) rather than 'exact'. Both are
        also broken out by WTB/WTS (total_wtb_own_stock, total_wts_own_stock,
        total_wtb_near_match, total_wts_near_match).
        """
        from apps.whatsapp_bridge.models import WhatsAppMessage

        start, end = _resolve_date_range(request)
        account_id = request.query_params.get('account')

        messages_qs = WhatsAppMessage.objects.filter(
            direction='inbound', message_time__gte=start, message_time__lt=end,
        )
        inquiries_qs = Inquiry.objects.filter(first_seen_at__gte=start, first_seen_at__lt=end)
        messages_qs = scope_queryset_to_visible_accounts(messages_qs, request.user, account_field='account')
        inquiries_qs = scope_queryset_to_visible_companies(inquiries_qs, request.user, company_field='company')
        if account_id:
            visible_account = _visible_account_or_none(request.user, account_id)
            if visible_account:
                messages_qs = messages_qs.filter(account=visible_account)
                inquiries_qs = inquiries_qs.filter(account=visible_account)
            else:
                messages_qs = messages_qs.none()
                inquiries_qs = inquiries_qs.none()

        totals = inquiries_qs.aggregate(
            wtb_total=Count('id', filter=Q(inquiry_type='buy')),
            wts_total=Count('id', filter=Q(inquiry_type='sell')),
        )

        # Both remaining counts (and their WTB/WTS breakdowns) depend on inspecting
        # each inquiry's `products` JSON list (no per-item rows to aggregate over in
        # SQL) — one pass over the already date/account-filtered set, not the whole
        # table.
        own_stock_count = 0
        near_match_count = 0
        own_stock_wtb = own_stock_wts = 0
        near_match_wtb = near_match_wts = 0
        for inquiry_type, products in inquiries_qs.values_list('inquiry_type', 'products'):
            has_stock_match = False
            has_near_match = False
            for item in (products or []):
                if item.get('product_id') is not None:
                    has_stock_match = True
                if item.get('match_type') == 'near':
                    has_near_match = True
            if has_stock_match:
                own_stock_count += 1
                if inquiry_type == 'buy':
                    own_stock_wtb += 1
                elif inquiry_type == 'sell':
                    own_stock_wts += 1
            if has_near_match:
                near_match_count += 1
                if inquiry_type == 'buy':
                    near_match_wtb += 1
                elif inquiry_type == 'sell':
                    near_match_wts += 1

        status_counts = {
            row['status']: row['c']
            for row in inquiries_qs.values('status').annotate(c=Count('id'))
        }
        status_breakdown = [
            {'status': value, 'label': label, 'count': status_counts.get(value, 0)}
            for value, label in InquiryStatus.choices
        ]

        return Response({
            'total_messages_received':  messages_qs.count(),
            'total_inquiries_created':  inquiries_qs.count(),
            'total_wtb':                totals['wtb_total'],
            'total_wts':                totals['wts_total'],
            'total_own_stock_matches':  own_stock_count,
            'total_near_matches':       near_match_count,
            'total_wtb_own_stock':      own_stock_wtb,
            'total_wts_own_stock':      own_stock_wts,
            'total_wtb_near_match':     near_match_wtb,
            'total_wts_near_match':     near_match_wts,
            'status_breakdown':         status_breakdown,
            'range': {
                'date_from': start.date().isoformat(),
                'date_to':   (end - timedelta(days=1)).date().isoformat(),
            },
        })

    @action(detail=False, methods=['get'], url_path='inventory-product-mentions')
    def inventory_product_mentions(self, request):
        """Item-wise WTB/WTS mention counts for inventory products.

        Counts are based on InquiryProduct trace rows, not raw Inquiry.products JSON,
        so the report only reflects product mentions that have been saved/traced.
        """
        start, end = _resolve_date_range(request)
        search = (request.query_params.get('search') or '').strip()
        limit = min(max(int(request.query_params.get('limit') or 100), 1), 500)

        qs = (
            InquiryProduct.objects
            .filter(
                product__isnull=False,
                first_seen_at__gte=start,
                first_seen_at__lt=end,
            )
            .select_related('product')
        )
        qs = scope_queryset_to_visible_companies(qs, request.user, company_field='company')
        if search:
            qs = qs.filter(
                Q(product__name__icontains=search)
                | Q(product__brand__icontains=search)
                | Q(canonical_name__icontains=search)
            )

        grouped = (
            qs.values(
                'product_id',
                'product__brand',
                'product__name',
                'product__sku',
                'product__qty',
                'product__sale_price',
                'product__currency',
            )
            .annotate(
                wtb_count=Count('id', filter=Q(inquiry_type='buy')),
                wts_count=Count('id', filter=Q(inquiry_type='sell')),
                total_count=Count('id'),
                first_seen=Min('first_seen_at'),
                last_seen=Max('first_seen_at'),
            )
            .order_by('-total_count', '-last_seen', 'product__name')[:limit]
        )

        rows = [
            {
                'product_id': row['product_id'],
                'brand': row['product__brand'] or '',
                'name': row['product__name'] or '',
                'sku': row['product__sku'] or '',
                'qty': row['product__qty'],
                'sale_price': row['product__sale_price'],
                'currency': row['product__currency'] or '',
                'wtb_count': row['wtb_count'],
                'wts_count': row['wts_count'],
                'total_count': row['total_count'],
                'first_seen': row['first_seen'],
                'last_seen': row['last_seen'],
            }
            for row in grouped
        ]
        totals = qs.aggregate(
            total_mentions=Count('id'),
            total_wtb=Count('id', filter=Q(inquiry_type='buy')),
            total_wts=Count('id', filter=Q(inquiry_type='sell')),
            products=Count('product_id', distinct=True),
        )
        return Response({
            'results': rows,
            'summary': totals,
            'range': {
                'date_from': start.date().isoformat(),
                'date_to': (end - timedelta(days=1)).date().isoformat(),
            },
        })


class TradingSettingsViewSet(viewsets.ViewSet):
    """Hot-settable plain-text/toggle UI settings for the trading desk — not AI
    prompts (see PromptConfig for those, which are LLM system prompts), just small
    values the frontend reads when composing something itself. Backed by the
    generic chatlens_core.SystemSettings key/value store rather than a dedicated
    model, since it's exactly the "misc named setting" case that table exists for."""
    permission_classes = [IsAuthenticated]

    WTS_REPLY_KEY = 'trading_wts_reply_settings'
    WTS_REPLY_DEFAULTS = {
        'heading':          'WTS',
        'send_flag':        True,
        'flag_position':    'prefix',
        'send_color':       True,
        'color_position':   'prefix',
        'send_currency':    True,
        'currency_position': 'prefix',
        'currency':         'AED',
        'send_secondary_currency': False,
        'secondary_currency': 'USD',
        'secondary_currency_rate': 0.27,
        'sort_by':          'original',
        'heading_blank_lines': 0,
    }
    _POSITIONS = {'prefix', 'suffix'}
    _SORT_OPTIONS = {'original', 'color', 'storage', 'region', 'flag'}
    _MAX_HEADING_BLANK_LINES = 3

    @action(detail=False, methods=['get', 'put'], url_path='wts-reply')
    def wts_reply(self, request):
        """heading: text prefixed to the WhatsApp price-reply composed from the
        Trading dashboard. send_flag/send_color: whether each product's Flag/Color
        attribute (§ ProductAttribute) gets folded into that reply as an emoji, and
        flag_position/color_position (prefix|suffix) where relative to the product
        name. send_currency/currency/currency_position: whether a currency label is
        attached to the price, which one, and on which side. send_secondary_currency/
        secondary_currency/secondary_currency_rate: an optional second, converted
        amount shown alongside the primary price (converted = price * rate). sort_by:
        'original' (the order items appear in the inquiry) or one of
        color/storage/region/flag to group/order lines by that ProductAttribute.
        heading_blank_lines: extra blank lines between the heading and the first
        item, 0-3."""
        import json
        from apps.chatlens_core.models import SystemSettings

        if request.method == 'GET':
            obj = SystemSettings.objects.filter(
                company=default_company_for_user(request.user),
                key=self.WTS_REPLY_KEY,
            ).first()
            saved = {}
            if obj and obj.value:
                try:
                    saved = json.loads(obj.value)
                except (json.JSONDecodeError, TypeError):
                    saved = {}
            return Response({**self.WTS_REPLY_DEFAULTS, **saved})

        def position(field):
            val = request.data.get(field)
            return val if val in self._POSITIONS else self.WTS_REPLY_DEFAULTS[field]

        def positive_float(value, default):
            try:
                f = float(value)
                return f if f > 0 else default
            except (TypeError, ValueError):
                return default

        def clamped_int(value, default, lo, hi):
            try:
                n = int(value)
            except (TypeError, ValueError):
                return default
            return max(lo, min(hi, n))

        heading = (request.data.get('heading') or '').strip() or self.WTS_REPLY_DEFAULTS['heading']
        currency = (request.data.get('currency') or '').strip() or self.WTS_REPLY_DEFAULTS['currency']
        secondary_currency = (request.data.get('secondary_currency') or '').strip() or self.WTS_REPLY_DEFAULTS['secondary_currency']
        payload = {
            'heading':           heading,
            'send_flag':         bool(request.data.get('send_flag', True)),
            'flag_position':     position('flag_position'),
            'send_color':        bool(request.data.get('send_color', True)),
            'color_position':    position('color_position'),
            'send_currency':     bool(request.data.get('send_currency', True)),
            'currency_position': position('currency_position'),
            'currency':          currency,
            'send_secondary_currency': bool(request.data.get('send_secondary_currency', False)),
            'secondary_currency': secondary_currency,
            'secondary_currency_rate': positive_float(
                request.data.get('secondary_currency_rate'),
                self.WTS_REPLY_DEFAULTS['secondary_currency_rate'],
            ),
            'sort_by': request.data.get('sort_by') if request.data.get('sort_by') in self._SORT_OPTIONS else self.WTS_REPLY_DEFAULTS['sort_by'],
            'heading_blank_lines': clamped_int(
                request.data.get('heading_blank_lines'),
                self.WTS_REPLY_DEFAULTS['heading_blank_lines'],
                0, self._MAX_HEADING_BLANK_LINES,
            ),
        }
        SystemSettings.objects.update_or_create(
            company=default_company_for_user(request.user),
            key=self.WTS_REPLY_KEY,
            defaults={
                'value': json.dumps(payload),
                'description': 'WhatsApp price-reply composition settings for the Trading dashboard (heading text, Flag/Color attribute prefix/suffix, primary + optional secondary currency label).',
            },
        )
        return Response(payload)

    @action(detail=False, methods=['get', 'put'], url_path='inquiry-products')
    def inquiry_products(self, request):
        from apps.trading.services.trading_settings_service import (
            get_inquiry_product_save_settings,
            save_inquiry_product_save_settings,
        )

        company = default_company_for_user(request.user)
        if request.method == 'GET':
            return Response(get_inquiry_product_save_settings(company))

        try:
            payload = save_inquiry_product_save_settings(
                company,
                (request.data.get('mode') or '').strip(),
            )
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(payload)

    @action(detail=False, methods=['get', 'put'], url_path='v2-matching-thresholds')
    def v2_matching_thresholds(self, request):
        from apps.trading.services.trading_settings_service import (
            get_v2_matching_settings,
            save_v2_matching_settings,
        )

        company = default_company_for_user(request.user)
        if request.method == 'GET':
            return Response(get_v2_matching_settings(company))

        try:
            payload = save_v2_matching_settings(company, request.data)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(payload)

    @action(detail=False, methods=['get', 'put'], url_path='v2-matching')
    def v2_matching(self, request):
        return self.v2_matching_thresholds(request)


class ProductPriceUpdateViewSet(viewsets.ViewSet):
    """New, independent qty/cost and sale-price update pipeline for the "Product Price
    Update" page — deliberately separate from ProductViewSet.parse_inventory/
    bulk_update_inventory (the existing combined-textbox Update Inventory feature on
    the Products page) rather than a replacement for it, per explicit instruction.

    Two distinct two-list AI matching processes, each with its own prompt
    (PromptConfig.KEY_QTY_COST_UPDATE / KEY_SALE_PRICE_UPDATE): a supplier's qty/cost
    list matched against our own inventory, and a separate external sale-price list
    matched against our own inventory. Kept as two processes, not one combined
    textbox, because the two source lists come from different parties with different
    naming conventions — mixing them the way the older feature does makes the AI's
    matching job harder, not easier."""
    permission_classes = [IsAuthenticated]

    def _parse(self, request, prompt_key, prompt_default):
        text = (request.data.get('text') or '').strip()
        if not text:
            return Response({'error': 'text is required'}, status=status.HTTP_400_BAD_REQUEST)

        from apps.trading.services.price_update_service import parse_against_inventory

        try:
            items = parse_against_inventory(
                text,
                prompt_key,
                prompt_default,
                company=default_company_for_user(request.user),
            )
            return Response({'items': items})
        except Exception as exc:
            logger.exception('ProductPriceUpdateViewSet | parse failed | prompt_key=%s', prompt_key)
            return Response({'error': str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _apply(self, request, fields, zero_unmatched_qty=False):
        """fields: iterable of (payload_key, product_attr) pairs to copy across,
        e.g. [('qty', 'qty'), ('cost_price', 'cost_price')]."""
        from apps.trading.services.price_update_service import apply_items_to_inventory

        items = request.data.get('items') or []
        result = apply_items_to_inventory(
            items,
            fields,
            zero_unmatched_qty=zero_unmatched_qty,
            company=default_company_for_user(request.user),
        )
        return Response(result)

    @action(detail=False, methods=['post'], url_path='parse-qty-cost')
    def parse_qty_cost(self, request):
        """Supplier qty/cost list → matched against our own inventory."""
        return self._parse(request, PromptConfig.KEY_QTY_COST_UPDATE, QTY_COST_UPDATE_DEFAULT)

    @action(detail=False, methods=['post'], url_path='apply-qty-cost')
    def apply_qty_cost(self, request):
        # The qty/cost list is a supplier's current stock — anything we hold that
        # they didn't list this time is no longer available from them, so it's
        # zeroed out rather than left showing stale (possibly nonzero) qty.
        return self._apply(request, [('qty', 'qty'), ('cost_price', 'cost_price')], zero_unmatched_qty=True)

    @action(detail=False, methods=['post'], url_path='preview-zero-qty')
    def preview_zero_qty(self, request):
        """Dry-run for the qty/cost apply's zero-out step — returns which active
        products would have qty set to 0 by this exact item list, without writing
        anything, so the frontend can confirm with the user before applying."""
        from apps.trading.services.price_update_service import preview_zero_candidates

        items = request.data.get('items') or []
        return Response(preview_zero_candidates(items, company=default_company_for_user(request.user)))

    @action(detail=False, methods=['post'], url_path='parse-sale-price')
    def parse_sale_price(self, request):
        """External sale-price list → matched against our own inventory."""
        return self._parse(request, PromptConfig.KEY_SALE_PRICE_UPDATE, SALE_PRICE_UPDATE_DEFAULT)

    @action(detail=False, methods=['post'], url_path='apply-sale-price')
    def apply_sale_price(self, request):
        return self._apply(request, [('sale_price', 'sale_price')])


class AutomationRuleViewSet(viewsets.ModelViewSet):
    """CRUD for the Product Price Update page's Automated Price Update rules
    (Sale Price tab only — see apps.trading.services.price_update_automation for
    the matching/apply logic this configures). Each rule's `sources` list is
    replaced wholesale on every create/update — simpler and safer than diffing
    individual source rows for what's a small, human-edited list."""
    serializer_class = AutomationRuleSerializer
    permission_classes = [IsAuthenticated]
    queryset = AutomationRule.objects.none()

    def get_queryset(self):
        return _visible_rule_queryset(
            self.request.user,
            AutomationRule.objects.prefetch_related(
                'sources__contact__account', 'sources__group__account',
            ).order_by('-created_at'),
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        rule = serializer.save()
        self._sync_sources(rule, request.data.get('sources') or [])
        return Response(AutomationRuleSerializer(rule).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        rule = serializer.save()
        if 'sources' in request.data:
            self._sync_sources(rule, request.data.get('sources') or [])
        return Response(AutomationRuleSerializer(rule).data)

    def _sync_sources(self, rule, sources_data):
        from apps.whatsapp_bridge.models import WhatsAppContact, WhatsAppGroup

        valid_types = dict(AutomationRuleSource.SOURCE_TYPE_CHOICES)
        rule.sources.all().delete()
        objs = []
        for s in sources_data:
            source_type = s.get('source_type')
            if source_type not in valid_types:
                continue
            contact_id = s.get('contact_id')
            group_id = s.get('group_id')
            if source_type == AutomationRuleSource.SOURCE_CONTACT and not contact_id:
                continue
            if source_type == AutomationRuleSource.SOURCE_GROUP and not group_id:
                continue
            if source_type == AutomationRuleSource.SOURCE_CONTACT_IN_GROUP and not (contact_id and group_id):
                continue
            if contact_id and not scope_queryset_to_visible_accounts(
                WhatsAppContact.objects.filter(pk=contact_id),
                self.request.user,
                account_field='account',
            ).exists():
                raise ValidationError({'sources': f'Contact {contact_id} is not visible to this user.'})
            if group_id and not scope_queryset_to_visible_accounts(
                WhatsAppGroup.objects.filter(pk=group_id),
                self.request.user,
                account_field='account',
            ).exists():
                raise ValidationError({'sources': f'Group {group_id} is not visible to this user.'})
            objs.append(AutomationRuleSource(
                rule=rule,
                source_type=source_type,
                contact_id=contact_id if source_type != AutomationRuleSource.SOURCE_GROUP else None,
                group_id=group_id if source_type != AutomationRuleSource.SOURCE_CONTACT else None,
            ))
        if objs:
            AutomationRuleSource.objects.bulk_create(objs)

    @action(detail=True, methods=['post'], url_path='toggle')
    def toggle(self, request, pk=None):
        rule = self.get_object()
        rule.is_active = not rule.is_active
        rule.save(update_fields=['is_active', 'updated_at'])
        return Response(AutomationRuleSerializer(rule).data)


class AutomatedPriceCaptureViewSet(viewsets.GenericViewSet, mixins.ListModelMixin, mixins.RetrieveModelMixin):
    """Read/review surface for the "Recent detections" feed — a human confirms
    (apply, with optional edits to the parsed items) or dismisses (ignore) each
    queued capture. Auto-applied captures show up here too, already resolved,
    purely as an audit trail."""
    serializer_class = AutomatedPriceCaptureSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = (
            AutomatedPriceCapture.objects
            .select_related('rule', 'message', 'message__contact', 'message__chat')
            .order_by('-created_at')
        )
        qs = scope_queryset_to_visible_accounts(qs, self.request.user, account_field='message__account')
        status_ = self.request.query_params.get('status')
        if status_:
            qs = qs.filter(status=status_)
        return qs

    @action(detail=True, methods=['post'], url_path='apply')
    def apply(self, request, pk=None):
        capture = self.get_object()
        if capture.status != AutomatedPriceCapture.STATUS_QUEUED:
            return Response({'detail': 'This capture has already been processed.'}, status=status.HTTP_400_BAD_REQUEST)

        items = request.data.get('items')
        if items is not None:
            capture.items = items
            capture.save(update_fields=['items'])

        from apps.trading.services.price_update_automation import apply_capture
        apply_capture(capture)
        capture.refresh_from_db()
        return Response(AutomatedPriceCaptureSerializer(capture).data)

    @action(detail=True, methods=['post'], url_path='ignore')
    def ignore(self, request, pk=None):
        capture = self.get_object()
        if capture.status != AutomatedPriceCapture.STATUS_QUEUED:
            return Response({'detail': 'This capture has already been processed.'}, status=status.HTTP_400_BAD_REQUEST)
        capture.status = AutomatedPriceCapture.STATUS_IGNORED
        capture.save(update_fields=['status'])
        return Response(AutomatedPriceCaptureSerializer(capture).data)

    @action(detail=False, methods=['get'], url_path='summary')
    def summary(self, request):
        """Headline counts for the Automated Price Updates summary strip."""
        week_ago = now() - timedelta(days=7)
        visible_rules = _visible_rule_queryset(request.user)
        visible_rule_ids = visible_rules.values('pk')
        visible_captures = scope_queryset_to_visible_accounts(
            AutomatedPriceCapture.objects.all(),
            request.user,
            account_field='message__account',
        )
        return Response({
            'active_rules':       visible_rules.filter(is_active=True).count(),
            'watched_sources':    AutomationRuleSource.objects.filter(rule__in=visible_rule_ids).count(),
            'captured_this_week': visible_captures.filter(created_at__gte=week_ago).count(),
            'queued':             visible_captures.filter(status=AutomatedPriceCapture.STATUS_QUEUED).count(),
        })
