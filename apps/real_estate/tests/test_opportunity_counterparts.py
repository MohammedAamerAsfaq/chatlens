from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.real_estate.models import (
    ActivityType, CandidateEmbedding, ClassificationStatus, EmbeddingStatus, OpportunityItem,
    PropertyCandidate, PropertyRequirement, PropertyType, RealEstateOpportunity, RequirementEmbedding,
)
from apps.tenancy.models import Company
from apps.tenancy.testing import create_member

EMBED = 'apps.real_estate.services.opportunity_search.ai_manager.embed'


def vector(primary, secondary=0.0):
    return [primary, secondary] + ([0.0] * 510)


class OpportunityCounterpartTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name='Match Estate', slug='match-estate', industry_type='real_estate')
        self.other_company = Company.objects.create(name='Other Match', slug='other-match', industry_type='real_estate')
        self.user = get_user_model().objects.create_user('match-estate-owner')
        create_member(company=self.company, user=self.user, role='super_user')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.apartment = PropertyType.objects.create(company=self.company, name='Apartment', code='apartment')
        self.villa = PropertyType.objects.create(company=self.company, name='Villa', code='villa')

    def opportunity(self, activity, summary, embedding, *, company=None, **item):
        company = company or self.company
        record = RealEstateOpportunity.objects.create(
            company=company, activity_type=activity, classification_status=ClassificationStatus.CLASSIFIED,
            summary=summary, original_message=summary, first_seen_at=timezone.now(),
        )
        if activity in ActivityType.requirement_values():
            requirement = PropertyRequirement.objects.create(company=company, opportunity=record)
            RequirementEmbedding.objects.create(
                company=company, requirement=requirement, status=EmbeddingStatus.EMBEDDED, embedding=embedding,
            )
            kind, role = OpportunityItem.KIND_DEMAND, OpportunityItem.AMOUNT_BUDGET
        else:
            candidate = PropertyCandidate.objects.create(company=company, opportunity=record)
            CandidateEmbedding.objects.create(
                company=company, candidate=candidate, status=EmbeddingStatus.EMBEDDED, embedding=embedding,
            )
            kind, role = OpportunityItem.KIND_SUPPLY, OpportunityItem.AMOUNT_ASKING
        if item:
            OpportunityItem.objects.create(
                company=company, opportunity=record, sequence=1, item_kind=kind, amount_role=role, **item,
            )
        return record

    def counterparts(self, opportunity, **params):
        return self.client.get(f'/api/real-estate/opportunities/{opportunity.pk}/counterparts/', params)

    @patch(EMBED)
    def test_buyer_finds_sellers_ranked_by_the_hybrid_search(self, embed):
        embed.return_value = vector(1.0)
        buyer = self.opportunity(
            ActivityType.BUYING, 'Need a 2 bed apartment in Marina', vector(1.0),
            title='Marina apartment', property_type=self.apartment, location_raw='Dubai Marina',
            bedrooms_min=2, bedrooms_max=2, amount_max=2000000,
        )
        match = self.opportunity(
            ActivityType.SELLING, '2 bed Marina apartment for sale', vector(1.0),
            title='Marina apartment', property_type=self.apartment, location_raw='Dubai Marina',
            bedrooms_min=2, bedrooms_max=2, amount_min=1800000, amount_max=1800000,
        )
        villa = self.opportunity(
            ActivityType.SELLING, 'Villa for sale', vector(1.0),
            title='Villa', property_type=self.villa, bedrooms_min=2, bedrooms_max=2,
        )
        other_buyer = self.opportunity(ActivityType.BUYING, 'Another buyer', vector(1.0))
        self.opportunity(ActivityType.SELLING, 'Hidden', vector(1.0), company=self.other_company)

        response = self.counterparts(buyer, relevance='all')

        self.assertEqual(response.status_code, 200, response.json())
        data = response.json()
        ids = [row['id'] for row in data['results']]
        self.assertEqual(ids, [match.pk])  # the villa is a different property type: excluded
        self.assertNotIn(villa.pk, ids)
        self.assertNotIn(other_buyer.pk, ids)
        row = data['results'][0]
        self.assertIn('property type', row['search_reasons'])
        self.assertIn('bedrooms', row['search_reasons'])
        # A budget "up to 2M" covers a 1.8M asking price.
        self.assertIn('price/budget', row['search_reasons'])
        self.assertEqual(data['search_mode'], 'counterpart')
        interpretation = data['search_interpretation']
        self.assertEqual(interpretation['counterpart_activity_type'], 'selling')
        self.assertEqual((interpretation['amount_min'], interpretation['amount_max']), (0, 2000000))
        self.assertIn('Apartment', interpretation['canonical_query'])
        self.assertIn('up to 2000000 AED', interpretation['canonical_query'])
        embed.assert_called_once_with(interpretation['canonical_query'], company=self.company)

    @patch(EMBED)
    def test_seller_finds_buyers_whose_budget_ceiling_covers_the_price(self, embed):
        embed.return_value = vector(1.0)
        seller = self.opportunity(
            ActivityType.SELLING, 'Apartment for sale', vector(1.0),
            title='Apartment', property_type=self.apartment, amount_min=1500000, amount_max=1500000,
        )
        # Semantic similarity 0.6 leaves room under the 100% cap for the price to decide the order.
        affordable = self.opportunity(
            ActivityType.BUYING, 'Apartment wanted', vector(0.6, 0.8),
            title='Apartment', property_type=self.apartment, amount_max=2000000,
        )
        too_low = self.opportunity(
            ActivityType.BUYING, 'Apartment wanted', vector(0.6, 0.8),
            title='Apartment', property_type=self.apartment, amount_max=900000,
        )

        rows = self.counterparts(seller, relevance='all').json()['results']

        by_id = {row['id']: row for row in rows}
        self.assertIn('price/budget', by_id[affordable.pk]['search_reasons'])
        self.assertEqual(by_id[too_low.pk]['search_adjustments'][0]['reason'], 'Price/budget outside range')
        self.assertEqual(rows[0]['id'], affordable.pk)

    @patch(EMBED)
    def test_leasing_inquiry_finds_leasing_offers_and_offer_finds_inquiries(self, embed):
        embed.return_value = vector(1.0)
        tenant = self.opportunity(ActivityType.LEASING_INQUIRY, 'Studio to rent', vector(1.0), title='Studio')
        landlord = self.opportunity(ActivityType.LEASING_OFFER, 'Studio for rent', vector(1.0), title='Studio')
        self.opportunity(ActivityType.SELLING, 'Studio for sale', vector(1.0), title='Studio')

        self.assertEqual([row['id'] for row in self.counterparts(tenant, relevance='all').json()['results']], [landlord.pk])
        self.assertEqual([row['id'] for row in self.counterparts(landlord, relevance='all').json()['results']], [tenant.pk])

    @patch(EMBED)
    def test_falls_back_to_the_message_when_nothing_was_extracted(self, embed):
        embed.return_value = vector(1.0)
        buyer = self.opportunity(ActivityType.BUYING, 'Looking for a townhouse', vector(1.0))

        response = self.counterparts(buyer)

        self.assertEqual(response.status_code, 200, response.json())
        embed.assert_called_once_with('Looking for a townhouse', company=self.company)

    @patch(EMBED)
    def test_refuses_an_opportunity_with_nothing_to_match_on(self, embed):
        buyer = self.opportunity(ActivityType.BUYING, '', vector(1.0))

        response = self.counterparts(buyer)

        self.assertEqual(response.status_code, 400)
        self.assertIn('no property details or message', str(response.json()['non_field_errors']))
        embed.assert_not_called()

    def test_another_companys_opportunity_is_not_found(self):
        hidden = self.opportunity(ActivityType.BUYING, 'Hidden buyer', vector(1.0), company=self.other_company)

        self.assertEqual(self.counterparts(hidden).status_code, 404)

    @patch(EMBED)
    def test_open_ended_budget_does_not_match_every_price(self, embed):
        embed.return_value = vector(1.0)
        seller = self.opportunity(
            ActivityType.SELLING, 'Apartment for sale', vector(1.0),
            title='Apartment', amount_min=500000, amount_max=500000,
        )
        from_three_million = self.opportunity(
            ActivityType.BUYING, 'Apartment wanted', vector(1.0), title='Apartment', amount_min=3000000,
        )

        row = self.counterparts(seller, relevance='all').json()['results'][0]

        self.assertEqual(row['id'], from_three_million.pk)
        self.assertNotIn('price/budget', row['search_reasons'])

    @patch(EMBED)
    def test_the_fallback_other_type_is_not_used_to_filter(self, embed):
        embed.return_value = vector(1.0)
        other = PropertyType.objects.create(company=self.company, name='Other', code='other')
        seller = self.opportunity(
            ActivityType.SELLING, 'Unit 1001 at The One Hotel', vector(1.0),
            title='Unit 1001', property_type=other, location_raw='The One Hotel',
        )
        apartment_buyer = self.opportunity(
            ActivityType.BUYING, 'Apartment wanted', vector(1.0), title='Apartment', property_type=self.apartment,
        )

        data = self.counterparts(seller, relevance='all').json()

        self.assertEqual([row['id'] for row in data['results']], [apartment_buyer.pk])
        self.assertEqual(data['search_interpretation']['property_types'], [])
        self.assertNotIn('Other', data['search_interpretation']['canonical_query'])
