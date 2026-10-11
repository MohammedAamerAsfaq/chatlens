from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from apps.real_estate.models import (
    ActivityType, ClassificationStatus, Listing, Property, PropertyCandidate,
    PropertyRequirement, RealEstateOpportunity,
)
from apps.real_estate.services.candidate_service import promote_candidate
from apps.real_estate.services.extraction_projection import project_extraction
from apps.tenancy.models import Company, CompanyMembership


class RealEstateInventoryTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name='Estate A', slug='estate-a', industry_type='real_estate')
        self.other = Company.objects.create(name='Estate B', slug='estate-b', industry_type='real_estate')
        self.user = get_user_model().objects.create_user('estate-owner')
        CompanyMembership.objects.create(
            company=self.company, user=self.user, role=CompanyMembership.ROLE_SUPER_USER,
        )

    def opportunity(self, activity):
        return RealEstateOpportunity.objects.create(
            company=self.company,
            activity_type=activity,
            classification_status=ClassificationStatus.CLASSIFIED,
            first_seen_at=timezone.now(),
        )

    def test_cross_company_listing_is_rejected(self):
        foreign_property = Property.objects.create(
            company=self.other, title='Foreign villa', property_type='villa',
        )
        listing = Listing(
            company=self.company, property=foreign_property, listing_type='sale',
            asking_price=1000000, is_verified=True,
        )
        with self.assertRaises(ValidationError):
            listing.full_clean()

    def test_database_prevents_conflicting_active_listings(self):
        property_record = Property.objects.create(
            company=self.company, title='Marina flat', property_type='apartment',
        )
        values = dict(
            company=self.company, property=property_record, listing_type='sale',
            asking_price=1000000, is_verified=True, status='active',
        )
        Listing.objects.create(**values)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Listing.objects.create(**values)

    def test_demand_projects_to_requirement_only(self):
        opportunity = self.opportunity(ActivityType.BUYING)
        projected = project_extraction(opportunity, {
            'confidence': 0.9,
            'property': {
                'property_type': 'apartment', 'locations': ['Dubai Marina'],
                'bedrooms': 2, 'budget': {'max': '2500000', 'currency': 'AED'},
            },
        })
        self.assertIsInstance(projected, PropertyRequirement)
        self.assertEqual(projected.acceptable_locations, ['Dubai Marina'])
        self.assertFalse(PropertyCandidate.objects.filter(opportunity=opportunity).exists())
        self.assertFalse(Property.objects.filter(company=self.company).exists())

    def test_supply_projects_to_candidate_then_explicit_promotion(self):
        opportunity = self.opportunity(ActivityType.LEASING_OFFER)
        candidate = project_extraction(opportunity, {
            'summary': 'Two-bedroom apartment for rent',
            'property': {
                'property_type': 'apartment', 'location': 'Business Bay',
                'bedrooms': 2, 'asking_price': 120000, 'currency': 'AED',
            },
        })
        self.assertIsInstance(candidate, PropertyCandidate)
        self.assertFalse(Property.objects.filter(company=self.company).exists())

        property_record, listing = promote_candidate(candidate, self.user)
        candidate.refresh_from_db()
        self.assertEqual(candidate.review_status, 'promoted')
        self.assertEqual(listing.property, property_record)
        self.assertEqual(listing.listing_type, 'lease')
        self.assertEqual(listing.status, 'draft')
        self.assertTrue(listing.is_verified)
