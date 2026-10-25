from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.real_estate.models import (
    InquiryMedium, OpportunityItem, PropertyCandidate, PropertyRequirement,
    RealEstateOpportunity,
)
from apps.real_estate.services.inquiry_media import seed_default_inquiry_media
from apps.real_estate.services.property_types import seed_default_property_types
from apps.tenancy.models import Company, CompanyMembership


class ManualOpportunityApiTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            name='Manual Estate', slug='manual-estate', industry_type='real_estate',
        )
        self.other_company = Company.objects.create(
            name='Other Estate', slug='manual-other-estate', industry_type='real_estate',
        )
        self.user = get_user_model().objects.create_user('manual-estate-owner')
        CompanyMembership.objects.create(
            company=self.company, user=self.user, role=CompanyMembership.ROLE_SUPER_USER,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        seed_default_property_types(self.company)
        self.medium = seed_default_inquiry_media(self.company)[0]

    def payload(self, activity_type):
        return {
            'activity_type': activity_type,
            'inquiry_medium': self.medium.pk,
            'source_party_name': 'Sample Client',
            'source_contact_detail': '+971500000001',
            'source_reference': 'CALL-1001',
            'market_scope': 'local',
            'status': 'new',
            'summary': 'Client needs a two-bedroom apartment in Dubai Marina.',
            'original_message': 'Need 2BR Dubai Marina, budget AED 2 million.',
            'items': [{
                'title': 'Dubai Marina two-bedroom apartment',
                'property_type': 'apartment',
                'locations': ['Dubai Marina'],
                'bedrooms_min': '2',
                'bedrooms_max': '2',
                'area_min': '1100',
                'area_max': '1400',
                'area_unit': 'sqft',
                'amount_min': '1800000',
                'amount_max': '2000000',
                'currency': 'AED',
                'required_amenities': ['Parking'],
                'preferred_amenities': ['Marina view'],
                'free_form_constraints': 'Vacant on transfer.',
            }],
        }

    def test_medium_list_seeds_company_defaults(self):
        InquiryMedium.objects.filter(company=self.company).delete()

        response = self.client.get('/api/real-estate/inquiry-media/?page_size=100')

        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual(
            {row['code'] for row in response.json()['results']},
            {'phone', 'email', 'whatsapp', 'telegram', 'signal', 'website', 'meeting'},
        )
        self.assertFalse(InquiryMedium.objects.filter(company=self.other_company).exists())

    def test_manual_buying_inquiry_creates_board_card_and_requirement(self):
        response = self.client.post(
            '/api/real-estate/opportunities/manual/', self.payload('buying'), format='json',
        )

        self.assertEqual(response.status_code, 201, response.json())
        opportunity = RealEstateOpportunity.objects.get(pk=response.json()['id'])
        self.assertEqual(opportunity.activity_type, 'buying')
        self.assertEqual(opportunity.inquiry_medium, self.medium)
        self.assertEqual(opportunity.source_party_name, 'Sample Client')
        requirement = PropertyRequirement.objects.get(opportunity=opportunity)
        self.assertEqual(requirement.required_amenities, ['Parking'])
        self.assertEqual(requirement.preferred_amenities, ['Marina view'])
        self.assertEqual(requirement.free_form_constraints, 'Vacant on transfer.')
        item = OpportunityItem.objects.get(opportunity=opportunity)
        self.assertEqual(item.item_kind, OpportunityItem.KIND_DEMAND)
        self.assertEqual(item.amount_min, 1800000)
        self.assertEqual(item.amount_max, 2000000)

        board = self.client.get('/api/real-estate/opportunities/?activity_type=buying')
        self.assertEqual(board.status_code, 200, board.json())
        self.assertEqual([row['id'] for row in board.json()['results']], [opportunity.pk])

    def test_manual_selling_inquiry_creates_candidate_and_supply_item(self):
        payload = self.payload('selling')
        response = self.client.post(
            '/api/real-estate/opportunities/manual/', payload, format='json',
        )

        self.assertEqual(response.status_code, 201, response.json())
        opportunity = RealEstateOpportunity.objects.get(pk=response.json()['id'])
        self.assertTrue(PropertyCandidate.objects.filter(opportunity=opportunity).exists())
        item = OpportunityItem.objects.get(opportunity=opportunity)
        self.assertEqual(item.item_kind, OpportunityItem.KIND_SUPPLY)
        self.assertEqual(item.amount_min, 1800000)
        self.assertEqual(item.amount_max, 2000000)

    def test_manual_leasing_inquiry_creates_demand_card(self):
        response = self.client.post(
            '/api/real-estate/opportunities/manual/',
            self.payload('leasing_inquiry'),
            format='json',
        )

        self.assertEqual(response.status_code, 201, response.json())
        opportunity = RealEstateOpportunity.objects.get(pk=response.json()['id'])
        self.assertTrue(PropertyRequirement.objects.filter(opportunity=opportunity).exists())
        self.assertEqual(
            OpportunityItem.objects.get(opportunity=opportunity).item_kind,
            OpportunityItem.KIND_DEMAND,
        )

    def test_manual_leasing_offer_creates_supply_card(self):
        response = self.client.post(
            '/api/real-estate/opportunities/manual/',
            self.payload('leasing_offer'),
            format='json',
        )

        self.assertEqual(response.status_code, 201, response.json())
        opportunity = RealEstateOpportunity.objects.get(pk=response.json()['id'])
        self.assertTrue(PropertyCandidate.objects.filter(opportunity=opportunity).exists())
        self.assertEqual(
            OpportunityItem.objects.get(opportunity=opportunity).item_kind,
            OpportunityItem.KIND_SUPPLY,
        )

    def test_manual_inquiry_rejects_medium_from_another_company(self):
        foreign_medium = seed_default_inquiry_media(self.other_company)[0]
        payload = self.payload('buying')
        payload['inquiry_medium'] = foreign_medium.pk

        response = self.client.post(
            '/api/real-estate/opportunities/manual/', payload, format='json',
        )

        self.assertEqual(response.status_code, 400, response.json())
        self.assertIn('inquiry_medium', response.json())
        self.assertFalse(RealEstateOpportunity.objects.exists())
