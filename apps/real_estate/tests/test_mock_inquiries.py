from uuid import uuid4

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.real_estate.models import (
    ActivityType, RealEstateMockInquiry, RealEstateMockInquiryRun,
    RealEstateMockSourceRecord,
)
from apps.real_estate.services.mock_inquiry_generation import generate_mock_inquiries
from apps.real_estate.services.mock_inquiry_cleanup import clear_mock_inquiries
from apps.real_estate.services.mock_inquiry_profiles import PROFILES, parse_source_record
from apps.task_management.models import BackgroundTask
from apps.tenancy.models import Company, CompanyMembership


class RealEstateMockInquiryTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            name='Mock Estate', slug='mock-estate', industry_type='real_estate',
        )
        self.other_company = Company.objects.create(
            name='Other Estate', slug='other-mock-estate', industry_type='real_estate',
        )
        self.user = get_user_model().objects.create_user('mock-estate-owner')
        CompanyMembership.objects.create(
            company=self.company, user=self.user,
            role=CompanyMembership.ROLE_SUPER_USER,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def source_record(self, company=None, **overrides):
        values = [
            'Demo Buyer', '', '0501234567', '', '2,000,000', '2BR',
            'Binghatti Hills',
        ]
        fields = {
            'company': company or self.company,
            'import_run_id': uuid4(),
            'source_file_name': 'Binghatti Leads-1.xlsx',
            'source_file_checksum': uuid4().hex,
            'source_sheet_name': 'Leads',
            'source_sheet_index': 0,
            'source_row_number': 2,
            'row_kind': 'data',
            'raw_values': values,
            'display_values': values,
            'row_checksum': uuid4().hex,
        }
        fields.update(overrides)
        return RealEstateMockSourceRecord.objects.create(**fields)

    def test_buying_profile_extracts_contact_and_property_context(self):
        record = self.source_record()

        data = parse_source_record(record, PROFILES[record.source_file_name])

        self.assertEqual(data['name'], 'Demo Buyer')
        self.assertEqual(data['phone'], '971501234567')
        self.assertEqual(data['project'], 'Binghatti Hills')
        self.assertEqual(data['budget'], '2,000,000')

    def test_dataset_endpoint_is_company_scoped(self):
        self.source_record()
        self.source_record(company=self.other_company, source_row_number=3)

        response = self.client.get('/api/real-estate/mock-inquiries/datasets/')

        self.assertEqual(response.status_code, 200, response.json())
        dataset = next(
            row for row in response.json()['datasets']
            if row['source_file_name'] == 'Binghatti Leads-1.xlsx'
        )
        self.assertEqual(dataset['total_records'], 1)
        self.assertEqual(dataset['eligible_pending'], 1)

    def test_start_run_enqueues_durable_generation_task(self):
        self.source_record()

        response = self.client.post('/api/real-estate/mock-inquiries/start-run/', {
            'source_file_name': 'Binghatti Leads-1.xlsx',
            'record_count': 1,
        }, format='json')

        self.assertEqual(response.status_code, 202, response.json())
        task = BackgroundTask.objects.get(pk=response.json()['task_id'])
        self.assertEqual(task.task_key, 'real_estate.generate_mock_inquiries')
        self.assertEqual(task.queue_name, 'real_estate_imports')
        self.assertEqual(task.company, self.company)

    def test_generator_queues_normal_live_ingestion_and_disables_outbound(self):
        source = self.source_record()
        run = RealEstateMockInquiryRun.objects.create(
            company=self.company, source_file_name=source.source_file_name,
            activity_type=ActivityType.BUYING, requested_count=1,
            created_by=self.user,
        )

        result = generate_mock_inquiries(run.pk)

        run.refresh_from_db()
        source.refresh_from_db()
        inquiry = RealEstateMockInquiry.objects.get(run=run)
        self.assertEqual(result['generated'], 1)
        self.assertEqual(run.status, RealEstateMockInquiryRun.STATUS_COMPLETE)
        self.assertEqual(source.processing_status, 'processed')
        self.assertEqual(inquiry.live_task.task_key, 'whatsapp.persist_live_message')
        self.assertEqual(inquiry.live_task.queue_name, 'live_ingestion')
        self.assertEqual(inquiry.live_task.company, self.company)
        self.assertTrue(inquiry.generated_message.startswith('I am looking to buy'))
        self.assertFalse(run.mock_account.outbound_sending_enabled)
        self.assertFalse(run.mock_account.direct_sending_enabled)
        self.assertFalse(run.mock_account.group_sending_enabled)

    def test_start_run_rejects_dataset_without_pending_rows(self):
        response = self.client.post('/api/real-estate/mock-inquiries/start-run/', {
            'source_file_name': 'Binghatti Leads-1.xlsx',
            'record_count': 1,
        }, format='json')

        self.assertEqual(response.status_code, 400)
        self.assertIn('source_file_name', response.json())

    def test_clear_resets_sources_and_retains_cleared_audit(self):
        source = self.source_record()
        run = RealEstateMockInquiryRun.objects.create(
            company=self.company, source_file_name=source.source_file_name,
            activity_type=ActivityType.BUYING, requested_count=1,
            created_by=self.user,
        )
        generate_mock_inquiries(run.pk)
        inquiry = RealEstateMockInquiry.objects.get(run=run)
        inquiry.live_task.status = BackgroundTask.STATUS_SUCCEEDED
        inquiry.live_task.save(update_fields=['status'])

        result = clear_mock_inquiries(self.company)

        source.refresh_from_db()
        self.assertEqual(result['source_rows_reset'], 1)
        self.assertEqual(source.processing_status, 'pending')
        self.assertFalse(RealEstateMockInquiryRun.objects.filter(pk=run.pk).exists())
        self.assertFalse(RealEstateMockInquiry.objects.filter(pk=inquiry.pk).exists())
