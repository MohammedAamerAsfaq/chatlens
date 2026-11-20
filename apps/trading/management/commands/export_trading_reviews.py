import json
from django.core.management.base import BaseCommand
from apps.trading.models import TradingMessageReview


class Command(BaseCommand):
    help = 'Export explicitly reviewed trading messages as JSONL for a single company.'

    def add_arguments(self, parser):
        parser.add_argument('--company-id', type=int, required=True)

    def handle(self, *args, **options):
        reviews = TradingMessageReview.objects.filter(company_id=options['company_id']).select_related('message').order_by('id')
        for review in reviews.iterator():
            self.stdout.write(json.dumps({
                'schema_version': 1, 'review_id': review.pk, 'message_id': review.message_id,
                'message_time': review.message.message_time.isoformat(),
                'content_fingerprint': review.message.content_fingerprint,
                'text': review.source_text, 'label': review.label,
                'reviewed_at': review.created_at.isoformat(),
            }, ensure_ascii=False))
