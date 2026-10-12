from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.ai_providers.models import AIProviderConfig
from apps.ai_providers.manager import ai_manager
from apps.real_estate.models import (
    ActivityType, CandidateEmbedding, ClassificationStatus, Listing,
    ListingEmbedding, Property, PropertyAddress, PropertyCandidate,
    PropertyEmbedding, PropertyRequirement, RealEstateOpportunity,
    RequirementEmbedding,
)
from apps.real_estate.services.embedding_documents import property_document
from apps.real_estate.services.embedding_service import embed_real_estate
from apps.task_management.models import BackgroundTask
from apps.tenancy.models import Company, CompanyMembership
from apps.real_estate.services.property_types import seed_default_property_types


class RealEstateEmbeddingTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            name='Embedded Estate', slug='embedded-estate', industry_type='real_estate',
        )
        self.other = Company.objects.create(
            name='Other Embedded Estate', slug='other-embedded-estate', industry_type='real_estate',
        )
        self.types = {item.code: item for item in seed_default_property_types(self.company)}
        self.user = get_user_model().objects.create_user('embedding-owner')
        CompanyMembership.objects.create(
            company=self.company, user=self.user, role=CompanyMembership.ROLE_SUPER_USER,
        )
        AIProviderConfig.objects.create(
            company=self.company, display_name='Test vectors', provider='voyage',
            capability='embedding', api_key='test', model='voyage-3', is_active=True,
        )
        self.property = Property.objects.create(
            company=self.company, title='Marina View Apartment', property_type=self.types['apartment'],
            description='Bright waterfront home', bedrooms=2, bathrooms=2,
        )
        PropertyAddress.objects.create(
            company=self.company, property=self.property, city='Dubai',
            community='Dubai Marina', unit_number='1204', normalized_location='Dubai Marina, Dubai',
        )

    def opportunity(self, activity, summary):
        return RealEstateOpportunity.objects.create(
            company=self.company, activity_type=activity,
            classification_status=ClassificationStatus.CLASSIFIED,
            summary=summary, original_message=summary, first_seen_at=timezone.now(),
        )

    def test_property_document_uses_search_context_not_private_identifiers(self):
        document = property_document(
            Property.objects.select_related('address').prefetch_related('media').get(pk=self.property.pk),
        )
        self.assertIn('Location: Dubai Marina, Dubai', document)
        self.assertIn('Bedrooms: 2.0', document)
        self.assertNotIn('1204', document)

    @patch.object(ai_manager, 'embed', return_value=[0.1] * 512)
    def test_four_entity_types_store_vectors_in_separate_tables(self, mocked_embed):
        listing = Listing.objects.create(
            company=self.company, property=self.property, listing_type='sale',
            asking_price=2200000, is_verified=True,
        )
        requirement = PropertyRequirement.objects.create(
            company=self.company,
            opportunity=self.opportunity(ActivityType.BUYING, 'Need a two-bedroom marina apartment'),
            acceptable_locations=['Dubai Marina'], budget_max=2500000,
        )
        candidate = PropertyCandidate.objects.create(
            company=self.company,
            opportunity=self.opportunity(ActivityType.SELLING, 'Apartment offered in Dubai Marina'),
            title='Seller apartment', location_raw='Dubai Marina', asking_price=2200000,
        )

        for kind, target in (
            ('property', self.property), ('listing', listing),
            ('requirement', requirement), ('candidate', candidate),
        ):
            self.assertTrue(embed_real_estate(kind, target.pk, self.company.pk))

        self.assertTrue(PropertyEmbedding.objects.filter(property=self.property, status='embedded').exists())
        self.assertTrue(ListingEmbedding.objects.filter(listing=listing, status='embedded').exists())
        self.assertTrue(RequirementEmbedding.objects.filter(requirement=requirement, status='embedded').exists())
        self.assertTrue(CandidateEmbedding.objects.filter(candidate=candidate, status='embedded').exists())
        self.property.refresh_from_db()
        self.assertEqual(self.property.title, 'Marina View Apartment')
        self.assertEqual(mocked_embed.call_count, 4)

    def test_embedding_rejects_cross_company_target(self):
        row = PropertyEmbedding(company=self.other, property=self.property)
        with self.assertRaises(ValidationError):
            row.full_clean()

    def test_dispatch_uses_dedicated_company_owned_queue(self):
        from apps.real_estate.services.embedding_dispatch import enqueue_embedding

        task = enqueue_embedding('property', self.property.pk, revision='test-revision')
        self.assertEqual(task.queue_name, 'real_estate_embeddings')
        self.assertEqual(task.company, self.company)
        self.assertEqual(task.payload['company_id'], self.company.pk)
        self.assertEqual(task.payload['object_id'], self.property.pk)

    def test_status_endpoint_is_company_scoped(self):
        PropertyEmbedding.objects.create(company=self.company, property=self.property, status='pending')
        client = APIClient()
        client.force_authenticate(self.user)

        response = client.get('/api/real-estate/properties/embedding-status/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['total'], 1)
        self.assertEqual(response.json()['pending'], 1)

    def test_backfill_endpoint_enqueues_missing_vectors(self):
        client = APIClient()
        client.force_authenticate(self.user)

        response = client.post('/api/real-estate/properties/backfill-embeddings/', {}, format='json')

        self.assertEqual(response.status_code, 202, response.json())
        self.assertEqual(response.json()['enqueued'], 1)
        self.assertTrue(BackgroundTask.objects.filter(
            task_key='real_estate.embed_property', company=self.company,
            payload__object_id=self.property.pk,
        ).exists())

    def test_property_save_automatically_enqueues_after_commit(self):
        with self.captureOnCommitCallbacks(execute=True):
            record = Property.objects.create(
                company=self.company, title='Signal villa', property_type=self.types['villa'],
            )

        self.assertTrue(BackgroundTask.objects.filter(
            task_key='real_estate.embed_property', company=self.company,
            payload__object_id=record.pk,
        ).exists())
