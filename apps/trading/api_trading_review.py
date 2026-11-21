from django.shortcuts import get_object_or_404
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.tenancy.api_permissions import CompanyPermissionRequired
from apps.tenancy.services.access import default_company_for_user, scope_queryset_to_visible_accounts
from apps.trading.models import MessageClassification, TradingMessageReview


class ProductLabel(serializers.Serializer):
    name = serializers.CharField(max_length=500, trim_whitespace=True)
    quantity = serializers.CharField(required=False, allow_blank=True, max_length=100)
    price = serializers.CharField(required=False, allow_blank=True, max_length=100)
    currency = serializers.CharField(required=False, allow_blank=True, max_length=20)


class ReviewLabel(serializers.Serializer):
    is_inquiry = serializers.BooleanField()
    direction = serializers.ChoiceField(choices=['buy', 'sell', 'both', 'unknown', ''], allow_blank=True)
    products = ProductLabel(many=True, max_length=100)
    notes = serializers.CharField(required=False, allow_blank=True, max_length=2000)

    def validate(self, attrs):
        if not attrs['is_inquiry'] and (attrs['direction'] or attrs['products']):
            raise serializers.ValidationError('Non-inquiries must have no direction or products.')
        if attrs['is_inquiry'] and not attrs['direction']:
            raise serializers.ValidationError('Choose a direction or unknown for an inquiry.')
        return attrs


class TradingReviewViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated, CompanyPermissionRequired]
    read_permission = 'trading.matches.manage'
    write_permission = 'trading.matches.manage'

    def _classifications(self, request, company):
        qs = MessageClassification.objects.filter(message__account__communication_account__company=company)
        return scope_queryset_to_visible_accounts(qs, request.user, account_field='message__account')

    @action(detail=False, methods=['get'])
    def next(self, request):
        company = default_company_for_user(request.user)
        if not company:
            return Response({'detail': 'No active company selected.'}, status=400)
        pool = request.query_params.get('pool', 'all')
        if pool not in ('all', 'inquiry', 'non_inquiry', 'buy', 'sell', 'uncertain'):
            return Response({'detail': 'Invalid review pool.'}, status=400)
        qs = self._classifications(request, company).filter(message__trading_review__isnull=True).exclude(message__message_text='')
        if pool == 'non_inquiry':
            qs = qs.filter(is_inquiry=False)
        elif pool in ('buy', 'sell'):
            qs = qs.filter(is_inquiry=True, inquiry_type=pool)
        elif pool == 'inquiry':
            qs = qs.filter(is_inquiry=True)
        elif pool == 'uncertain':
            qs = qs.filter(is_inquiry=True).exclude(inquiry_type__in=('buy', 'sell'))
        try:
            after = int(request.query_params.get('after', 0))
            if after < 0:
                raise ValueError
        except ValueError:
            return Response({'detail': 'Invalid cursor.'}, status=400)
        if after:
            qs = qs.filter(message_id__gt=after)
        classification = qs.select_related('message').order_by('message_id').first()
        if not classification:
            return Response({'done': True})
        return Response({'message_id': classification.message_id, 'text': classification.message.message_text,
                         'ai': {'is_inquiry': classification.is_inquiry, 'direction': classification.inquiry_type,
                                'products': classification.products, 'version': classification.classification_version},
                         'reviewed_count': scope_queryset_to_visible_accounts(TradingMessageReview.objects.filter(company=company), request.user, account_field='message__account').count()})

    @action(detail=False, methods=['post'])
    def submit(self, request):
        company = default_company_for_user(request.user)
        if not company:
            return Response({'detail': 'No active company selected.'}, status=400)
        try:
            message_id = int(request.data.get('message_id'))
            if message_id <= 0:
                raise ValueError
        except (TypeError, ValueError):
            return Response({'detail': 'A valid message_id is required.'}, status=400)
        serializer = ReviewLabel(data=request.data.get('label'))
        serializer.is_valid(raise_exception=True)
        classification = get_object_or_404(self._classifications(request, company).select_related('message'), message_id=message_id)
        if not classification.message.message_text:
            return Response({'detail': 'A text message is required.'}, status=400)
        review, created = TradingMessageReview.objects.get_or_create(
            message=classification.message,
            defaults={'company': company, 'source_text': classification.message.message_text,
                      'ai_snapshot': {'is_inquiry': classification.is_inquiry, 'direction': classification.inquiry_type,
                                      'products': classification.products, 'version': classification.classification_version},
                      'label': serializer.validated_data, 'reviewed_by': request.user})
        if not created:
            return Response({'detail': 'This message has already been reviewed.'}, status=409)
        return Response({'id': review.pk}, status=201)

