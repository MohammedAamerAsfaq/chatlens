from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.real_estate.models import (
    ActivityType, ClassificationStatus, EmbeddingStatus, PropertyRequirement,
    RealEstateOpportunity, RequirementEmbedding,
)
from apps.tenancy.models import Company

from .models import ApiKey


class ExternalRealEstateOpportunitySearchTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            name='External Search Estate', slug='external-search-estate',
            industry_type=Company.INDUSTRY_REAL_ESTATE,
        )
        self.other_company = Company.objects.create(
            name='Hidden Search Estate', slug='hidden-search-estate',
            industry_type=Company.INDUSTRY_REAL_ESTATE,
        )
        _, self.secret = ApiKey.generate(
            company=self.company, name='Search key', scopes=[ApiKey.SCOPE_DATA_READ],
        )
        self.client = APIClient()
        self.url = reverse('external-real-estate-opportunity-search')

    def create_opportunity(self, *, company=None, summary='Dubai home'):
        return RealEstateOpportunity.objects.create(
            company=company or self.company,
            activity_type=ActivityType.BUYING,
            classification_status=ClassificationStatus.CLASSIFIED,
            summary=summary,
            original_message=summary,
            first_seen_at=timezone.now(),
        )

    def get(self, params=None, secret=None):
        return self.client.get(
            self.url,
            params or {},
            HTTP_AUTHORIZATION=f'Api-Key {secret or self.secret}',
        )

    def test_requires_data_read_scope(self):
        _, secret = ApiKey.generate(company=self.company, name='No scope', scopes=[])

        response = self.get({'activity_type': ActivityType.BUYING}, secret=secret)

        self.assertEqual(response.status_code, 403)

    def test_blank_query_returns_only_key_company_lane(self):
        visible = self.create_opportunity()
        self.create_opportunity(company=self.other_company, summary='Private company record')

        response = self.get({'activity_type': ActivityType.BUYING})

        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual([row['id'] for row in response.json()['results']], [visible.pk])

    @patch('apps.real_estate.services.opportunity_search.ai_manager.embed')
    def test_query_uses_semantic_ranking_and_returns_score(self, embed):
        vector = [1.0, 0.0] + ([0.0] * 510)
        embed.return_value = vector
        opportunity = self.create_opportunity(summary='Marina apartment wanted')
        requirement = PropertyRequirement.objects.create(
            company=self.company, opportunity=opportunity,
        )
        RequirementEmbedding.objects.create(
            company=self.company,
            requirement=requirement,
            status=EmbeddingStatus.EMBEDDED,
            embedding=vector,
        )

        response = self.get({
            'activity_type': ActivityType.BUYING,
            'q': 'Marina apartment',
        })

        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual(response.json()['results'][0]['id'], opportunity.pk)
        self.assertEqual(response.json()['results'][0]['search_score'], 1.0)
        embed.assert_called_once_with('Marina apartment', company=self.company)

    def test_rejects_missing_activity_type(self):
        response = self.get()

        self.assertEqual(response.status_code, 400)
        self.assertIn('activity_type', response.json())
