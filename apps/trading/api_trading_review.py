from django.shortcuts import get_object_or_404
from django.db import transaction
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.tenancy.api_permissions import CompanyPermissionRequired
from apps.tenancy.services.access import default_company_for_user, scope_queryset_to_visible_accounts
from apps.trading.models import MessageClassification, TradingMessageReview, TradingReviewBatch, TradingReviewBatchItem, TradingReviewRevision


class ProductLabel(serializers.Serializer):
    name = serializers.CharField(max_length=500, trim_whitespace=True)
    quantity = serializers.CharField(required=False, allow_blank=True, max_length=100)
    price = serializers.CharField(required=False, allow_blank=True, max_length=100)
    currency = serializers.CharField(required=False, allow_blank=True, max_length=20)


class ReviewLabel(serializers.Serializer):
    is_inquiry = serializers.BooleanField()
    direction = serializers.ChoiceField(choices=['buy', 'sell', 'both', 'unknown', ''], allow_blank=True)
    # Long stock lists commonly exceed 100 product lines.
    products = ProductLabel(many=True, max_length=1000)
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

    @action(detail=False, methods=['get'], url_path='batch-next')
    def batch_next(self, request):
        company = default_company_for_user(request.user)
        if not company:
            return Response({'detail': 'No active company selected.'}, status=400)
        try:
            after = int(request.query_params.get('after', 0))
            if after < 0:
                raise ValueError
        except ValueError:
            return Response({'detail': 'Invalid cursor.'}, status=400)
        batch = TradingReviewBatch.objects.filter(company=company).order_by('-id').first()
        if not batch:
            return Response({'available': False})
        visible = scope_queryset_to_visible_accounts(
            TradingReviewBatchItem.objects.filter(batch=batch, message__account__communication_account__company=company, message__classification__isnull=False),
            request.user, account_field='message__account')
        total = visible.count()
        completed = visible.filter(message__trading_review__isnull=False).count()
        item = (visible.filter(message__trading_review__isnull=True, position__gt=after)
                .select_related('message__classification').order_by('position').first())
        response = {'available': True, 'batch_name': batch.name, 'total': total, 'completed': completed}
        if not item:
            response['done'] = True
            return Response(response)
        classification = item.message.classification
        response.update({'done': False, 'position': item.position, 'message_id': item.message_id,
                         'text': item.message.message_text, 'duplicate_count': len(item.duplicate_message_ids),
                         'sampling_pool': item.sampling_pool,
                         'ai': {'is_inquiry': classification.is_inquiry, 'direction': classification.inquiry_type,
                                'products': classification.products, 'version': classification.classification_version}})
        return Response(response)

    @action(detail=False, methods=['get'], url_path='review-next')
    def review_next(self, request):
        company = default_company_for_user(request.user)
        if not company:
            return Response({'detail': 'No active company selected.'}, status=400)
        try:
            after = int(request.query_params.get('after', 0))
            if after < 0:
                raise ValueError
        except ValueError:
            return Response({'detail': 'Invalid cursor.'}, status=400)
        origin = request.query_params.get('origin', 'ai')
        if origin not in ('ai', 'human'):
            return Response({'detail': 'Invalid review origin.'}, status=400)
        sample = request.query_params.get('sample', 'all')
        if sample not in ('all', 'evaluation') or (sample == 'evaluation' and origin != 'ai'):
            return Response({'detail': 'Invalid review sample.'}, status=400)
        qs = scope_queryset_to_visible_accounts(TradingMessageReview.objects.filter(company=company, pk__gt=after), request.user, account_field='message__account')
        if sample == 'evaluation':
            from apps.trading.services.trading_review_sampling import ReviewGroups
            from apps.trading.management.commands.export_trading_reviews import group_split
            groups = ReviewGroups()
            eligible = []
            for existing in TradingMessageReview.objects.filter(company=company).order_by('pk').only('pk', 'source_text').iterator():
                index = groups.add(existing.source_text, existing.pk)
                if index is not None and group_split(groups.groups[index]['id']) in ('validation', 'test'):
                    eligible.append(existing.pk)
            qs = qs.filter(pk__in=eligible)
        if origin == 'ai':
            qs = qs.filter(label__notes__startswith='AI review by OpenAI Codex;')
        else:
            qs = qs.filter(reviewed_by__isnull=False).exclude(label__notes__startswith='AI review by OpenAI Codex;')
        review = qs.order_by('pk').first()
        if not review:
            return Response({'done': True})
        return Response({'done': False, 'review_id': review.pk, 'message_id': review.message_id,
                         'text': review.source_text, 'ai': review.ai_snapshot, 'label': review.label, 'origin': origin})

    @action(detail=False, methods=['post'], url_path='correct')
    def correct(self, request):
        company = default_company_for_user(request.user)
        if not company:
            return Response({'detail': 'No active company selected.'}, status=400)
        try:
            review_id = int(request.data.get('review_id'))
            if review_id <= 0:
                raise ValueError
        except (TypeError, ValueError):
            return Response({'detail': 'A valid review_id is required.'}, status=400)
        serializer = ReviewLabel(data=request.data.get('label'))
        serializer.is_valid(raise_exception=True)
        label = dict(serializer.validated_data)
        if label.get('notes', '').startswith('AI review by OpenAI Codex;'):
            return Response({'detail': 'Replace the AI provenance note when confirming a human review.'}, status=400)
        with transaction.atomic():
            qs = scope_queryset_to_visible_accounts(TradingMessageReview.objects.filter(company=company), request.user, account_field='message__account')
            review = get_object_or_404(qs.select_for_update(), pk=review_id)
            if request.data.get('expected_label') != review.label:
                return Response({'detail': 'This review has changed. Reload it before saving.'}, status=409)
            TradingReviewRevision.objects.create(review=review, previous_label=review.label,
                previous_reviewer=review.reviewed_by, changed_by=request.user)
            review.label = label
            review.reviewed_by = request.user
            review.save(update_fields=['label', 'reviewed_by'])
        return Response({'id': review.pk})

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

