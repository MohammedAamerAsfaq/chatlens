from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils.timezone import now
from rest_framework.test import APIClient

from apps.tenancy.models import (
    CommunicationAccount, CommunicationAccountAssignment, Company, CompanyMembership, ConnectionProvider,
)
from apps.trading.models import (
    Inquiry, InquiryShare, InquiryStatus, SharedInquiryAction, SharedInquiryActionEvent,
)
from apps.whatsapp_bridge.models import WhatsAppAccount, WhatsAppChat, WhatsAppContact
from apps.tenancy.testing import create_member


class InquirySharingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model().objects
        cls.owner = users.create_user(username='owner', password='pw')
        cls.bob = users.create_user(username='bob', password='pw')
        cls.carol = users.create_user(username='carol', password='pw')
        cls.outsider = users.create_user(username='outsider', password='pw')

        cls.company = Company.objects.create(name='Share Co', slug='share-co', industry_type=Company.INDUSTRY_TRADING)
        other = Company.objects.create(name='Other Co', slug='other-co', industry_type=Company.INDUSTRY_TRADING)
        memberships = {
            user: create_member(company=cls.company, user=user, role='user')
            for user in (cls.owner, cls.bob, cls.carol)
        }
        create_member(company=other, user=cls.outsider, role='user')

        provider = ConnectionProvider.objects.get(key='baileys')

        def account(user, name, phone):
            comm = CommunicationAccount.objects.create(
                company=cls.company, provider=provider, channel='whatsapp', name=name,
            )
            CommunicationAccountAssignment.objects.create(
                company=cls.company, communication_account=comm, membership=memberships[user],
                access_level=CommunicationAccountAssignment.ACCESS_OWNER,
            )
            return WhatsAppAccount.objects.create(
                owner=user, communication_account=comm, display_name=name, phone_number=phone,
            )

        cls.owner_account = account(cls.owner, 'Owner WA', '971500000010')
        cls.bob_account = account(cls.bob, 'Bob WA', '971500000011')
        account(cls.carol, 'Carol WA', '971500000012')
        cls.customer = WhatsAppContact.objects.create(
            account=cls.owner_account, wa_contact_id='971555000111@s.whatsapp.net',
            phone_number='971555000111', display_name='Customer',
        )

    def setUp(self):
        self.client = APIClient()

    def inquiry(self, key, first_seen_at=None):
        return Inquiry.objects.create(
            company=self.company, account=self.owner_account, contact=self.customer,
            inquiry_type='buy', products=[], summary=key, dedup_key=f'buy:share:{key}',
            source_type='direct', first_seen_at=first_seen_at or now(),
        )

    def feed(self, user, **params):
        self.client.force_authenticate(user)
        resp = self.client.get('/api/inquiries/open-feed/', {
            'type': 'buy', 'status': 'all',
            'date_from': (now() - timedelta(days=1)).date().isoformat(),
            'date_to': now().date().isoformat(),
            **params,
        })
        self.assertEqual(resp.status_code, 200, resp.content)
        return {row['id']: row for row in resp.json()['results']}

    def share_all(self, user, recipients):
        self.client.force_authenticate(user)
        return self.client.put(
            '/api/inquiry-sharing/recipients/', {'recipient_ids': [u.pk for u in recipients]}, format='json',
        )

    def set_status(self, user, inquiry, status_value, **extra):
        self.client.force_authenticate(user)
        return self.client.patch(f'/api/inquiries/{inquiry.pk}/', {'status': status_value, **extra}, format='json')

    def test_unshared_inquiry_is_invisible_to_other_users(self):
        inquiry = self.inquiry('private')
        self.assertNotIn(inquiry.pk, self.feed(self.bob))
        self.assertEqual(self.set_status(self.bob, inquiry, 'closed').status_code, 404)

    def test_share_all_covers_only_inquiries_from_now_on(self):
        before = self.inquiry('before', first_seen_at=now() - timedelta(hours=1))
        resp = self.share_all(self.owner, [self.bob])
        self.assertEqual(resp.status_code, 200, resp.content)
        after = self.inquiry('after')

        feed = self.feed(self.bob)
        self.assertNotIn(before.pk, feed)
        self.assertTrue(feed[after.pk]['is_shared'])
        self.assertEqual(feed[after.pk]['shared_by'], ['owner'])
        self.assertEqual(feed[after.pk]['status'], 'open')
        # The recipient cannot open the owner's chat.
        self.assertIsNone(feed[after.pk]['source_chat_id'])
        self.assertNotIn(after.pk, self.feed(self.carol))

    def test_recipient_actions_are_separate_from_owner_and_each_other(self):
        self.share_all(self.owner, [self.bob, self.carol])
        inquiry = self.inquiry('shared')

        resp = self.set_status(self.bob, inquiry, 'quoted_waiting', remarks='sent 5425')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.json()['status'], 'quoted_waiting')

        inquiry.refresh_from_db()
        self.assertEqual(inquiry.status, InquiryStatus.OPEN)
        self.assertEqual(self.feed(self.carol)[inquiry.pk]['status'], 'open')
        self.assertEqual(self.feed(self.bob)[inquiry.pk]['status'], 'quoted_waiting')

        handling = self.feed(self.owner)[inquiry.pk]['shared_handling']
        self.assertEqual(len(handling), 1)
        self.assertEqual(handling[0]['user_name'], 'bob')
        self.assertEqual(handling[0]['status'], 'quoted_waiting')
        self.assertEqual(handling[0]['remarks'], 'sent 5425')

        # The owner's own action stays on the inquiry and does not reach Bob's view.
        self.assertEqual(self.set_status(self.owner, inquiry, 'closed').status_code, 200)
        self.assertEqual(self.feed(self.bob)[inquiry.pk]['status'], 'quoted_waiting')

        self.set_status(self.bob, inquiry, 'deal_done')
        self.assertEqual(
            list(SharedInquiryActionEvent.objects.filter(inquiry=inquiry, user=self.bob).values_list('status', flat=True)),
            ['quoted_waiting', 'deal_done'],
        )
        self.assertIsNotNone(SharedInquiryAction.objects.get(inquiry=inquiry, user=self.bob).closed_at)

    def test_status_filter_uses_the_viewers_own_status(self):
        self.share_all(self.owner, [self.bob])
        inquiry = self.inquiry('filter')
        self.assertIn(inquiry.pk, self.feed(self.bob, status='open'))
        self.set_status(self.bob, inquiry, 'quoted_waiting')
        self.assertNotIn(inquiry.pk, self.feed(self.bob, status='open'))
        self.assertIn(inquiry.pk, self.feed(self.bob, status='quoted_waiting'))
        # The owner's status is still open.
        self.assertIn(inquiry.pk, self.feed(self.owner, status='open'))

    def test_recipient_cannot_change_the_inquiry_itself(self):
        self.share_all(self.owner, [self.bob])
        inquiry = self.inquiry('owner-only')
        self.client.force_authenticate(self.bob)
        resp = self.client.patch(f'/api/inquiries/{inquiry.pk}/', {'classification_rating': 1}, format='json')
        self.assertEqual(resp.status_code, 403)
        resp = self.client.post(f'/api/inquiries/{inquiry.pk}/correct-match/', {'index': 0, 'product_id': 1}, format='json')
        self.assertEqual(resp.status_code, 404)
        resp = self.set_status(self.bob, inquiry, 'not_a_status')
        self.assertEqual(resp.status_code, 400)

    def test_individual_share_and_revoke(self):
        inquiry = self.inquiry('single', first_seen_at=now() - timedelta(hours=2))
        self.client.force_authenticate(self.owner)
        resp = self.client.post(f'/api/inquiries/{inquiry.pk}/shares/', {'recipient_ids': [self.carol.pk]}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        shared = {row['id']: row['shared'] for row in resp.json()['recipients']}
        self.assertEqual(shared, {self.bob.pk: False, self.carol.pk: True})

        self.assertEqual(self.feed(self.carol)[inquiry.pk]['shared_by'], ['owner'])
        self.set_status(self.carol, inquiry, 'price_high')

        self.client.force_authenticate(self.owner)
        self.client.post(f'/api/inquiries/{inquiry.pk}/shares/', {'recipient_ids': []}, format='json')
        self.assertNotIn(inquiry.pk, self.feed(self.carol))
        self.assertEqual(InquiryShare.objects.filter(inquiry=inquiry, revoked_at__isnull=False).count(), 1)
        # Carol's action history survives the revoke.
        self.assertTrue(SharedInquiryActionEvent.objects.filter(inquiry=inquiry, user=self.carol).exists())

    def test_recipients_must_be_company_members(self):
        resp = self.share_all(self.owner, [self.outsider])
        self.assertEqual(resp.status_code, 400)
        inquiry = self.inquiry('outsider')
        self.client.force_authenticate(self.owner)
        resp = self.client.post(f'/api/inquiries/{inquiry.pk}/shares/', {'recipient_ids': [self.outsider.pk]}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_turning_share_all_off_hides_inquiries_and_on_again_starts_fresh(self):
        self.share_all(self.owner, [self.bob])
        first = self.inquiry('first')
        self.assertIn(first.pk, self.feed(self.bob))
        self.share_all(self.owner, [])
        self.assertNotIn(first.pk, self.feed(self.bob))
        self.share_all(self.owner, [self.bob])
        self.assertNotIn(first.pk, self.feed(self.bob))

        self.client.force_authenticate(self.owner)
        settings = self.client.get('/api/inquiry-sharing/').json()
        self.assertTrue(settings['owns_accounts'])
        self.assertEqual({r['id']: r['shared'] for r in settings['recipients']}, {self.bob.pk: True, self.carol.pk: False})

    def test_recipient_messages_the_customer_from_their_own_account(self):
        self.share_all(self.owner, [self.bob])
        inquiry = self.inquiry('message')
        self.client.force_authenticate(self.bob)

        resp = self.client.post(
            f'/api/inquiries/{inquiry.pk}/shared-direct-chat/', {'account': self.owner_account.pk}, format='json',
        )
        self.assertEqual(resp.status_code, 400)

        resp = self.client.post(
            f'/api/inquiries/{inquiry.pk}/shared-direct-chat/', {'account': self.bob_account.pk}, format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        chat = WhatsAppChat.objects.get(pk=resp.json()['id'])
        self.assertEqual(chat.account, self.bob_account)
        self.assertEqual(chat.wa_chat_id, '971555000111@s.whatsapp.net')
        self.assertEqual(chat.contact.phone_number, '971555000111')
        self.assertEqual(WhatsAppContact.objects.filter(account=self.bob_account).count(), 1)
        # A customer Bob has never chatted with must stay subject to the new-chat safety checks.
        self.assertFalse(chat.contact.is_existing_chat)
        from apps.whatsapp_bridge.outbound.policy import new_chat_snapshot
        self.assertEqual(new_chat_snapshot(self.bob_account, chat.wa_chat_id)['state'], 'likely_new')
