import logging
from django.db.models import Count, Q
from django.utils.timezone import now
from datetime import timedelta
from rest_framework import viewsets, mixins
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import Product, MessageClassification, Inquiry, InquiryStatus
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
    permission_classes = [AllowAny]

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
    permission_classes = [AllowAny]

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


class MessageClassificationViewSet(viewsets.GenericViewSet, mixins.ListModelMixin):
    serializer_class   = MessageClassificationSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        qs = MessageClassification.objects.order_by('-classified_at')
        if message_id := self.request.query_params.get('message'):
            qs = qs.filter(message_id=message_id)
        return qs
