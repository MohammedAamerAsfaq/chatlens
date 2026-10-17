from datetime import timedelta

from django.db.models import Count, Max, Min, Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import status, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.trading.models import Inquiry, InquiryProduct
from apps.whatsapp_bridge.models import OutboundMessage, WhatsAppAccount, WhatsAppChat, WhatsAppContact, WhatsAppMessage

from .authentication import ApiKeyAuthentication
from .external_serializers import (
    ChatSerializer, ContactSerializer, InquirySerializer, MessageSerializer, OutboundMessageSerializer,
    SendMessageSerializer, WebhookDeliveryAttemptSerializer, WebhookSubscriptionCreatedSerializer,
    WebhookSubscriptionSerializer,
)
from .models import ApiKey, ApiKeyUsageLog, WebhookDeliveryAttempt, WebhookSubscription
from .pagination import ApiKeyPageNumberPagination
from .permissions import HasApiScope
from .throttling import ApiKeyRateThrottle


def _parse_query_datetime(request, param):
    raw = request.query_params.get(param)
    if not raw:
        return None
    value = parse_datetime(raw)
    if value is None:
        raise ValidationError({param: [f'{param} must be an ISO 8601 datetime, e.g. 2026-01-31T00:00:00Z.']})
    if timezone.is_naive(value):
        value = timezone.make_aware(value)
    return value


class ExternalApiMixin:
    authentication_classes = [ApiKeyAuthentication]
    permission_classes = [HasApiScope]
    throttle_classes = [ApiKeyRateThrottle]
    pagination_class = ApiKeyPageNumberPagination

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        api_key = getattr(request, 'auth', None)
        if api_key is not None:
            ApiKeyUsageLog.objects.create(
                api_key=api_key, company=api_key.company, method=request.method,
                path=request.path, status_code=response.status_code,
            )
        return response


class PingView(ExternalApiMixin, APIView):
    """Lets a third party confirm its key works without needing any particular scope."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        api_key = request.auth
        return Response({
            'status': 'ok',
            'company': api_key.company.name,
            'key_name': api_key.name,
            'key_prefix': api_key.key_prefix,
            'scopes': api_key.scopes,
            'server_time': timezone.now(),
        })


class ContactViewSet(ExternalApiMixin, viewsets.ReadOnlyModelViewSet):
    required_scope = ApiKey.SCOPE_DATA_READ
    serializer_class = ContactSerializer

    def get_queryset(self):
        return WhatsAppContact.objects.filter(
            account__communication_account__company=self.request.auth.company,
        ).order_by('display_name')


class ChatViewSet(ExternalApiMixin, viewsets.ReadOnlyModelViewSet):
    required_scope = ApiKey.SCOPE_DATA_READ
    serializer_class = ChatSerializer

    def get_queryset(self):
        return WhatsAppChat.objects.filter(
            account__communication_account__company=self.request.auth.company,
        ).order_by('-last_message_at')


class MessageViewSet(ExternalApiMixin, viewsets.ReadOnlyModelViewSet):
    required_scope = ApiKey.SCOPE_DATA_READ
    serializer_class = MessageSerializer

    def get_queryset(self):
        qs = WhatsAppMessage.objects.filter(
            account__communication_account__company=self.request.auth.company,
        )
        chat_id = self.request.query_params.get('chat')
        if chat_id:
            qs = qs.filter(chat_id=chat_id)
        return qs.order_by('-message_time')


class OutboundMessageViewSet(ExternalApiMixin, viewsets.ReadOnlyModelViewSet):
    required_scope = ApiKey.SCOPE_DATA_READ
    serializer_class = OutboundMessageSerializer

    def get_queryset(self):
        return OutboundMessage.objects.filter(
            company=self.request.auth.company,
        ).order_by('-created_at')


class InquiryViewSet(ExternalApiMixin, viewsets.ReadOnlyModelViewSet):
    required_scope = ApiKey.SCOPE_DATA_READ
    serializer_class = InquirySerializer

    def get_queryset(self):
        qs = Inquiry.objects.filter(company=self.request.auth.company)
        if value := self.request.query_params.get('status'):
            qs = qs.filter(status=value)
        if value := self.request.query_params.get('inquiry_type'):
            qs = qs.filter(inquiry_type=value)
        if value := _parse_query_datetime(self.request, 'first_seen_after'):
            qs = qs.filter(first_seen_at__gte=value)
        if value := _parse_query_datetime(self.request, 'first_seen_before'):
            qs = qs.filter(first_seen_at__lte=value)
        return qs.order_by('-first_seen_at')


class ProductMentionsView(ExternalApiMixin, APIView):
    """Grouped WTB/WTS mention counts per product over a date range.

    Mirrors apps/trading/views.py ReportViewSet.inventory_product_mentions (the internal
    Product Mentions report) so the two stay consistent, scoped to the key's company
    instead of the session user's visible companies.
    """

    required_scope = ApiKey.SCOPE_DATA_READ
    DEFAULT_RANGE_DAYS = 30
    MAX_LIMIT = 500
    DEFAULT_LIMIT = 100

    def get(self, request):
        end = _parse_query_datetime(request, 'first_seen_before') or timezone.now()
        start = _parse_query_datetime(request, 'first_seen_after') or (end - timedelta(days=self.DEFAULT_RANGE_DAYS))
        search = (request.query_params.get('search') or '').strip()
        try:
            limit = min(max(int(request.query_params.get('limit') or self.DEFAULT_LIMIT), 1), self.MAX_LIMIT)
        except ValueError:
            raise ValidationError({'limit': ['limit must be an integer.']})

        qs = InquiryProduct.objects.filter(
            company=request.auth.company, product__isnull=False,
            first_seen_at__gte=start, first_seen_at__lte=end,
        )
        if search:
            qs = qs.filter(
                Q(product__name__icontains=search)
                | Q(product__brand__icontains=search)
                | Q(canonical_name__icontains=search)
            )

        grouped = (
            qs.values(
                'product_id', 'product__brand', 'product__name', 'product__sku',
                'product__qty', 'product__sale_price', 'product__currency',
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
            'range': {'first_seen_after': start, 'first_seen_before': end},
        })


class SendMessageView(ExternalApiMixin, APIView):
    required_scope = ApiKey.SCOPE_MESSAGES_SEND

    def post(self, request):
        from apps.whatsapp_bridge.outbound.message_service import create_outbound_message

        serializer = SendMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        company = request.auth.company

        account = WhatsAppAccount.objects.filter(
            pk=data['whatsapp_account_id'], communication_account__company=company,
        ).first()
        if not account:
            return Response({'whatsapp_account_id': ['Account was not found for this company.']}, status=404)
        if not account.outbound_sending_enabled:
            return Response({'detail': 'Outbound sending is not enabled for this account.'}, status=403)

        try:
            outbound, created = create_outbound_message(
                account=account,
                destination_jid=data['destination_jid'].strip().lower(),
                text=data.get('text', ''),
                requested_by=None,
                idempotency_key=data.get('idempotency_key'),
                confirm_new_chat=data.get('confirm_new_chat', False),
                actor_label=f'apikey:{request.auth.key_prefix}',
            )
        except ValueError as exc:
            if str(exc) == 'likely_new_chat_confirmation_required':
                return Response(
                    {'detail': 'This may start a new chat. Explicit confirmation is required.', 'code': str(exc)},
                    status=status.HTTP_409_CONFLICT,
                )
            raise
        return Response(
            OutboundMessageSerializer(outbound).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class WebhookSubscriptionViewSet(ExternalApiMixin, viewsets.ModelViewSet):
    required_scope = ApiKey.SCOPE_WEBHOOKS_MANAGE
    serializer_class = WebhookSubscriptionSerializer

    def get_queryset(self):
        return WebhookSubscription.objects.filter(company=self.request.auth.company)

    def perform_create(self, serializer):
        serializer.save(company=self.request.auth.company, created_by_api_key=self.request.auth)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(WebhookSubscriptionCreatedSerializer(serializer.instance).data, status=201)


class WebhookDeliveryAttemptViewSet(ExternalApiMixin, viewsets.ReadOnlyModelViewSet):
    required_scope = ApiKey.SCOPE_WEBHOOKS_MANAGE
    serializer_class = WebhookDeliveryAttemptSerializer

    def get_queryset(self):
        return WebhookDeliveryAttempt.objects.filter(
            subscription__company=self.request.auth.company,
            subscription_id=self.kwargs['subscription_pk'],
        )
