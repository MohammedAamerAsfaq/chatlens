from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from apps.tenancy.models import CommunicationAccount, Company, ConnectionProvider
from apps.trading.models import (
    BuyingInquiry,
    BuyingInquirySupplier,
    SellingOffer,
    SellingOfferCustomer,
)
from apps.whatsapp_bridge.models import WhatsAppAccount, WhatsAppContact
from apps.whatsapp_bridge.outbound.policy import new_chat_snapshot


class DirectCampaignChatLensTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser('campaign-admin', 'admin@example.com', 'pw')
        self.company = Company.objects.create(
            name='Campaign Test',
            slug='campaign-test',
            company_type=Company.TYPE_CONTROL,
        )
        provider = ConnectionProvider.objects.create(
            key='campaign-whatsapp',
            name='Campaign WhatsApp',
            channel=ConnectionProvider.CHANNEL_WHATSAPP,
        )
        communication_account = CommunicationAccount.objects.create(
            channel=ConnectionProvider.CHANNEL_WHATSAPP,
            company=self.company,
            provider=provider,
            name='Campaign Account',
        )
        self.account = WhatsAppAccount.objects.create(
            owner=self.user,
            communication_account=communication_account,
            display_name='Campaign Account',
            phone_number='971500000000',
        )
        self.contact = WhatsAppContact.objects.create(
            account=self.account,
            wa_contact_id='971511111111@s.whatsapp.net',
            phone_number='971511111111',
            display_name='Campaign Contact',
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_buying_supplier_exposes_destination_and_counts_chatlens_click(self):
        inquiry = BuyingInquiry.objects.create(company=self.company, name='Buy stock', created_by=self.user)
        supplier = BuyingInquirySupplier.objects.create(inquiry=inquiry, contact=self.contact)

        response = self.client.post(
            f'/api/buying-inquiries/{inquiry.pk}/mark-supplier-chatlens-click/',
            {'supplier_id': supplier.pk},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['account_id'], self.account.pk)
        self.assertEqual(response.data['destination_jid'], self.contact.wa_contact_id)
        self.assertEqual(response.data['chatlens_click_count'], 1)

    def test_selling_customer_exposes_destination_and_counts_chatlens_click(self):
        offer = SellingOffer.objects.create(company=self.company, name='Sell stock', created_by=self.user)
        customer = SellingOfferCustomer.objects.create(offer=offer, contact=self.contact)

        response = self.client.post(
            f'/api/selling-offers/{offer.pk}/mark-customer-chatlens-click/',
            {'customer_id': customer.pk},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['account_id'], self.account.pk)
        self.assertEqual(response.data['destination_jid'], self.contact.wa_contact_id)
        self.assertEqual(response.data['chatlens_click_count'], 1)

    def test_contact_chat_state_persists_and_controls_future_campaign_rows(self):
        self.assertTrue(self.contact.is_existing_chat)
        response = self.client.patch(
            f'/api/contacts/{self.contact.pk}/',
            {'is_existing_chat': False},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.contact.refresh_from_db()
        self.assertFalse(self.contact.is_existing_chat)
        self.assertEqual(
            new_chat_snapshot(self.account, self.contact.wa_contact_id)['reason'],
            'operator_marked_new',
        )

        inquiry = BuyingInquiry.objects.create(company=self.company, name='Future inquiry')
        supplier = BuyingInquirySupplier.objects.create(inquiry=inquiry, contact=self.contact)
        response = self.client.post(
            f'/api/buying-inquiries/{inquiry.pk}/mark-supplier-chatlens-click/',
            {'supplier_id': supplier.pk},
            format='json',
        )
        self.assertFalse(response.data['is_existing_chat'])

        response = self.client.patch(
            f'/api/contacts/{self.contact.pk}/',
            {'is_existing_chat': True},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            new_chat_snapshot(self.account, self.contact.wa_contact_id)['reason'],
            'operator_marked_existing',
        )
