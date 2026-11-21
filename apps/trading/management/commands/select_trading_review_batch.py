import json
from django.core.management.base import BaseCommand, CommandError
from apps.trading.models import MessageClassification, TradingMessageReview
from apps.trading.services.trading_review_sampling import ReviewGroups, balanced_groups


class Command(BaseCommand):
    help = 'Select a balanced JSONL review batch of distinct message groups for one company.'

    def add_arguments(self, parser):
        parser.add_argument('--company-id', type=int, required=True)
        parser.add_argument('--limit', type=int, default=1000)
        parser.add_argument('--scan-limit', type=int, default=20000)

    def handle(self, *args, **options):
        company_id, limit, scan_limit = options['company_id'], options['limit'], options['scan_limit']
        if company_id <= 0 or limit <= 0 or scan_limit <= 0:
            raise CommandError('Company, limit and scan-limit must be positive.')
        groups = ReviewGroups()
        # Seed with reviewed source snapshots to avoid selecting known copies.
        for review in TradingMessageReview.objects.filter(company_id=company_id).order_by('id').iterator():
            idx = groups.add(review.source_text, {'message_id': review.message_id, 'reviewed': True})
            if idx is not None:
                groups.groups[idx]['reviewed'] = True
        qs = (MessageClassification.objects.filter(message__account__communication_account__company_id=company_id)
              .exclude(message__message_text='').select_related('message').order_by('-message_id')[:scan_limit])
        for item in qs.iterator(chunk_size=500):
            message = item.message
            if not message.message_text.strip():
                continue
            idx = groups.add(message.message_text, {'message_id': message.pk, 'reviewed': False})
            group = groups.groups[idx]
            if 'message_id' not in group:
                group.update({'message_id': message.pk, 'text': message.message_text,
                              'pool': ('non_inquiry' if not item.is_inquiry else item.inquiry_type if item.inquiry_type in ('buy', 'sell') else 'uncertain'),
                              'ai': {'is_inquiry': item.is_inquiry, 'direction': item.inquiry_type, 'products': item.products, 'version': item.classification_version}})
        eligible = [g for g in groups.groups if not g.get('reviewed') and 'message_id' in g]
        # Newest first within each stratum.
        eligible.reverse()
        for group in balanced_groups(eligible, limit):
            self.stdout.write(json.dumps({'group_id': group['id'], 'message_id': group['message_id'],
                'text': group['text'], 'sampling_pool': group['pool'], 'ai': group['ai'],
                'duplicate_message_ids': [m['message_id'] for m in group['members'] if m['message_id'] != group['message_id']]}, ensure_ascii=True))
