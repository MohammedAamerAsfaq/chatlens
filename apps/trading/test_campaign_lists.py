from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from apps.tenancy.models import CommunicationAccount, CommunicationAccountAssignment, Company, ConnectionProvider
from apps.tenancy.testing import create_member
from apps.trading.models import (
    BuyingInquiry,
    CampaignList,
    CampaignListContact,
    CampaignListGroup,
    CampaignListProduct,
    Product,
    ProductAlias,
    SellingOffer,
    SellingOfferCustomer,
)
from apps.whatsapp_bridge.models import WhatsAppAccount, WhatsAppContact, WhatsAppGroup


class ListFixtures:
    def setUp(self):
        self.company = Company.objects.create(name='Lists Co', slug='lists-co')
        self.manager = User.objects.create_user('list-manager', password='pw')
        self.viewer = User.objects.create_user('list-viewer', password='pw')
        manager_membership = create_member(company=self.company, user=self.manager, role='campaign_operator')
        viewer_membership = create_member(company=self.company, user=self.viewer, role='viewer')
        provider = ConnectionProvider.objects.create(key='lists-wa', name='WA', channel=ConnectionProvider.CHANNEL_WHATSAPP)
        comm = CommunicationAccount.objects.create(
            channel=ConnectionProvider.CHANNEL_WHATSAPP, company=self.company, provider=provider, name='Sales',
        )
        for membership in (manager_membership, viewer_membership):
            CommunicationAccountAssignment.objects.create(company=self.company, communication_account=comm, membership=membership)
        self.account = WhatsAppAccount.objects.create(
            owner=self.manager, communication_account=comm, display_name='Sales', phone_number='971500000000',
        )
        self.ali = self._contact('971511111111', 'Ali')
        self.bob = self._contact('971522222222', 'Bob')
        self.lid = WhatsAppContact.objects.create(account=self.account, wa_contact_id='123456789@lid', display_name='Linked')
        self.dealers = self._group('dealers@g.us', 'Dealers')
        self.announce = self._group('news@g.us', 'News', announce=True)
        self.client = APIClient()
        self.client.force_authenticate(self.manager)

    def _contact(self, phone, name):
        return WhatsAppContact.objects.create(
            account=self.account, wa_contact_id=f'{phone}@s.whatsapp.net', phone_number=phone, display_name=name,
        )

    def _group(self, jid, name, **fields):
        return WhatsAppGroup.objects.create(
            account=self.account, wa_group_id=jid, name=name, can_send=True, account_is_participant=True, **fields,
        )

    def _list(self, kind='contacts', name='VIP buyers'):
        return CampaignList.objects.create(company=self.company, kind=kind, name=name, created_by=self.manager)


class CampaignListTests(ListFixtures, TestCase):
    def test_searching_contacts_to_add_does_not_filter_by_list_name(self):
        contacts = self._list()
        response = self.client.get(f'/api/campaign-lists/{contacts.pk}/candidates/', {'search': 'bob'})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual([row['name'] for row in response.data['results']], ['Bob'])

    def test_manager_creates_a_customer_list_and_adds_contacts(self):
        response = self.client.post('/api/campaign-lists/', {'kind': 'contacts', 'name': ' VIP buyers '}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['name'], 'VIP buyers')
        list_id = response.data['id']

        response = self.client.post(f'/api/campaign-lists/{list_id}/add-members/', {'ids': [self.ali.pk, self.bob.pk]}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['added'], 2)
        self.assertEqual(response.data['list']['member_count'], 2)
        self.assertEqual([row['name'] for row in response.data['list']['members']], ['Ali', 'Bob'])

        response = self.client.get('/api/campaign-lists/', {'kind': 'contacts'})
        self.assertEqual([(row['name'], row['member_count']) for row in response.data], [('VIP buyers', 2)])

    def test_list_names_are_unique_per_company_and_kind_ignoring_case(self):
        self._list(name='VIP buyers')
        response = self.client.post('/api/campaign-lists/', {'kind': 'contacts', 'name': 'vip BUYERS'}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('name', response.data)
        response = self.client.post('/api/campaign-lists/', {'kind': 'groups', 'name': 'VIP buyers'}, format='json')
        self.assertEqual(response.status_code, 201)

    def test_linked_ids_and_unsendable_groups_cannot_join_a_list(self):
        contacts = self._list()
        response = self.client.post(f'/api/campaign-lists/{contacts.pk}/add-members/', {'ids': [self.ali.pk, self.lid.pk]}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(contacts.contacts.exists())

        groups = self._list(kind='groups', name='Dealers')
        response = self.client.post(f'/api/campaign-lists/{groups.pk}/add-members/', {'ids': [self.announce.pk]}, format='json')
        self.assertEqual(response.status_code, 400)

        candidates = self.client.get(f'/api/campaign-lists/{groups.pk}/candidates/')
        self.assertEqual([row['name'] for row in candidates.data['results']], ['Dealers'])

    def test_add_all_matching_adds_every_eligible_search_result(self):
        contacts = self._list()
        CampaignListContact.objects.create(campaign_list=contacts, contact=self.ali)
        response = self.client.post(f'/api/campaign-lists/{contacts.pk}/add-members/', {'all_matching': True, 'search': ''}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual((response.data['added'], response.data['skipped']), (1, 1))
        self.assertEqual(set(contacts.contacts.values_list('contact_id', flat=True)), {self.ali.pk, self.bob.pk})

    def test_viewer_can_see_lists_but_not_change_them(self):
        contacts = self._list()
        self.client.force_authenticate(self.viewer)
        self.assertEqual(self.client.get('/api/campaign-lists/').status_code, 200)
        self.assertEqual(self.client.get(f'/api/campaign-lists/{contacts.pk}/').status_code, 200)
        self.assertEqual(self.client.post('/api/campaign-lists/', {'kind': 'contacts', 'name': 'X'}, format='json').status_code, 403)
        self.assertEqual(self.client.post(f'/api/campaign-lists/{contacts.pk}/add-members/', {'ids': [self.ali.pk]}, format='json').status_code, 403)
        self.assertEqual(self.client.delete(f'/api/campaign-lists/{contacts.pk}/').status_code, 403)

    def test_applying_a_customer_list_adds_its_members_to_a_selling_offer(self):
        contacts = self._list()
        CampaignListContact.objects.create(campaign_list=contacts, contact=self.ali)
        CampaignListContact.objects.create(campaign_list=contacts, contact=self.bob)
        offer = SellingOffer.objects.create(company=self.company, name='Stock', created_by=self.manager)
        SellingOfferCustomer.objects.create(offer=offer, contact=self.ali)

        response = self.client.post(f'/api/selling-offers/{offer.pk}/add-list/', {'list_id': contacts.pk}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual((response.data['added'], response.data['skipped'], response.data['unavailable']), (1, 1, 0))
        self.assertEqual(set(offer.customers.values_list('contact_id', flat=True)), {self.ali.pk, self.bob.pk})
        self.assertEqual(offer.customers.get(contact=self.bob).source, 'manual')

    def test_applying_a_group_list_skips_groups_that_are_no_longer_sendable(self):
        groups = self._list(kind='groups', name='Dealers')
        CampaignListGroup.objects.create(campaign_list=groups, group=self.dealers)
        stale = self._group('old@g.us', 'Old')
        CampaignListGroup.objects.create(campaign_list=groups, group=stale)
        stale.account_is_participant = False
        stale.save(update_fields=['account_is_participant'])
        inquiry = BuyingInquiry.objects.create(company=self.company, name='Need stock', audience_type='groups', created_by=self.manager)

        response = self.client.post(f'/api/buying-inquiries/{inquiry.pk}/add-list/', {'list_id': groups.pk}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual((response.data['added'], response.data['unavailable']), (1, 1))
        self.assertEqual(list(inquiry.groups.values_list('group_id', flat=True)), [self.dealers.pk])

        detail = self.client.get(f'/api/campaign-lists/{groups.pk}/')
        self.assertEqual({row['name']: row['usable'] for row in detail.data['members']}, {'Dealers': True, 'Old': False})

    def test_a_list_must_match_the_campaign_audience(self):
        groups = self._list(kind='groups', name='Dealers')
        offer = SellingOffer.objects.create(company=self.company, name='Stock', created_by=self.manager)
        response = self.client.post(f'/api/selling-offers/{offer.pk}/add-list/', {'list_id': groups.pk}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('contact list', str(response.data['list_id']))

    def test_viewer_cannot_apply_a_list_to_a_campaign(self):
        contacts = self._list()
        offer = SellingOffer.objects.create(company=self.company, name='Stock', created_by=self.manager)
        self.client.force_authenticate(self.viewer)
        response = self.client.post(f'/api/selling-offers/{offer.pk}/add-list/', {'list_id': contacts.pk}, format='json')
        self.assertEqual(response.status_code, 403)

    def test_another_companys_list_cannot_be_used(self):
        other = Company.objects.create(name='Other', slug='other-co')
        foreign = CampaignList.objects.create(company=other, kind='contacts', name='Theirs')
        offer = SellingOffer.objects.create(company=self.company, name='Stock', created_by=self.manager)
        response = self.client.post(f'/api/selling-offers/{offer.pk}/add-list/', {'list_id': foreign.pk}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.client.get(f'/api/campaign-lists/{foreign.pk}/').status_code, 404)

    def test_removing_members(self):
        contacts = self._list()
        row = CampaignListContact.objects.create(campaign_list=contacts, contact=self.ali)
        response = self.client.post(f'/api/campaign-lists/{contacts.pk}/remove-members/', {'ids': [row.pk]}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['removed'], 1)
        self.assertEqual(response.data['list']['member_count'], 0)


class CampaignProductListTests(ListFixtures, TestCase):
    """Product lists stand alone: any campaign, contact or group, can take one."""

    def setUp(self):
        super().setUp()
        self.screen = self._product('Samsung A15 Incell LCD', '26.50', qty=4)
        self.battery = self._product('Samsung A15 Battery', '12.00')
        ProductAlias.objects.create(product=self.battery, alias='A15 BATT')
        self.old = self._product('Samsung J2 LCD', '9.00', is_active=False)

    def _product(self, name, price, qty=0, is_active=True):
        return Product.objects.create(
            company=self.company, name=name, brand='samsung', category='LCD', qty=qty,
            cost_price=price, sale_price=price, currency='AED', is_active=is_active,
        )

    def _product_list(self, *products):
        product_list = self._list(kind='products', name='A15 parts')
        for product in products:
            CampaignListProduct.objects.create(campaign_list=product_list, product=product)
        return product_list

    def test_manager_builds_a_product_list_from_active_products(self):
        response = self.client.post('/api/campaign-lists/', {'kind': 'products', 'name': 'A15 parts'}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        list_id = response.data['id']

        candidates = self.client.get(f'/api/campaign-lists/{list_id}/candidates/', {'search': 'batt'})
        self.assertEqual(candidates.status_code, 200, candidates.data)
        self.assertEqual([row['name'] for row in candidates.data['results']], ['A15 Battery'])
        combined = self.client.get(f'/api/campaign-lists/{list_id}/candidates/', {'search': 'samsung a15 inc'})
        self.assertEqual([row['name'] for row in combined.data['results']], ['A15 Incell LCD'])
        everything = self.client.get(f'/api/campaign-lists/{list_id}/candidates/')
        self.assertNotIn('J2 LCD', [row['name'] for row in everything.data['results']])

        response = self.client.post(f'/api/campaign-lists/{list_id}/add-members/', {'ids': [self.screen.pk, self.battery.pk]}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['list']['member_count'], 2)
        self.assertEqual(response.data['list']['members'][0]['detail'], '26.50 AED · Qty 4')

        response = self.client.post(f'/api/campaign-lists/{list_id}/add-members/', {'ids': [self.old.pk]}, format='json')
        self.assertEqual(response.status_code, 400)

    def test_product_list_fills_a_contact_campaign_with_catalogue_prices(self):
        product_list = self._product_list(self.screen, self.battery)
        offer = SellingOffer.objects.create(company=self.company, name='Stock', created_by=self.manager)
        response = self.client.post(f'/api/selling-offers/{offer.pk}/add-product-list/', {'list_id': product_list.pk}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual((response.data['added'], response.data['skipped'], response.data['unavailable']), (2, 0, 0))
        row = offer.products.get(product=self.screen)
        self.assertEqual((row.quantity, str(row.price), row.currency), (4, '26.50', 'AED'))

        again = self.client.post(f'/api/selling-offers/{offer.pk}/add-product-list/', {'list_id': product_list.pk}, format='json')
        self.assertEqual((again.data['added'], again.data['skipped']), (0, 2))

    def test_replacing_with_a_product_list_leaves_exactly_the_list(self):
        offer = SellingOffer.objects.create(company=self.company, name='Stock', created_by=self.manager)
        self.client.post(f'/api/selling-offers/{offer.pk}/add-product/', {'product_id': self.battery.pk}, format='json')
        self.client.post(f'/api/selling-offers/{offer.pk}/add-product/', {'product_id': self.screen.pk}, format='json')
        product_list = self._product_list(self.screen)
        response = self.client.post(
            f'/api/selling-offers/{offer.pk}/add-product-list/', {'list_id': product_list.pk, 'replace': True}, format='json',
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual((response.data['removed'], response.data['added'], response.data['skipped']), (2, 1, 0))
        self.assertEqual(list(offer.products.values_list('product_id', flat=True)), [self.screen.pk])
        self.assertEqual(len(response.data['offer']['products']), 1)

    def test_replace_must_be_a_boolean_and_a_refused_replace_keeps_products(self):
        offer = SellingOffer.objects.create(company=self.company, name='Stock', created_by=self.manager)
        self.client.post(f'/api/selling-offers/{offer.pk}/add-product/', {'product_id': self.battery.pk}, format='json')
        product_list = self._product_list(self.screen)
        response = self.client.post(
            f'/api/selling-offers/{offer.pk}/add-product-list/', {'list_id': product_list.pk, 'replace': 'yes'}, format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('replace', response.data)
        response = self.client.post(
            f'/api/selling-offers/{offer.pk}/add-product-list/', {'list_id': self._list().pk, 'replace': True}, format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(offer.products.count(), 1)

    def test_remove_all_products_clears_a_campaign(self):
        inquiry = BuyingInquiry.objects.create(company=self.company, name='Need', audience_type='groups', created_by=self.manager)
        self.client.post(f'/api/buying-inquiries/{inquiry.pk}/add-product-list/', {'list_id': self._product_list(self.screen, self.battery).pk}, format='json')
        response = self.client.post(f'/api/buying-inquiries/{inquiry.pk}/remove-all-products/', format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['removed'], 2)
        self.assertEqual(response.data['inquiry']['products'], [])
        self.client.force_authenticate(self.viewer)
        self.assertEqual(self.client.post(f'/api/buying-inquiries/{inquiry.pk}/remove-all-products/').status_code, 403)

    def test_product_list_fills_a_group_campaign_and_skips_inactive_products(self):
        product_list = self._product_list(self.screen, self.old)
        inquiry = BuyingInquiry.objects.create(company=self.company, name='Need', audience_type='groups', created_by=self.manager)
        response = self.client.post(f'/api/buying-inquiries/{inquiry.pk}/add-product-list/', {'list_id': product_list.pk}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual((response.data['added'], response.data['unavailable']), (1, 1))
        self.assertEqual(list(inquiry.products.values_list('product_id', flat=True)), [self.screen.pk])

    def test_product_list_works_on_a_direct_message_campaign(self):
        product_list = self._product_list(self.screen)
        offer = SellingOffer.objects.create(company=self.company, name='Hello', message_mode='direct', direct_message='Hi', created_by=self.manager)
        response = self.client.post(f'/api/selling-offers/{offer.pk}/add-product-list/', {'list_id': product_list.pk}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(offer.products.count(), 1)

    def test_recipient_and_product_lists_are_not_interchangeable(self):
        product_list = self._product_list(self.screen)
        contacts = self._list()
        offer = SellingOffer.objects.create(company=self.company, name='Stock', created_by=self.manager)
        self.assertEqual(self.client.post(f'/api/selling-offers/{offer.pk}/add-list/', {'list_id': product_list.pk}, format='json').status_code, 400)
        self.assertEqual(self.client.post(f'/api/selling-offers/{offer.pk}/add-product-list/', {'list_id': contacts.pk}, format='json').status_code, 400)

    def test_viewer_cannot_add_a_product_list_to_a_campaign(self):
        product_list = self._product_list(self.screen)
        offer = SellingOffer.objects.create(company=self.company, name='Stock', created_by=self.manager)
        self.client.force_authenticate(self.viewer)
        response = self.client.post(f'/api/selling-offers/{offer.pk}/add-product-list/', {'list_id': product_list.pk}, format='json')
        self.assertEqual(response.status_code, 403)
