from django.core.management.base import BaseCommand, CommandError

from apps.clientpulse.services.contact_linking import generate_identity_merge_candidates
from apps.tenancy.models import Company


class Command(BaseCommand):
    help = 'Find exact same-company contact identity collisions for manual review.'

    def add_arguments(self, parser):
        parser.add_argument('--company-id', type=int, required=True)
        parser.add_argument('--apply', action='store_true')

    def handle(self, *args, **options):
        company_id = options['company_id']
        if not Company.objects.filter(pk=company_id).exists():
            raise CommandError(f'Company {company_id} does not exist.')
        count = generate_identity_merge_candidates(
            company_id, apply=options['apply'],
        )
        mode = 'created/reused' if options['apply'] else 'found'
        self.stdout.write(self.style.SUCCESS(f'{count} candidate pair(s) {mode}.'))
