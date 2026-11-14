from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils.timezone import now
from rest_framework.test import APIClient

from apps.tenancy.models import (
    CommunicationAccount, CommunicationAccountAssignment, Company, CompanyMembership, ConnectionProvider,
)
from apps.trading.models import Inquiry, InquiryStatus, InquiryStatusEvent
from apps.whatsapp_bridge.models import WhatsAppAccount


class InquiryStatusHistoryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model().objects
        cls.owner = users.create_user(username='owner', password='pw')
        cls.admin = users.create_user(username='boss', password='pw', first_name='Boss')
        cls.company = Company.objects.create(name='Hist Co', slug='hist-co', industry_type=Company.INDUSTRY_TRADING)
        owner_membership = CompanyMembership.objects.create(
            company=cls.company, user=cls.owner, role=CompanyMembership.ROLE_USER,
        )
        CompanyMembership.objects.create(company=cls.company, user=cls.admin, role=CompanyMembership.ROLE_SUPER_USER)
        comm = CommunicationAccount.objects.create(
            company=cls.company, provider=ConnectionProvider.objects.get(key='baileys'),
            channel='whatsapp', name='Owner WA',
        )
        CommunicationAccountAssignment.objects.create(
            company=cls.company, communication_account=comm, membership=owner_membership,
            access_level=CommunicationAccountAssignment.ACCESS_OWNER,
        )
        cls.account = WhatsAppAccount.objects.create(
            owner=cls.owner, communication_account=comm, display_name='Owner WA', phone_number='971500000020',
        )

    def setUp(self):
        self.client = APIClient()

    def inquiry(self, key='x', first_seen_at=None):
        return Inquiry.objects.create(
            company=self.company, account=self.account, inquiry_type='buy', products=[],
            summary=key, dedup_key=f'buy:hist:{key}', source_type='direct',
            first_seen_at=first_seen_at or now(),
        )

    def patch(self, user, inquiry, data):
        self.client.force_authenticate(user)
        return self.client.patch(f'/api/inquiries/{inquiry.pk}/', data, format='json')

    def feed_row(self, user, inquiry):
        self.client.force_authenticate(user)
        resp = self.client.get('/api/inquiries/open-feed/', {
            'type': 'buy', 'status': 'all',
            'date_from': (now() - timedelta(days=1)).date().isoformat(), 'date_to': now().date().isoformat(),
        })
        return {row['id']: row for row in resp.json()['results']}[inquiry.pk]

    def test_every_status_change_is_recorded_with_who_made_it(self):
        inquiry = self.inquiry()
        self.assertEqual(self.patch(self.owner, inquiry, {'status': 'quoted_waiting'}).status_code, 200)
        self.assertEqual(self.patch(self.admin, inquiry, {'status': 'price_high', 'remarks': 'too high'}).status_code, 200)

        events = list(InquiryStatusEvent.objects.filter(inquiry=inquiry).order_by('created_at', 'id'))
        self.assertEqual(
            [(e.user, e.old_status, e.new_status, e.source) for e in events],
            [
                (self.owner, 'open', 'quoted_waiting', 'update'),
                (self.admin, 'quoted_waiting', 'price_high', 'update'),
            ],
        )
        self.assertEqual(events[1].remarks, 'too high')
        inquiry.refresh_from_db()
        self.assertEqual(inquiry.status, InquiryStatus.PRICE_HIGH)

    def test_board_shows_when_someone_other_than_the_owner_changed_it(self):
        inquiry = self.inquiry()
        self.assertIsNone(self.feed_row(self.owner, inquiry)['status_change'])
        self.patch(self.owner, inquiry, {'status': 'quoted_waiting'})
        change = self.feed_row(self.owner, inquiry)['status_change']
        self.assertTrue(change['by_owner'])
        self.patch(self.admin, inquiry, {'status': 'price_high'})
        change = self.feed_row(self.owner, inquiry)['status_change']
        self.assertEqual((change['user_name'], change['by_owner'], change['status_label']), ('Boss', False, 'Price High'))

    def test_unchanged_status_and_remarks_only_record_nothing(self):
        inquiry = self.inquiry()
        self.patch(self.owner, inquiry, {'status': 'open'})
        self.patch(self.owner, inquiry, {'remarks': 'called'})
        inquiry.refresh_from_db()
        self.assertEqual(inquiry.remarks, 'called')
        self.patch(self.owner, inquiry, {'status': 'open', 'remarks': 'again'})
        inquiry.refresh_from_db()
        self.assertEqual(inquiry.remarks, 'again')
        self.assertFalse(InquiryStatusEvent.objects.filter(inquiry=inquiry).exists())

    def test_invalid_status_is_rejected_and_put_is_blocked(self):
        inquiry = self.inquiry()
        self.assertEqual(self.patch(self.owner, inquiry, {'status': 'bogus'}).status_code, 400)
        self.client.force_authenticate(self.owner)
        resp = self.client.put(f'/api/inquiries/{inquiry.pk}/', {'status': 'closed', 'summary': 'x'}, format='json')
        self.assertEqual(resp.status_code, 405)
        inquiry.refresh_from_db()
        self.assertEqual(inquiry.status, InquiryStatus.OPEN)

    def test_close_stale_records_one_event_per_closed_inquiry(self):
        stale = [self.inquiry(f'stale{n}', first_seen_at=now() - timedelta(hours=5)) for n in range(2)]
        quoted = self.inquiry('quoted', first_seen_at=now() - timedelta(hours=5))
        self.patch(self.owner, quoted, {'status': 'quoted_waiting'})
        fresh = self.inquiry('fresh')

        self.client.force_authenticate(self.admin)
        resp = self.client.post('/api/inquiries/close-stale/', {'hours': 2}, format='json')
        self.assertEqual(resp.json()['closed'], 2)
        events = InquiryStatusEvent.objects.filter(source=InquiryStatusEvent.SOURCE_CLOSE_STALE)
        self.assertEqual({e.inquiry_id for e in events}, {i.pk for i in stale})
        self.assertTrue(all(e.user == self.admin and e.new_status == 'closed' for e in events))
        fresh.refresh_from_db()
        quoted.refresh_from_db()
        self.assertEqual((fresh.status, quoted.status), ('open', 'quoted_waiting'))

    def test_manual_inquiry_records_its_first_status_and_history_endpoint(self):
        self.client.force_authenticate(self.owner)
        resp = self.client.post('/api/inquiries/manual/', {
            'account_id': self.account.pk, 'inquiry_type': 'buy', 'summary': 'Phone',
            'items': [{'canonical_name': 'Phone', 'quantity': 1}],
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        inquiry = Inquiry.objects.get(pk=resp.json()['id'])
        self.patch(self.admin, inquiry, {'status': 'closed'})

        self.client.force_authenticate(self.owner)
        history = self.client.get(f'/api/inquiries/{inquiry.pk}/status-history/').json()['results']
        self.assertEqual(
            [(h['user_name'], h['old_status'], h['new_status'], h['source']) for h in history],
            [('Boss', 'open', 'closed', 'update'), ('owner', '', 'open', 'manual_create')],
        )
