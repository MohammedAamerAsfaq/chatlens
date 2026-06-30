import logging
from django.core.management.base import BaseCommand
from django.db.models import Q

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Backfill vector embeddings for messages that do not yet have one.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--account-id', type=int, default=None,
            help='Limit to a specific WhatsApp account (default: all accounts)',
        )
        parser.add_argument(
            '--batch-size', type=int, default=500,
            help='Number of message IDs fetched per DB query (default: 500)',
        )
        parser.add_argument(
            '--async', dest='use_async', action='store_true', default=False,
            help='Queue Celery tasks instead of embedding synchronously (default: sync)',
        )
        parser.add_argument(
            '--limit', type=int, default=None,
            help='Stop after embedding this many messages (useful for testing)',
        )

    def handle(self, *args, **options):
        from apps.whatsapp_bridge.models import WhatsAppMessage

        qs = (
            WhatsAppMessage.objects
            .filter(message_text__isnull=False)
            .exclude(message_text='')
            .filter(Q(embedding__isnull=True))
            .order_by('id')
        )

        account_id = options['account_id']
        if account_id:
            qs = qs.filter(account_id=account_id)

        total = qs.count()
        self.stdout.write(f'Messages without embeddings: {total}')
        if total == 0:
            return

        limit = options['limit']
        batch_size = options['batch_size']
        use_async = options['use_async']
        processed = 0

        if use_async:
            from apps.message_intelligence.tasks import generate_message_embedding
            for msg_id in qs.values_list('id', flat=True)[:limit]:
                generate_message_embedding.delay(msg_id)
                processed += 1
                if processed % 1000 == 0:
                    self.stdout.write(f'  Queued {processed}/{total or "?"}...')
            self.stdout.write(self.style.SUCCESS(f'Queued {processed} Celery tasks.'))
        else:
            from apps.message_intelligence.services.embedding_service import embed_messages_batch
            offset = 0
            while True:
                ids = list(qs.values_list('id', flat=True)[offset:offset + batch_size])
                if not ids:
                    break
                if limit and processed + len(ids) > limit:
                    ids = ids[:limit - processed]

                result = embed_messages_batch(ids)
                processed += result['embedded']
                self.stdout.write(
                    f'  chunk offset={offset} | '
                    f"embedded={result['embedded']} skipped={result['skipped']} errors={result['errors']}"
                )
                offset += batch_size
                if limit and processed >= limit:
                    break

            self.stdout.write(self.style.SUCCESS(f'Done. Embedded {processed} messages.'))
