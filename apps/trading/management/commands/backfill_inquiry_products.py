from django.core.management.base import BaseCommand

from apps.trading.models import Inquiry
from apps.trading.services.inquiry_product_service import create_inquiry_products_for_message


class Command(BaseCommand):
    help = 'Backfill InquiryProduct rows from existing Inquiry.products JSON.'

    def add_arguments(self, parser):
        parser.add_argument('--company-id', type=int, help='Limit backfill to one company.')
        parser.add_argument('--inquiry-id', type=int, help='Limit backfill to one inquiry.')
        parser.add_argument('--limit', type=int, help='Maximum inquiries to process.')
        parser.add_argument(
            '--latest',
            action='store_true',
            help='Process newest inquiries first instead of oldest first.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Count eligible inquiries without writing rows.',
        )

    def handle(self, *args, **options):
        qs = (
            Inquiry.objects
            .exclude(products=[])
            .select_related('company', 'account', 'contact')
            .prefetch_related('inquiry_messages__message')
        )
        qs = qs.order_by('-id' if options['latest'] else 'id')

        if options['company_id']:
            qs = qs.filter(company_id=options['company_id'])
        if options['inquiry_id']:
            qs = qs.filter(pk=options['inquiry_id'])
        if options['limit']:
            qs = qs[:options['limit']]

        processed = 0
        written = 0
        skipped = 0

        for inquiry in qs:
            processed += 1
            link = inquiry.inquiry_messages.order_by('id').first()
            if not link or not link.message_id:
                skipped += 1
                self.stderr.write(
                    f'Skipping inquiry {inquiry.pk}: no source message link.'
                )
                continue

            if options['dry_run']:
                continue

            written += create_inquiry_products_for_message(
                inquiry,
                link.message,
                inquiry.products,
            )

        self.stdout.write(
            self.style.SUCCESS(
                f'Processed {processed} inquiries; wrote/updated {written} product rows; skipped {skipped}.'
            )
        )
