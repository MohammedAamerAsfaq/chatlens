import json
from django.core.management.base import BaseCommand
from apps.trading.models import TradingMessageReview
from apps.trading.services.trading_review_sampling import ReviewGroups


def review_origin(review):
    # Null reviewer alone is not evidence of AI origin: users can be deleted.
    if (review.label or {}).get('notes', '').startswith('AI review by OpenAI Codex;'):
        return 'ai'
    return 'human' if review.reviewed_by_id is not None else 'unknown'


def group_split(group_id):
    bucket = int(group_id[:16], 16) % 100
    return 'test' if bucket < 10 else 'validation' if bucket < 20 else 'train'


class Command(BaseCommand):
    help = 'Export reviewed trading messages as JSONL for a single company.'

    def add_arguments(self, parser):
        parser.add_argument('--company-id', type=int, required=True)
        parser.add_argument('--origin', choices=['human', 'ai', 'all'], default='human', help='Defaults to human-reviewed examples only.')
        parser.add_argument('--split', choices=['train', 'validation', 'test', 'all'], default='all')

    def handle(self, *args, **options):
        reviews = list(TradingMessageReview.objects.filter(company_id=options['company_id']).select_related('message').order_by('id'))
        groups = ReviewGroups()
        assignments = {}
        for review in reviews:
            idx = groups.add(review.source_text, review.pk)
            if idx is not None:
                assignments[review.pk] = groups.groups[idx]['id']
        for review in reviews:
            if review.pk not in assignments:
                continue
            origin = review_origin(review)
            split = group_split(assignments[review.pk])
            if options['origin'] != 'all' and options['origin'] != origin:
                continue
            if options['split'] != 'all' and options['split'] != split:
                continue
            # Evaluation exports must not silently promote model-produced labels.
            if options['split'] in ('validation', 'test') and origin != 'human':
                continue
            self.stdout.write(json.dumps({
                'schema_version': 2, 'review_id': review.pk, 'message_id': review.message_id,
                'message_time': review.message.message_time.isoformat(),
                'content_fingerprint': review.message.content_fingerprint,
                'group_id': assignments[review.pk], 'split': split,
                'text': review.source_text, 'label': review.label, 'review_origin': origin,
                'reviewed_at': review.created_at.isoformat(),
            }, ensure_ascii=True))
