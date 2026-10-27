from django.contrib.auth.models import User
from django.test import TestCase

from apps.tenancy.models import CommunicationAccount, Company, CompanyMembership, ConnectionProvider
from apps.trading.models import Inquiry, InquiryStatus, Product
from apps.whatsapp_bridge.models import WhatsAppAccount, WhatsAppContact


class ManualInquiryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='manual-creator')
        self.company = Company.objects.create(name='Manual Co', slug='manual-co')
        CompanyMembership.objects.create(
            company=self.company, user=self.user, role=CompanyMembership.ROLE_ADMIN,
        )
        provider = ConnectionProvider.objects.create(
            key='manual-wa', name='WhatsApp', channel=ConnectionProvider.CHANNEL_WHATSAPP,
        )
        communication = CommunicationAccount.objects.create(
            company=self.company, provider=provider,
            channel=ConnectionProvider.CHANNEL_WHATSAPP, name='Sales',
        )
        self.account = WhatsAppAccount.objects.create(owner=self.user, communication_account=communication)
        self.contact = WhatsAppContact.objects.create(
            account=self.account, wa_contact_id='971500000009@s.whatsapp.net',
            phone_number='971500000009', display_name='Manual Buyer',
        )
        self.product = Product.objects.create(
            company=self.company, name='Phone X', sale_price=900, currency='AED',
        )
        self.client.force_login(self.user)

    def test_manual_inquiry_with_matched_product(self):
        response = self.client.post(
            '/api/inquiries/manual/',
            {
                'account_id': self.account.pk,
                'contact_id': self.contact.pk,
                'inquiry_type': 'buy',
                'summary': 'Wants 5 units of Phone X',
                'items': [{'product_id': self.product.pk, 'quantity': 5}],
            },
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 201, response.content)
        data = response.json()
        self.assertEqual(data['inquiry_type'], 'buy')
        self.assertEqual(data['status'], InquiryStatus.OPEN)
        self.assertEqual(data['source_type'], 'direct')
        self.assertEqual(data['contact_phone'], '971500000009')
        self.assertEqual(len(data['products']), 1)
        line = data['products'][0]
        self.assertEqual(line['product_id'], self.product.pk)
        self.assertEqual(line['canonical_name'], 'Phone X')
        self.assertEqual(line['quantity'], 5.0)
        self.assertEqual(line['price'], 900.0)
        self.assertEqual(line['match_type'], 'manual')

        inquiry = Inquiry.objects.get(pk=data['id'])
        self.assertEqual(inquiry.company, self.company)
        self.assertFalse(inquiry.inquiry_messages.exists())

    def test_manual_inquiry_with_free_text_product(self):
        response = self.client.post(
            '/api/inquiries/manual/',
            {
                'account_id': self.account.pk,
                'inquiry_type': 'sell',
                'summary': 'Selling spare cables',
                'items': [{'canonical_name': 'USB-C cables', 'quantity': 20, 'currency': 'AED'}],
            },
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 201, response.content)
        line = response.json()['products'][0]
        self.assertIsNone(line['product_id'])
        self.assertEqual(line['canonical_name'], 'USB-C cables')

    def test_manual_inquiry_rejects_contact_from_other_account(self):
        other_communication = CommunicationAccount.objects.create(
            company=self.company, provider=self.account.communication_account.provider,
            channel=ConnectionProvider.CHANNEL_WHATSAPP, name='Other',
        )
        other_account = WhatsAppAccount.objects.create(owner=self.user, communication_account=other_communication)
        other_contact = WhatsAppContact.objects.create(
            account=other_account, wa_contact_id='971500000010@s.whatsapp.net', phone_number='971500000010',
        )

        response = self.client.post(
            '/api/inquiries/manual/',
            {
                'account_id': self.account.pk,
                'contact_id': other_contact.pk,
                'inquiry_type': 'buy',
                'summary': 'Mismatched contact',
                'items': [{'canonical_name': 'Phone X', 'quantity': 1}],
            },
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn('contact_id', response.json())

    def test_manual_inquiry_rejects_product_from_other_company(self):
        other_company = Company.objects.create(name='Other Co', slug='manual-other-co')
        foreign_product = Product.objects.create(company=other_company, name='Foreign Widget')

        response = self.client.post(
            '/api/inquiries/manual/',
            {
                'account_id': self.account.pk,
                'inquiry_type': 'buy',
                'summary': 'Cross-company product',
                'items': [{'product_id': foreign_product.pk, 'quantity': 1}],
            },
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn('items', response.json())

    def test_manual_inquiry_requires_at_least_one_item(self):
        response = self.client.post(
            '/api/inquiries/manual/',
            {
                'account_id': self.account.pk,
                'inquiry_type': 'buy',
                'summary': 'No items',
                'items': [],
            },
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn('items', response.json())
