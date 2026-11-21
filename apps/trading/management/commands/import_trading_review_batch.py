import json
import re
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from apps.trading.models import MessageClassification, TradingReviewBatch, TradingReviewBatchItem


class Command(BaseCommand):
    help = 'Import a previously selected review batch for one company.'

    def add_arguments(self, parser):
        parser.add_argument('--company-id', type=int, required=True)
        parser.add_argument('--name', required=True)
        parser.add_argument('--file', required=True)

    def handle(self, *args, **options):
        try:
            with Path(options['file']).open(encoding='utf-8-sig') as stream:
                rows = [json.loads(line) for line in stream if line.strip()]
        except (OSError, ValueError) as exc:
            raise CommandError(f'Cannot read batch: {exc}') from exc
        if not rows or len(rows) > 10000 or not options['name'].strip() or len(options['name']) > 200:
            raise CommandError('Batch must have 1–10000 entries and a name of at most 200 characters.')
        ids = []
        for row in rows:
            if not isinstance(row, dict) or type(row.get('message_id')) is not int or row['message_id'] <= 0 or not re.fullmatch(r'[a-f0-9]{64}', str(row.get('group_id', ''))) or row.get('sampling_pool') not in ('buy', 'sell', 'non_inquiry', 'uncertain'):
                raise CommandError('Invalid batch entry.')
            links = row.get('duplicate_message_ids', [])
            if not isinstance(links, list) or any(type(mid) is not int or mid <= 0 for mid in links):
                raise CommandError('Invalid duplicate message IDs.')
            ids.append(row['message_id'])
        if len(ids) != len(set(ids)):
            raise CommandError('Duplicate representative message IDs in batch.')
        existing = set(MessageClassification.objects.filter(message_id__in=ids, message__account__communication_account__company_id=options['company_id']).values_list('message_id', flat=True))
        if existing != set(ids):
            raise CommandError('Some messages are missing, unclassified, or belong to another company.')
        # Duplicate links are also checked against the same tenant; the import file is untrusted.
        duplicates = {mid for row in rows for mid in row.get('duplicate_message_ids', []) if type(mid) is int and mid > 0}
        from apps.whatsapp_bridge.models import WhatsAppMessage
        allowed = set(WhatsAppMessage.objects.filter(pk__in=duplicates, account__communication_account__company_id=options['company_id']).values_list('pk', flat=True))
        if allowed != duplicates:
            raise CommandError('Some duplicate links are missing or belong to another company.')
        with transaction.atomic():
            batch = TradingReviewBatch.objects.create(company_id=options['company_id'], name=options['name'].strip())
            TradingReviewBatchItem.objects.bulk_create([TradingReviewBatchItem(batch=batch, message_id=row['message_id'], position=index,
                group_id=row['group_id'], sampling_pool=row['sampling_pool'], duplicate_message_ids=[mid for mid in row.get('duplicate_message_ids', []) if mid in allowed]) for index, row in enumerate(rows, 1)])
        self.stdout.write(f'Imported batch {batch.pk} with {len(rows)} messages.')
