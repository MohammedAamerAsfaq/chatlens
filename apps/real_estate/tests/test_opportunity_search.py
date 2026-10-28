from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.real_estate.models import (
    ActivityType,
    CandidateEmbedding,
    ClassificationStatus,
    EmbeddingStatus,
    OpportunityItem,
    PropertyCandidate,
    PropertyRequirement,
    RealEstateOpportunity,
    RequirementEmbedding,
)
from apps.tenancy.models import Company, CompanyMembership


class OpportunitySearchApiTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            name='Search Estate', slug='search-estate', industry_type='real_estate',
        )
        self.other_company = Company.objects.create(
            name='Other Estate', slug='other-search-estate', industry_type='real_estate',
        )
        self.user = get_user_model().objects.create_user('search-estate-owner')
        CompanyMembership.objects.create(
            company=self.company,
            user=self.user,
            role=CompanyMembership.ROLE_SUPER_USER,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def create_opportunity(self, activity, *, company=None, summary='Property request'):
        return RealEstateOpportunity.objects.create(
            company=company or self.company,
            activity_type=activity,
            classification_status=ClassificationStatus.CLASSIFIED,
            summary=summary,
            original_message=summary,
            first_seen_at=timezone.now(),
        )

    @staticmethod
    def vector(primary, secondary=0.0):
        return [primary, secondary] + ([0.0] * 510)

    @patch('apps.real_estate.services.opportunity_search.ai_manager.embed')
    def test_semantic_search_ranks_demand_and_returns_all_items(self, embed):
        embed.return_value = self.vector(1.0)
        closest = self.create_opportunity(ActivityType.BUYING, summary='Buy two Dubai homes')
        requirement = PropertyRequirement.objects.create(company=self.company, opportunity=closest)
        RequirementEmbedding.objects.create(
            company=self.company,
            requirement=requirement,
            status=EmbeddingStatus.EMBEDDED,
            embedding=self.vector(1.0),
        )
        for sequence, title in enumerate(('Marina apartment', 'Jumeirah villa'), start=1):
            OpportunityItem.objects.create(
                company=self.company,
                opportunity=closest,
                sequence=sequence,
                item_kind=OpportunityItem.KIND_DEMAND,
                amount_role=OpportunityItem.AMOUNT_BUDGET,
                title=title,
            )

        farther = self.create_opportunity(ActivityType.BUYING, summary='Buy a remote warehouse')
        farther_requirement = PropertyRequirement.objects.create(
            company=self.company, opportunity=farther,
        )
        RequirementEmbedding.objects.create(
            company=self.company,
            requirement=farther_requirement,
            status=EmbeddingStatus.EMBEDDED,
            embedding=self.vector(0.0, 1.0),
        )

        response = self.client.get(
            '/api/real-estate/opportunities/search/',
            {'activity_type': ActivityType.BUYING, 'q': 'Dubai homes'},
        )

        self.assertEqual(response.status_code, 200, response.json())
        rows = response.json()['results']
        self.assertEqual([row['id'] for row in rows], [closest.pk, farther.pk])
        self.assertEqual([item['title'] for item in rows[0]['items']], [
            'Marina apartment', 'Jumeirah villa',
        ])
        self.assertEqual(rows[0]['search_score'], 1.0)
        embed.assert_called_once_with('Dubai homes', company=self.company)

    @patch('apps.real_estate.services.opportunity_search.ai_manager.embed')
    def test_supply_search_excludes_other_lanes_and_companies(self, embed):
        embed.return_value = self.vector(1.0)
        visible = self.create_opportunity(ActivityType.SELLING, summary='Villa for sale')
        candidate = PropertyCandidate.objects.create(company=self.company, opportunity=visible)
        CandidateEmbedding.objects.create(
            company=self.company,
            candidate=candidate,
            status=EmbeddingStatus.EMBEDDED,
            embedding=self.vector(1.0),
        )
        self.create_opportunity(ActivityType.LEASING_OFFER, summary='Apartment for rent')
        self.create_opportunity(
            ActivityType.SELLING, company=self.other_company, summary='Hidden villa',
        )

        response = self.client.get(
            '/api/real-estate/opportunities/search/',
            {'activity_type': ActivityType.SELLING, 'q': 'villa'},
        )

        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual([row['id'] for row in response.json()['results']], [visible.pk])

    @patch('apps.real_estate.services.opportunity_search.ai_manager.embed')
    def test_blank_query_browses_lane_without_requiring_embedding(self, embed):
        visible = self.create_opportunity(ActivityType.LEASING_INQUIRY)

        response = self.client.get(
            '/api/real-estate/opportunities/search/',
            {'activity_type': ActivityType.LEASING_INQUIRY, 'q': ''},
        )

        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual([row['id'] for row in response.json()['results']], [visible.pk])
        embed.assert_not_called()

    def test_activity_is_required(self):
        response = self.client.get('/api/real-estate/opportunities/search/')

        self.assertEqual(response.status_code, 400)
        self.assertIn('activity_type', response.json())
