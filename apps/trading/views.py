import json
import logging
from django.db.models import Count, Q
from django.utils.timezone import now
from datetime import timedelta
from rest_framework import viewsets, mixins, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Product, MessageClassification, Inquiry, InquiryStatus, PromptConfig, PRODUCT_EXTRACTION_DEFAULT, INQUIRY_CLASSIFICATION_DEFAULT, INVENTORY_UPDATE_DEFAULT, AgentCallLog
from .serializers import (
    ProductSerializer,
    MessageClassificationSerializer,
    InquirySerializer,
    InquiryDetailSerializer,
)
from .services.product_cache import invalidate as invalidate_product_cache

logger = logging.getLogger(__name__)


class ProductViewSet(viewsets.ModelViewSet):
    serializer_class   = ProductSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = Product.objects.all()
        active = self.request.query_params.get('active')
        if active == 'true':
            qs = qs.filter(is_active=True)
        elif active == 'false':
            qs = qs.filter(is_active=False)
        return qs

    def perform_create(self, serializer):
        serializer.save()
        invalidate_product_cache()

    def perform_update(self, serializer):
        serializer.save()
        invalidate_product_cache()

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
                aliases=item.get('aliases') or [],
            )
            created.append(ProductSerializer(p).data)
        if created:
            invalidate_product_cache()
        return Response({'created': created, 'skipped': skipped})

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

    @action(detail=False, methods=['get'], url_path='stats')
    def stats(self, request):
        today = now().replace(hour=0, minute=0, second=0, microsecond=0)
        account_id = request.query_params.get('account')

        qs = Inquiry.objects.filter(first_seen_at__gte=today)
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

        inquiry.save(update_fields=update_fields)
        return Response(InquiryDetailSerializer(inquiry).data)

    @action(detail=False, methods=['get'], url_path='stats')
    def stats(self, request):
        today = now().replace(hour=0, minute=0, second=0, microsecond=0)
        account_id = request.query_params.get('account')

        qs = Inquiry.objects.filter(first_seen_at__gte=today)
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

        # Hourly timeline for today (0-23)
        timeline = []
        for hour in range(24):
            slot_start = today + timedelta(hours=hour)
            slot_end   = slot_start + timedelta(hours=1)
            if slot_start > now():
                break
            row = qs.filter(first_seen_at__gte=slot_start, first_seen_at__lt=slot_end).aggregate(
                wtb=Count('id', filter=Q(inquiry_type='buy')),
                wts=Count('id', filter=Q(inquiry_type='sell')),
            )
            timeline.append({'hour': slot_start.strftime('%H:%M'), **row})

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
        })

    @action(detail=False, methods=['get'], url_path='open-feed')
    def open_feed(self, request):
        """Return the latest open inquiries for the live dashboard feed."""
        account_id = request.query_params.get('account')
        limit      = min(int(request.query_params.get('limit', 50)), 200)

        qs = Inquiry.objects.filter(status=InquiryStatus.OPEN).select_related(
            'account', 'contact'
        ).order_by('-first_seen_at')[:limit]

        if account_id:
            qs = Inquiry.objects.filter(
                status=InquiryStatus.OPEN, account_id=account_id,
            ).select_related('account', 'contact').order_by('-first_seen_at')[:limit]

        return Response(InquirySerializer(qs, many=True).data)

    @action(detail=False, methods=['get'], url_path='classification-activity')
    def classification_activity(self, request):
        """Summary of recent classification results — useful for diagnosing the pipeline."""
        from apps.trading.models import MessageClassification, InquiryMessage
        account_id = request.query_params.get('account')
        today = now().replace(hour=0, minute=0, second=0, microsecond=0)

        qs = MessageClassification.objects.filter(classified_at__gte=today)
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
