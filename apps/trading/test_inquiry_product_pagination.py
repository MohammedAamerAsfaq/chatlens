from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.tenancy.models import CommunicationAccount, Company, ConnectionProvider
from apps.trading.models import Inquiry, InquiryProduct
from apps.whatsapp_bridge.models import WhatsAppAccount


class InquiryProductPaginationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser('pager', 'pager@example.com', 'pw')
        company = Company.objects.create(name='Pager Co', slug='pager-co')
        provider = ConnectionProvider.objects.create(
            key='pager-whatsapp', name='Pager WhatsApp', channel='whatsapp',
        )
        communication_account = CommunicationAccount.objects.create(
            channel='whatsapp', company=company, provider=provider, name='Pager Desk',
        )
        account = WhatsAppAccount.objects.create(
            owner=self.user, communication_account=communication_account, display_name='Pager Desk',
        )
        inquiry = Inquiry.objects.create(
            company=company,
            account=account,
            inquiry_type='buy',
            products=[],
            summary='Pagination test',
            dedup_key='pagination-test',
            source_type='direct',
            first_seen_at=timezone.now(),
        )
        InquiryProduct.objects.bulk_create([
            InquiryProduct(
                company=company,
                inquiry=inquiry,
                account=account,
                inquiry_type='buy',
                canonical_name=f'Product {index:02d}',
                normalized_name=f'product {index:02d}',
                first_seen_at=timezone.now(),
            )
            for index in range(30)
        ])
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_pages_return_distinct_slices_and_global_summary(self):
        first = self.client.get('/api/inquiry-products/', {'page': 1, 'page_size': 10})
        second = self.client.get('/api/inquiry-products/', {'page': 2, 'page_size': 10})

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.data['count'], 30)
        self.assertEqual(len(first.data['results']), 10)
        self.assertEqual(len(second.data['results']), 10)
        self.assertTrue(
            {row['id'] for row in first.data['results']}.isdisjoint(
                row['id'] for row in second.data['results']
            )
        )
        self.assertEqual(first.data['summary'], {
            'mapped': 0,
            'pending': 30,
            'unmatched': 30,
        })
