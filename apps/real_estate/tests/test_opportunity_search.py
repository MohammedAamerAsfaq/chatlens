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
    PropertyAttributeAlias,
    PropertyAttributeDefinition,
    PropertyAttributeOption,
    PropertyType,
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
            {'activity_type': ActivityType.BUYING, 'q': 'Dubai homes', 'relevance': 'all'},
        )

        self.assertEqual(response.status_code, 200, response.json())
        rows = response.json()['results']
        self.assertEqual([row['id'] for row in rows], [closest.pk, farther.pk])
        self.assertEqual([item['title'] for item in rows[0]['items']], [
            'Marina apartment', 'Jumeirah villa',
        ])
        self.assertEqual(rows[0]['search_score'], 1.0)
        self.assertEqual(rows[0]['search_relevance'], 'strong')
        self.assertIn('query terms', rows[0]['search_reasons'])
        embed.assert_called_once_with('Dubai homes', company=self.company)

    @patch('apps.real_estate.services.opportunity_search.ai_manager.embed')
    def test_possible_relevance_removes_weak_results(self, embed):
        embed.return_value = self.vector(1.0)
        opportunity = self.create_opportunity(ActivityType.BUYING, summary='Unrelated record')
        requirement = PropertyRequirement.objects.create(company=self.company, opportunity=opportunity)
        RequirementEmbedding.objects.create(
            company=self.company, requirement=requirement,
            status=EmbeddingStatus.EMBEDDED, embedding=self.vector(0.0, 1.0),
        )

        response = self.client.get('/api/real-estate/opportunities/search/', {
            'activity_type': ActivityType.BUYING, 'q': 'warehouse in Sharjah',
            'relevance': 'possible',
        })

        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual(response.json()['results'], [])

    @patch('apps.real_estate.services.opportunity_search.ai_manager.embed')
    def test_exact_budget_can_rerank_a_nearer_semantic_result(self, embed):
        embed.return_value = self.vector(1.0)
        exact = self.create_opportunity(ActivityType.BUYING, summary='Apartment wanted')
        exact_requirement = PropertyRequirement.objects.create(company=self.company, opportunity=exact)
        RequirementEmbedding.objects.create(
            company=self.company, requirement=exact_requirement,
            status=EmbeddingStatus.EMBEDDED, embedding=self.vector(0.8, 0.6),
        )
        OpportunityItem.objects.create(
            company=self.company, opportunity=exact, sequence=1,
            item_kind=OpportunityItem.KIND_DEMAND, amount_role=OpportunityItem.AMOUNT_BUDGET,
            title='Apartment', amount_min=1300000, amount_max=1300000,
        )
        nearby = self.create_opportunity(ActivityType.BUYING, summary='Apartment wanted')
        nearby_requirement = PropertyRequirement.objects.create(company=self.company, opportunity=nearby)
        RequirementEmbedding.objects.create(
            company=self.company, requirement=nearby_requirement,
            status=EmbeddingStatus.EMBEDDED, embedding=self.vector(1.0),
        )
        OpportunityItem.objects.create(
            company=self.company, opportunity=nearby, sequence=1,
            item_kind=OpportunityItem.KIND_DEMAND, amount_role=OpportunityItem.AMOUNT_BUDGET,
            title='Apartment', amount_min=1500000, amount_max=1500000,
        )

        response = self.client.get('/api/real-estate/opportunities/search/', {
            'activity_type': ActivityType.BUYING, 'q': 'AED 1.3m', 'relevance': 'all',
        })

        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual(response.json()['results'][0]['id'], exact.pk)
        self.assertIn('price/budget', response.json()['results'][0]['search_reasons'])

    @patch('apps.real_estate.services.opportunity_search.ai_manager.embed')
    def test_similar_results_can_be_grouped_without_deleting_records(self, embed):
        embed.return_value = self.vector(1.0)
        opportunities = []
        property_type = PropertyType.objects.create(
            company=self.company, name='Apartment', code='apartment',
        )
        for summary in ('Marina apartment offered', 'Apartment available in Marina'):
            opportunity = self.create_opportunity(ActivityType.SELLING, summary=summary)
            candidate = PropertyCandidate.objects.create(company=self.company, opportunity=opportunity)
            CandidateEmbedding.objects.create(
                company=self.company, candidate=candidate,
                status=EmbeddingStatus.EMBEDDED, embedding=self.vector(1.0),
            )
            OpportunityItem.objects.create(
                company=self.company, opportunity=opportunity, sequence=1,
                item_kind=OpportunityItem.KIND_SUPPLY, amount_role=OpportunityItem.AMOUNT_ASKING,
                title='Marina apartment', property_type=property_type,
                location_raw='Dubai Marina', amount_min=2000000, amount_max=2000000,
            )
            opportunities.append(opportunity)

        response = self.client.get('/api/real-estate/opportunities/search/', {
            'activity_type': ActivityType.SELLING, 'q': 'Marina apartment',
            'relevance': 'all', 'group_duplicates': 'true',
        })

        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual(len(response.json()['results']), 1)
        row = response.json()['results'][0]
        self.assertEqual(row['duplicate_count'], 2)
        self.assertEqual(len(row['duplicate_opportunity_ids']), 1)
        self.assertEqual(RealEstateOpportunity.objects.filter(pk__in=[item.pk for item in opportunities]).count(), 2)

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

    def test_relevance_policy_is_validated(self):
        response = self.client.get('/api/real-estate/opportunities/search/', {
            'activity_type': ActivityType.BUYING, 'relevance': 'unsupported',
        })

        self.assertEqual(response.status_code, 400)
        self.assertIn('relevance', response.json())

    def test_studio_is_parsed_as_zero_bedrooms(self):
        from apps.real_estate.services.opportunity_search_query import parse_constraints

        constraints = parse_constraints('studio apartment in Dubai Marina', self.company)

        self.assertEqual(constraints.bedrooms, 0)

    def test_company_attribute_alias_resolves_to_canonical_bedroom_value(self):
        from apps.real_estate.services.property_attribute_catalog import seed_attribute_catalog
        from apps.real_estate.services.opportunity_search_query import parse_constraints

        seed_attribute_catalog(self.company)
        definition = PropertyAttributeDefinition.objects.get(
            company=self.company, code='bedrooms',
        )
        option = PropertyAttributeOption.objects.get(definition=definition, code='2')
        PropertyAttributeAlias.objects.create(
            company=self.company, definition=definition, option=option,
            alias='double room configuration',
        )

        constraints = parse_constraints(
            'Need an apartment with double room configuration', self.company,
        )

        self.assertEqual(constraints.bedrooms, 2)

    def test_hybrid_search_resolves_catalog_attribute_aliases(self):
        from apps.real_estate.services.opportunity_search_query import parse_constraints

        constraints = parse_constraints(
            'Need a fully furnished apartment with 2 baths', self.company,
        )
        attributes = {item['code']: item for item in constraints.attributes}

        self.assertEqual(attributes['furnishing']['value'], 'furnished')
        self.assertEqual(attributes['bathrooms']['numeric_value'], 2)

    def test_structured_attribute_alias_is_corrected_to_master_value(self):
        from apps.real_estate.services.opportunity_search_query import build_constraints

        constraints = build_constraints(
            query='ready with two bathrooms', company=self.company,
            attributes={'bathrooms': '2 baths', 'furnishing': 'fully furnished'},
        )
        attributes = {item['code']: item for item in constraints.attributes}

        self.assertEqual(attributes['bathrooms']['numeric_value'], 2)
        self.assertEqual(attributes['furnishing']['value'], 'furnished')

    @patch('apps.real_estate.services.opportunity_search.ai_manager.embed')
    def test_recognized_wrong_property_type_is_excluded(self, embed):
        embed.return_value = self.vector(1.0)
        apartment = PropertyType.objects.create(
            company=self.company, name='Apartment', code='apartment',
        )
        villa = PropertyType.objects.create(
            company=self.company, name='Villa', code='villa',
        )
        expected = self._embedded_demand('Apartment wanted', apartment, bedrooms=2)
        self._embedded_demand('Villa wanted', villa, bedrooms=2)

        response = self.client.get('/api/real-estate/opportunities/search/', {
            'activity_type': ActivityType.BUYING, 'q': '2 bedroom apartment',
            'relevance': 'all',
        })

        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual([row['id'] for row in response.json()['results']], [expected.pk])

    @patch('apps.real_estate.services.opportunity_search.ai_manager.embed')
    def test_adjacent_bedroom_count_is_kept_with_explained_penalty(self, embed):
        embed.return_value = self.vector(1.0)
        apartment = PropertyType.objects.create(
            company=self.company, name='Apartment', code='apartment',
        )
        opportunity = self._embedded_demand('Three bedroom apartment', apartment, bedrooms=3)

        response = self.client.get('/api/real-estate/opportunities/search/', {
            'activity_type': ActivityType.BUYING, 'q': '2 bedroom apartment',
            'relevance': 'all',
        })

        self.assertEqual(response.status_code, 200, response.json())
        row = response.json()['results'][0]
        self.assertEqual(row['id'], opportunity.pk)
        self.assertEqual(row['search_penalty'], 0.06)
        self.assertEqual(row['search_adjustments'][0]['reason'], 'Nearest bedroom count')

    def test_compact_price_is_normalized_before_persistence_projection(self):
        from apps.real_estate.services.opportunity_item_projection import _money_number

        self.assertEqual(_money_number('1m'), 1000000)
        self.assertEqual(_money_number('850k'), 850000)

    def _embedded_demand(self, summary, property_type, *, bedrooms):
        opportunity = self.create_opportunity(ActivityType.BUYING, summary=summary)
        requirement = PropertyRequirement.objects.create(
            company=self.company, opportunity=opportunity,
        )
        RequirementEmbedding.objects.create(
            company=self.company, requirement=requirement,
            status=EmbeddingStatus.EMBEDDED, embedding=self.vector(1.0),
        )
        OpportunityItem.objects.create(
            company=self.company, opportunity=opportunity, sequence=1,
            item_kind=OpportunityItem.KIND_DEMAND,
            amount_role=OpportunityItem.AMOUNT_BUDGET,
            title=summary, property_type=property_type,
            bedrooms_min=bedrooms, bedrooms_max=bedrooms,
        )
        return opportunity

    @patch('apps.real_estate.services.opportunity_search_input.call_real_estate_agent')
    @patch('apps.real_estate.services.opportunity_search.ai_manager.embed')
    def test_structured_search_normalizes_then_embeds_and_ranks_ranges(self, embed, call_agent):
        embed.return_value = self.vector(1.0)
        call_agent.return_value = '''{
          "property_types": ["Apartment"],
          "locations": ["Dubai Marina"],
          "bedrooms_min": 2,
          "bedrooms_max": 3,
          "amount_min": 1200000,
          "amount_max": 1500000,
          "currency": "AED",
          "amenities": ["sea view"],
          "keywords": ["ready"]
        }'''
        property_type = PropertyType.objects.create(
            company=self.company, name='Apartment', code='apartment',
        )
        opportunity = self.create_opportunity(ActivityType.BUYING, summary='Marina home wanted')
        requirement = PropertyRequirement.objects.create(
            company=self.company, opportunity=opportunity,
        )
        RequirementEmbedding.objects.create(
            company=self.company, requirement=requirement,
            status=EmbeddingStatus.EMBEDDED, embedding=self.vector(1.0),
        )
        OpportunityItem.objects.create(
            company=self.company, opportunity=opportunity, sequence=1,
            item_kind=OpportunityItem.KIND_DEMAND, amount_role=OpportunityItem.AMOUNT_BUDGET,
            title='Marina apartment', property_type=property_type,
            location_raw='Dubai Marina', bedrooms_min=3, bedrooms_max=3,
            amount_min=1400000, amount_max=1400000, currency='AED',
        )

        response = self.client.get('/api/real-estate/opportunities/search/', {
            'activity_type': ActivityType.BUYING,
            'q': 'family flat at marina around 1.2 to 1.5m',
            'search_mode': 'structured',
            'relevance': 'all',
        })

        self.assertEqual(response.status_code, 200, response.json())
        data = response.json()
        self.assertEqual(data['search_mode'], 'structured')
        self.assertEqual(data['search_interpretation']['bedrooms_min'], 2)
        self.assertIn('Dubai Marina', data['search_interpretation']['canonical_query'])
        self.assertEqual(data['results'][0]['id'], opportunity.pk)
        self.assertIn('bedrooms', data['results'][0]['search_reasons'])
        self.assertIn('price/budget', data['results'][0]['search_reasons'])
        call_agent.assert_called_once()
        embed.assert_called_once_with(
            data['search_interpretation']['canonical_query'], company=self.company,
        )

    def test_search_mode_is_validated_before_any_ai_call(self):
        response = self.client.get('/api/real-estate/opportunities/search/', {
            'activity_type': ActivityType.BUYING,
            'q': 'Dubai apartment',
            'search_mode': 'unsupported',
        })

        self.assertEqual(response.status_code, 400)
        self.assertIn('search_mode', response.json())
