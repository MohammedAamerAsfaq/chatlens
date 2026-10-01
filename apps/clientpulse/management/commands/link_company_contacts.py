from collections import Counter

from django.core.management.base import BaseCommand, CommandError

from apps.clientpulse.services.contact_linking import link_whatsapp_contact
from apps.tenancy.models import Company
from apps.whatsapp_bridge.models import WhatsAppContact


class Command(BaseCommand):
    help = 'Safely link WhatsApp contacts to exact canonical company-contact identities.'

    def add_arguments(self, parser):
        parser.add_argument('--company-id', type=int, required=True)
        parser.add_argument(
            '--apply', action='store_true',
            help='Persist links and ambiguity candidates. Without this flag the command is a dry run.',
        )

    def handle(self, *args, **options):
        company_id = options['company_id']
        if not Company.objects.filter(pk=company_id).exists():
            raise CommandError(f'Company {company_id} does not exist.')

        contacts = WhatsAppContact.objects.filter(
            account__communication_account__company_id=company_id,
        ).select_related('account__communication_account', 'company_contact')
        counts = Counter()
        for whatsapp_contact in contacts.iterator(chunk_size=500):
            result = link_whatsapp_contact(whatsapp_contact, apply=options['apply'])
            counts[result.status] += 1

        mode = 'APPLY' if options['apply'] else 'DRY RUN'
        summary = ', '.join(f'{key}={value}' for key, value in sorted(counts.items()))
        self.stdout.write(self.style.SUCCESS(f'{mode}: {summary or "no contacts"}'))
