import json
import logging
import threading
from django.db import connection as _db_conn
from django.db.models import Count, Q
from django.utils.timezone import now, make_aware
from datetime import timedelta, date as _date, datetime as _datetime, time as _time
from rest_framework import viewsets, mixins, status
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Product, ProductAlias, ProductAttribute, MessageClassification, Inquiry, InquiryStatus, PromptConfig, PRODUCT_EXTRACTION_DEFAULT, INQUIRY_CLASSIFICATION_DEFAULT, INVENTORY_UPDATE_DEFAULT, PRICE_LIST_FORMAT_DEFAULT, QTY_COST_UPDATE_DEFAULT, SALE_PRICE_UPDATE_DEFAULT, AgentCallLog, AiParsingLog, BuyingInquiry, SupplierQuote, AutomationRule, AutomationRuleSource, AutomatedPriceCapture
from .serializers import (
    ProductSerializer,
    ProductAliasSerializer,
    ProductAttributeSerializer,
    MessageClassificationSerializer,
    InquirySerializer,
    InquiryDetailSerializer,
    AiParsingLogSerializer,
    BuyingInquirySerializer,
    SupplierQuoteSerializer,
    AutomationRuleSerializer,
    AutomatedPriceCaptureSerializer,
)
from .services.product_cache import invalidate as invalidate_product_cache

logger = logging.getLogger(__name__)


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
        qs = Product.objects.all().select_related('embedding').prefetch_related('alias_set__embedding', 'attribute_set')
        active = self.request.query_params.get('active')
        if active == 'true':
            qs = qs.filter(is_active=True)
        elif active == 'false':
            qs = qs.filter(is_active=False)
        return qs

    def perform_create(self, serializer):
        product = serializer.save()
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
            if Product.objects.filter(name__iexact=name).exists():
                skipped.append(name)
                continue
            p = Product.objects.create(
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

        product_block = get_product_prompt_block()
        system_prompt = PromptConfig.get_body(
            PromptConfig.KEY_INVENTORY_UPDATE,
            INVENTORY_UPDATE_DEFAULT,
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
                try:
                    product = Product.objects.get(pk=product_id)
                except Product.DoesNotExist:
                    pass
            if not product and name:
                product = Product.objects.filter(name__iexact=name, is_active=True).first()

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

        obj = FormattedPriceList.get_current()
        return Response({
            'body':         obj.body if obj else '',
            'generated_at': obj.generated_at.isoformat() if obj and obj.generated_at else None,
        })

    @action(detail=False, methods=['post'], url_path='regenerate-price-list')
    def regenerate_price_list(self, request):
        """Re-run the AI formatting prompt against the current in-stock, priced catalog."""
        from apps.trading.services.price_list_service import generate_price_list

        try:
            obj = generate_price_list()
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

        results = [
            {'product': ProductSerializer(hit.product).data, 'distance': round(float(hit.distance), 4)}
            for hit in hits
        ]
        return Response({'results': results})

    @action(detail=False, methods=['get'], url_path='embedding-status')
    def embedding_status(self, request):
        """Counts of embedded vs. missing for products and their aliases — the only
        durable signal for a background embedding job that failed (a provider hiccup,
        rate limit, etc.). Those failures only ever land in a console warning with
        nothing persisted, so "missing an embedding" is itself the record; this and
        backfill-embeddings below are how that gets noticed and fixed instead of
        silently sitting broken forever."""
        from apps.message_intelligence.models import ProductEmbedding, ProductAliasEmbedding

        product_total = Product.objects.filter(is_active=True).count()
        product_embedded = ProductEmbedding.objects.filter(
            product__is_active=True, embedding__isnull=False,
        ).count()

        alias_total = ProductAlias.objects.filter(product__is_active=True).count()
        alias_embedded = ProductAliasEmbedding.objects.filter(
            alias__product__is_active=True, embedding__isnull=False,
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

        missing_product_ids = list(
            Product.objects.filter(is_active=True)
            .exclude(id__in=ProductEmbedding.objects.filter(embedding__isnull=False).values('product_id'))
            .values_list('id', flat=True)
        )
        missing_alias_ids = list(
            ProductAlias.objects.filter(product__is_active=True)
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
        if account_id:
            qs = qs.filter(account_id=account_id)

        product_ids = list(
            Product.objects.filter(is_active=True).values_list('id', 'name', 'brand')
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
        qs = Inquiry.objects.select_related('account', 'contact').order_by('-first_seen_at')
        p = self.request.query_params

        if account_id := p.get('account'):
            qs = qs.filter(account_id=account_id)
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

        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            return Response({'detail': 'product not found'}, status=status.HTTP_400_BAD_REQUEST)

        line['product_id'] = product.id
        line['match_type'] = 'exact'
        line['manually_corrected'] = True
        inquiry.products = products
        inquiry.save(update_fields=['products', 'updated_at'])
        return Response(InquiryDetailSerializer(inquiry).data)

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

        account_id = request.data.get('account')
        if account_id:
            qs = qs.filter(account_id=account_id)

        closed_count = qs.update(status=InquiryStatus.CLOSED, closed_at=now())
        return Response({'closed': closed_count})

    @action(detail=False, methods=['get'], url_path='stats')
    def stats(self, request):
        start, end = _resolve_date_range(request)
        account_id = request.query_params.get('account')

        qs = Inquiry.objects.filter(first_seen_at__gte=start, first_seen_at__lt=end)
        if account_id:
            qs = qs.filter(account_id=account_id)

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
        status/type/account. Paginated via `limit` (default 50, max 1000) — the response
        includes `count`, the true total matching the filters, so the frontend can tell
        when it's showing a truncated slice and load more instead of silently capping.
        """
        account_id = request.query_params.get('account')
        limit      = min(int(request.query_params.get('limit', 50)), 1000)
        status_val = request.query_params.get('status', InquiryStatus.OPEN)
        type_val   = request.query_params.get('type')

        today = now().replace(hour=0, minute=0, second=0, microsecond=0)
        qs = Inquiry.objects.filter(first_seen_at__gte=today).select_related('account', 'contact')

        if status_val and status_val != 'all':
            qs = qs.filter(status=status_val)
        if account_id:
            qs = qs.filter(account_id=account_id)
        if type_val in ('buy', 'sell'):
            qs = qs.filter(inquiry_type=type_val)

        qs = qs.order_by('-first_seen_at')
        return Response({
            'count':   qs.count(),
            'results': InquirySerializer(qs[:limit], many=True).data,
        })

    @action(detail=False, methods=['get'], url_path='classification-activity')
    def classification_activity(self, request):
        """Summary of recent classification results — useful for diagnosing the pipeline."""
        from apps.trading.models import MessageClassification, InquiryMessage
        account_id = request.query_params.get('account')
        start, end = _resolve_date_range(request)

        qs = MessageClassification.objects.filter(classified_at__gte=start, classified_at__lt=end)
        if account_id:
            qs = qs.filter(message__account_id=account_id)

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
        if account_id:
            mc_qs = mc_qs.filter(message__account_id=account_id)

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
        if account_id:
            qs = qs.filter(account_id=account_id)

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


class MessageClassificationViewSet(viewsets.GenericViewSet, mixins.ListModelMixin):
    serializer_class   = MessageClassificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = MessageClassification.objects.order_by('-classified_at')
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
            PromptConfig.KEY_INVENTORY_UPDATE:       (INVENTORY_UPDATE_DEFAULT,       'Inventory Update (bulk qty + price)'),
            PromptConfig.KEY_PRICE_LIST_FORMAT:      (PRICE_LIST_FORMAT_DEFAULT,      'Price List Formatting (WhatsApp send)'),
            PromptConfig.KEY_QTY_COST_UPDATE:        (QTY_COST_UPDATE_DEFAULT,        'Qty & Cost Update (Product Price Update page)'),
            PromptConfig.KEY_SALE_PRICE_UPDATE:      (SALE_PRICE_UPDATE_DEFAULT,      'Sale Price Update (Product Price Update page)'),
        }
        saved = {p.key: p for p in PromptConfig.objects.all()}
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
            PromptConfig.KEY_INVENTORY_UPDATE:       'Inventory Update (bulk qty + price)',
            PromptConfig.KEY_PRICE_LIST_FORMAT:      'Price List Formatting (WhatsApp send)',
            PromptConfig.KEY_QTY_COST_UPDATE:        'Qty & Cost Update (Product Price Update page)',
            PromptConfig.KEY_SALE_PRICE_UPDATE:      'Sale Price Update (Product Price Update page)',
        }
        label = defaults_map.get(key, key)
        obj, _ = PromptConfig.objects.update_or_create(
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
        PromptConfig.objects.filter(key=pk).delete()
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
        p = self.request.query_params
        if account_id := p.get('account'):
            qs = qs.filter(account_id=account_id)
        if status_ := p.get('status'):
            qs = qs.filter(status=status_)
        if reason := p.get('skip_reason'):
            qs = qs.filter(skip_reason=reason)
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
        p = self.request.query_params
        if account_id := p.get('account'):
            qs = qs.filter(account_id=account_id)
        if status_ := p.get('status'):
            qs = qs.filter(status=status_)
        return qs

    def perform_create(self, serializer):
        from apps.whatsapp_bridge.models import WhatsAppContact
        inquiry = serializer.save()
        # Auto-populate a supplier card for every contact currently tagged 'supplier' or
        # 'both' on this account — the user can add/remove individual suppliers afterward.
        suppliers = WhatsAppContact.objects.filter(account=inquiry.account, category__in=['supplier', 'both'])
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
    queryset = SupplierQuote.objects.select_related('supplier', 'buying_inquiry')

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
        if account_id:
            messages_qs = messages_qs.filter(account_id=account_id)
            inquiries_qs = inquiries_qs.filter(account_id=account_id)

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
            obj = SystemSettings.objects.filter(key=self.WTS_REPLY_KEY).first()
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
            key=self.WTS_REPLY_KEY,
            defaults={
                'value': json.dumps(payload),
                'description': 'WhatsApp price-reply composition settings for the Trading dashboard (heading text, Flag/Color attribute prefix/suffix, primary + optional secondary currency label).',
            },
        )
        return Response(payload)


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
            items = parse_against_inventory(text, prompt_key, prompt_default)
            return Response({'items': items})
        except Exception as exc:
            logger.exception('ProductPriceUpdateViewSet | parse failed | prompt_key=%s', prompt_key)
            return Response({'error': str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _apply(self, request, fields):
        """fields: iterable of (payload_key, product_attr) pairs to copy across,
        e.g. [('qty', 'qty'), ('cost_price', 'cost_price')]."""
        from apps.trading.services.price_update_service import apply_items_to_inventory

        items = request.data.get('items') or []
        result = apply_items_to_inventory(items, fields)
        return Response(result)

    @action(detail=False, methods=['post'], url_path='parse-qty-cost')
    def parse_qty_cost(self, request):
        """Supplier qty/cost list → matched against our own inventory."""
        return self._parse(request, PromptConfig.KEY_QTY_COST_UPDATE, QTY_COST_UPDATE_DEFAULT)

    @action(detail=False, methods=['post'], url_path='apply-qty-cost')
    def apply_qty_cost(self, request):
        return self._apply(request, [('qty', 'qty'), ('cost_price', 'cost_price')])

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
    queryset = AutomationRule.objects.all().prefetch_related(
        'sources__contact__account', 'sources__group__account',
    ).order_by('-created_at')

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
        return Response({
            'active_rules':       AutomationRule.objects.filter(is_active=True).count(),
            'watched_sources':    AutomationRuleSource.objects.count(),
            'captured_this_week': AutomatedPriceCapture.objects.filter(created_at__gte=week_ago).count(),
            'queued':             AutomatedPriceCapture.objects.filter(status=AutomatedPriceCapture.STATUS_QUEUED).count(),
        })
