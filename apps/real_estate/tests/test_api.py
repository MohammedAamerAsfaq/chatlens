from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.real_estate.models import (
    ActivityType, ClassificationStatus, Listing, Property, PropertyCandidate, PropertyType,
    RealEstateOpportunity,
)
from apps.tenancy.models import Company, CompanyMembership
from apps.real_estate.services.property_types import seed_default_property_types


class RealEstateApiTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name='API Estate', slug='api-estate', industry_type='real_estate')
        self.other = Company.objects.create(name='Other Estate', slug='other-estate', industry_type='real_estate')
        self.types = {item.code: item for item in seed_default_property_types(self.company)}
        self.other_types = {item.code: item for item in seed_default_property_types(self.other)}
        self.user = get_user_model().objects.create_user('api-estate-owner')
        CompanyMembership.objects.create(
            company=self.company, user=self.user, role=CompanyMembership.ROLE_SUPER_USER,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_properties_are_company_scoped_and_archived_on_delete(self):
        visible = Property.objects.create(company=self.company, title='Visible flat', property_type=self.types['apartment'])
        listing = Listing.objects.create(
            company=self.company, property=visible, listing_type='sale', asking_price=100,
            is_verified=True, status='active',
        )
        Property.objects.create(company=self.other, title='Hidden villa', property_type=self.other_types['villa'])

        response = self.client.get('/api/real-estate/properties/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row['id'] for row in response.json()['results']], [visible.pk])

        response = self.client.delete(f'/api/real-estate/properties/{visible.pk}/')
        self.assertEqual(response.status_code, 204)
        visible.refresh_from_db()
        self.assertTrue(visible.is_archived)
        self.assertEqual(visible.availability_status, 'inactive')
        listing.refresh_from_db()
        self.assertTrue(listing.is_archived)
        self.assertEqual(listing.status, 'closed')

    def test_property_create_ignores_client_company_and_uses_active_company(self):
        response = self.client.post('/api/real-estate/properties/', {
            'company': self.other.pk,
            'title': 'Owned flat',
            'property_type': 'apartment',
        }, format='json')
        self.assertEqual(response.status_code, 201, response.json())
        self.assertEqual(Property.objects.get(pk=response.json()['id']).company, self.company)

    def test_property_type_master_supports_custom_types_and_safe_deactivation(self):
        response = self.client.post('/api/real-estate/property-types/', {
            'name': 'Hotel Apartment', 'code': 'hotel_apartment',
            'category': 'residential', 'sort_order': 25,
        }, format='json')
        self.assertEqual(response.status_code, 201, response.json())
        type_id = response.json()['id']
        self.assertEqual(PropertyType.objects.get(pk=type_id).company, self.company)

        response = self.client.post('/api/real-estate/properties/', {
            'title': 'Serviced unit', 'property_type': 'hotel_apartment', 'area_unit': 'acre',
        }, format='json')
        self.assertEqual(response.status_code, 201, response.json())
        self.assertEqual(response.json()['property_type_name'], 'Hotel Apartment')
        self.assertEqual(response.json()['area_unit'], 'acre')

        self.assertEqual(self.client.delete(f'/api/real-estate/property-types/{type_id}/').status_code, 204)
        response = self.client.post('/api/real-estate/properties/', {
            'title': 'Another serviced unit', 'property_type': 'hotel_apartment',
        }, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertTrue(PropertyType.objects.get(pk=type_id).is_active is False)

    def test_candidate_promotion_is_explicit(self):
        opportunity = RealEstateOpportunity.objects.create(
            company=self.company,
            activity_type=ActivityType.SELLING,
            classification_status=ClassificationStatus.CLASSIFIED,
            first_seen_at=timezone.now(),
        )
        candidate = PropertyCandidate.objects.create(
            company=self.company,
            opportunity=opportunity,
            title='Seller villa',
            property_type=self.types['villa'],
            asking_price=3000000,
        )
        self.assertFalse(Property.objects.filter(company=self.company).exists())
        response = self.client.post(
            f'/api/real-estate/candidates/{candidate.pk}/promote/', {}, format='json',
        )
        self.assertEqual(response.status_code, 201, response.json())
        candidate.refresh_from_db()
        self.assertEqual(candidate.review_status, 'promoted')
        self.assertTrue(Property.objects.filter(pk=response.json()['property_id']).exists())

    def test_non_real_estate_company_is_blocked(self):
        self.company.industry_type = Company.INDUSTRY_GENERAL
        self.company.save(update_fields=['industry_type'])
        response = self.client.get('/api/real-estate/properties/')
        self.assertEqual(response.status_code, 403)

    def test_agent_sees_only_assigned_opportunities(self):
        agent = get_user_model().objects.create_user('estate-agent')
        CompanyMembership.objects.create(
            company=self.company, user=agent, role=CompanyMembership.ROLE_USER,
        )
        assigned = RealEstateOpportunity.objects.create(
            company=self.company, assigned_to=agent, activity_type=ActivityType.BUYING,
            classification_status=ClassificationStatus.CLASSIFIED, first_seen_at=timezone.now(),
        )
        RealEstateOpportunity.objects.create(
            company=self.company, assigned_to=self.user, activity_type=ActivityType.SELLING,
            classification_status=ClassificationStatus.CLASSIFIED, first_seen_at=timezone.now(),
        )
        self.client.force_authenticate(agent)
        response = self.client.get('/api/real-estate/opportunities/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row['id'] for row in response.json()['results']], [assigned.pk])

    def test_csv_preview_then_import_is_explicit(self):
        csv_file = SimpleUploadedFile(
            'properties.csv',
            b'reference_code,title,property_type,city,listing_type,asking_price,is_verified\n'
            b'SV-001,Marina Flat,apartment,Dubai,sale,2200000,true\n',
            content_type='text/csv',
        )
        response = self.client.post(
            '/api/real-estate/properties/import-preview/', {'file': csv_file}, format='multipart',
        )
        self.assertEqual(response.status_code, 200, response.json())
        self.assertFalse(Property.objects.filter(company=self.company).exists())
        row = response.json()['rows'][0]
        self.assertTrue(row['valid'])

        response = self.client.post(
            '/api/real-estate/properties/bulk-import/', {'rows': [row]}, format='json',
        )
        self.assertEqual(response.status_code, 201, response.json())
        record = Property.objects.get(company=self.company, reference_code='SV-001')
        self.assertEqual(record.address.city, 'Dubai')
        self.assertEqual(record.listings.get().asking_price, 2200000)

    def test_csv_import_skips_exact_duplicate_and_export_is_company_scoped(self):
        existing = Property.objects.create(
            company=self.company, reference_code='SV-002', title='Existing Villa', property_type=self.types['villa'],
        )
        Property.objects.create(company=self.other, reference_code='HIDDEN', title='Hidden', property_type=self.other_types['villa'])
        response = self.client.post('/api/real-estate/properties/bulk-import/', {
            'rows': [{'row_number': 2, 'reference_code': 'SV-002', 'title': 'Existing Villa', 'property_type': 'villa'}],
        }, format='json')
        self.assertEqual(response.status_code, 201, response.json())
        self.assertEqual(response.json()['skipped_rows'], [2])
        self.assertEqual(Property.objects.filter(company=self.company, reference_code='SV-002').count(), 1)

        response = self.client.get('/api/real-estate/properties/export/')
        self.assertEqual(response.status_code, 200)
        body = b''.join(response.streaming_content).decode()
        self.assertIn(existing.title, body)
        self.assertNotIn('Hidden', body)

    def test_csv_preview_rejects_duplicates_within_the_upload(self):
        upload = SimpleUploadedFile(
            'properties.csv',
            b'reference_code,title,property_type\n'
            b'REF-DUP,Marina View,apartment\n'
            b'REF-DUP,Another Title,villa\n',
            content_type='text/csv',
        )

        response = self.client.post(
            '/api/real-estate/properties/import-preview/', {'file': upload}, format='multipart',
        )

        self.assertEqual(response.status_code, 200, response.json())
        self.assertTrue(response.json()['rows'][0]['valid'])
        self.assertFalse(response.json()['rows'][1]['valid'])
        self.assertIn('duplicate', response.json()['rows'][1]['errors'])
