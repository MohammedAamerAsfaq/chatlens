import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.real_estate.models import RealEstateOpportunity
from apps.real_estate.services.opportunity_search import search_opportunities
from apps.tenancy.models import Company


class Command(BaseCommand):
    help = 'Evaluate Real Estate opportunity search against a labeled JSON benchmark.'

    def add_arguments(self, parser):
        parser.add_argument('--company', required=True, help='Company slug')
        parser.add_argument('--file', required=True, help='Benchmark JSON path')
        parser.add_argument(
            '--relevance', choices=['all', 'possible', 'strong'], default='possible',
        )
        parser.add_argument('--group-duplicates', action='store_true')

    def handle(self, *args, **options):
        company = Company.objects.filter(slug=options['company']).first()
        if not company:
            raise CommandError(f"Company '{options['company']}' was not found.")
        cases = self._load(options['file'])
        queryset = RealEstateOpportunity.objects.filter(company=company).select_related(
            'account', 'contact', 'assigned_to', 'source_chat', 'inquiry_medium',
            'requirement', 'property_candidate', 'property_candidate__property_type',
        ).prefetch_related('items__property_type', 'items__property', 'items__linked_by')

        top1_hits = reciprocal_rank = recall_at_five = 0.0
        for case in cases:
            expected = {int(value) for value in case['relevant_ids']}
            rows = search_opportunities(
                queryset,
                company=company,
                activity_type=case['activity_type'],
                query=case['query'],
                relevance=options['relevance'],
                group_duplicates=options['group_duplicates'],
            )
            ids = [row.pk for row in rows]
            top1_hits += bool(ids and ids[0] in expected)
            first_rank = next((index for index, value in enumerate(ids, 1) if value in expected), 0)
            reciprocal_rank += 1 / first_rank if first_rank else 0
            recall_at_five += len(expected.intersection(ids[:5])) / len(expected)
            state = 'PASS' if ids and ids[0] in expected else 'MISS'
            self.stdout.write(
                f"{state:4} {case.get('name', case['query'])}: top={ids[:5]} expected={sorted(expected)}"
            )

        count = len(cases)
        self.stdout.write(self.style.SUCCESS(
            f'Cases={count} Top1={top1_hits / count:.1%} '
            f'MRR={reciprocal_rank / count:.3f} Recall@5={recall_at_five / count:.1%}'
        ))

    @staticmethod
    def _load(path):
        try:
            cases = json.loads(Path(path).read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError) as exc:
            raise CommandError(f'Unable to read benchmark: {exc}') from exc
        if not isinstance(cases, list) or not cases:
            raise CommandError('Benchmark must be a non-empty JSON list.')
        for case in cases:
            if not all(case.get(key) for key in ('activity_type', 'query', 'relevant_ids')):
                raise CommandError('Every case needs activity_type, query, and relevant_ids.')
        return cases
