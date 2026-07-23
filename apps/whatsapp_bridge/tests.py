import json
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, Client
from django.utils import timezone

from .models import (
    WhatsAppAccount, WhatsAppContact, WhatsAppMessage,
    WhatsAppUnresolvedMessage, ResolutionStatus,
)
from .services.ingestion_service import IngestionService

INTERNAL_HEADERS = {'HTTP_X_INTERNAL_TOKEN': 'test-token'}


def _make_account(**overrides):
    owner, _ = User.objects.get_or_create(username='unresolved-message-tests-owner')
    fields = {
        'owner': owner,
        'display_name': 'Test Account',
        'phone_number': '971500000000',
        'worker_session_id': 'test-session',
    }
    fields.update(overrides)
    return WhatsAppAccount.objects.create(**fields)


def _unresolved_payload(**overrides):
    payload = {
        'worker_session_id': None,  # filled per-test
        'raw_jid': '16011805913098@lid',
        'participant_jid': '',
        'lid_jid': '16011805913098@lid',
        'from_me': True,
        'direction': 'outbound',
        'message_type': 'text',
        'message_text': '5100',
        'has_media': False,
        'message_time': timezone.now().isoformat(),
        'push_name': '',
        'is_history': False,
        'reason': 'unresolvable_lid',
        'raw_key': {'id': 'ABC123', 'fromMe': True, 'remoteJid': '16011805913098@lid'},
        'raw_payload': {
            'provider_message_id': 'ABC123',
            'chat_type': 'individual',
            'sender_number': '',
            'push_name': '',
            'group_name': '',
            'direction': 'outbound',
            'message_type': 'text',
            'message_text': '5100',
            'message_time': timezone.now().isoformat(),
            'has_media': False,
            'media_mime_type': '',
            'media_url': None,
            'raw_payload': {'key': {'id': 'ABC123'}, 'message': {'conversation': '5100'}},
        },
        'provider_message_id': 'ABC123',
    }
    payload.update(overrides)
    return payload


class UnresolvedMessagePreservationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.account = _make_account(phone_number='971500000000', worker_session_id='test-session')

    def test_preserve_creates_pending_row_with_full_content(self):
        payload = _unresolved_payload(worker_session_id=self.account.pk)
        obj = IngestionService().preserve_unresolved_message(self.account, payload)

        self.assertEqual(obj.resolution_status, ResolutionStatus.PENDING)
        self.assertEqual(obj.lid_jid, '16011805913098@lid')
        self.assertEqual(obj.message_text, '5100')
        self.assertEqual(obj.reason, 'unresolvable_lid')
        self.assertTrue(obj.from_me)
        self.assertIsNotNone(obj.raw_payload)
        self.assertEqual(obj.raw_payload['provider_message_id'], 'ABC123')

    def test_preserve_is_idempotent_on_provider_message_id(self):
        payload = _unresolved_payload(worker_session_id=self.account.pk)
        IngestionService().preserve_unresolved_message(self.account, payload)
        IngestionService().preserve_unresolved_message(self.account, {**payload, 'message_text': '5100 updated'})

        self.assertEqual(
            WhatsAppUnresolvedMessage.objects.filter(account=self.account, provider_message_id='ABC123').count(),
            1,
        )
        row = WhatsAppUnresolvedMessage.objects.get(account=self.account, provider_message_id='ABC123')
        self.assertEqual(row.message_text, '5100 updated')

    def test_preserve_without_provider_message_id_does_not_collide(self):
        payload = _unresolved_payload(worker_session_id=self.account.pk, provider_message_id=None)
        payload['raw_payload']['provider_message_id'] = None
        IngestionService().preserve_unresolved_message(self.account, payload)
        IngestionService().preserve_unresolved_message(self.account, payload)

        self.assertEqual(
            WhatsAppUnresolvedMessage.objects.filter(account=self.account, provider_message_id__isnull=True).count(),
            2,
        )


class RecoverUnresolvedForLidTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.account = _make_account(phone_number='971500000001', worker_session_id='test-session-2')

    def setUp(self):
        # Background embedding/classification hit real AI providers — irrelevant to
        # what these tests verify (that a WhatsAppMessage gets created + linked) and
        # must not make live network calls during a test run.
        self._proc_patch = patch('apps.whatsapp_bridge.services.ingestion_service._process_message_in_background')
        self._embed_patch = patch('apps.whatsapp_bridge.services.ingestion_service._embed_in_background')
        self._proc_patch.start()
        self._embed_patch.start()
        self.addCleanup(self._proc_patch.stop)
        self.addCleanup(self._embed_patch.stop)

    def test_recover_with_no_pending_rows_is_a_safe_noop(self):
        result = IngestionService().recover_unresolved_for_lid(self.account, '99999@lid', '971500000009@s.whatsapp.net')
        self.assertEqual(result, {'total': 0, 'recovered': 0, 'failed': 0})

    def test_recover_creates_message_and_marks_row_resolved(self):
        payload = _unresolved_payload(worker_session_id=self.account.pk)
        row = IngestionService().preserve_unresolved_message(self.account, payload)
        self.assertEqual(row.resolution_status, ResolutionStatus.PENDING)

        result = IngestionService().recover_unresolved_for_lid(
            self.account, '16011805913098@lid', '971544732206@s.whatsapp.net',
        )
        self.assertEqual(result, {'total': 1, 'recovered': 1, 'failed': 0})

        row.refresh_from_db()
        self.assertEqual(row.resolution_status, ResolutionStatus.RESOLVED)
        self.assertIsNotNone(row.resolved_message)
        self.assertIsNotNone(row.resolved_at)
        self.assertEqual(row.resolution_error, '')

        message = WhatsAppMessage.objects.get(account=self.account, provider_message_id='ABC123')
        self.assertEqual(message.message_text, '5100')
        self.assertEqual(message.chat.wa_chat_id, '971544732206@s.whatsapp.net')
        self.assertEqual(message.contact.wa_contact_id, '971544732206@s.whatsapp.net')

    def test_recovery_is_duplicate_safe_when_message_already_ingested(self):
        """Simulates: Baileys retried delivery and it succeeded normally BEFORE
        the persisted-mapping recovery ran. Recovery must link, not duplicate."""
        payload = _unresolved_payload(worker_session_id=self.account.pk)
        row = IngestionService().preserve_unresolved_message(self.account, payload)

        service = IngestionService()
        normal_payload = {
            'worker_session_id': self.account.pk,
            'provider_message_id': 'ABC123',
            'chat_id': '971544732206@s.whatsapp.net',
            'chat_type': 'individual',
            'direction': 'outbound',
            'message_text': '5100',
            'message_type': 'text',
            'message_time': timezone.now().isoformat(),
            'sender_number': '',
            'push_name': '',
        }
        service.ingest_message(normal_payload)
        self.assertEqual(WhatsAppMessage.objects.filter(provider_message_id='ABC123').count(), 1)

        result = service.recover_unresolved_for_lid(
            self.account, '16011805913098@lid', '971544732206@s.whatsapp.net',
        )
        self.assertEqual(result, {'total': 1, 'recovered': 1, 'failed': 0})
        self.assertEqual(WhatsAppMessage.objects.filter(provider_message_id='ABC123').count(), 1)

        row.refresh_from_db()
        self.assertEqual(row.resolution_status, ResolutionStatus.RESOLVED)

    def test_recovery_failure_leaves_row_pending_with_error_recorded(self):
        payload = _unresolved_payload(worker_session_id=self.account.pk)
        row = IngestionService().preserve_unresolved_message(self.account, payload)

        with patch.object(IngestionService, '_insert_message', side_effect=RuntimeError('boom')):
            result = IngestionService().recover_unresolved_for_lid(
                self.account, '16011805913098@lid', '971544732206@s.whatsapp.net',
            )

        self.assertEqual(result, {'total': 1, 'recovered': 0, 'failed': 1})
        row.refresh_from_db()
        self.assertEqual(row.resolution_status, ResolutionStatus.PENDING)
        self.assertIn('boom', row.resolution_error)
        self.assertFalse(WhatsAppMessage.objects.filter(provider_message_id='ABC123').exists())

    def test_recovery_of_history_message_does_not_trigger_live_classification(self):
        payload = _unresolved_payload(worker_session_id=self.account.pk, is_history=True)
        IngestionService().preserve_unresolved_message(self.account, payload)

        with patch('apps.whatsapp_bridge.services.ingestion_service._process_message_in_background') as live_proc, \
             patch('apps.whatsapp_bridge.services.ingestion_service._embed_in_background') as embed_only:
            IngestionService().recover_unresolved_for_lid(
                self.account, '16011805913098@lid', '971544732206@s.whatsapp.net',
            )
            live_proc.assert_not_called()
            embed_only.assert_called_once()


class UnresolvedMessageEndpointTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.account = _make_account(phone_number='971500000002', worker_session_id='test-session-3')

    def setUp(self):
        self.client = Client()
        from django.conf import settings
        settings.INTERNAL_API_TOKEN = 'test-token'

    def test_endpoint_rejects_missing_token(self):
        resp = self.client.post(
            '/api/internal/whatsapp/unresolved-message/',
            data=json.dumps(_unresolved_payload(worker_session_id=self.account.pk)),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 401)

    def test_endpoint_persists_and_returns_pending_status(self):
        resp = self.client.post(
            '/api/internal/whatsapp/unresolved-message/',
            data=json.dumps(_unresolved_payload(worker_session_id=self.account.pk)),
            content_type='application/json',
            **INTERNAL_HEADERS,
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body['success'])
        self.assertEqual(body['resolution_status'], 'pending')
        self.assertTrue(
            WhatsAppUnresolvedMessage.objects.filter(account=self.account, provider_message_id='ABC123').exists()
        )

    def test_endpoint_requires_raw_jid(self):
        payload = _unresolved_payload(worker_session_id=self.account.pk)
        del payload['raw_jid']
        resp = self.client.post(
            '/api/internal/whatsapp/unresolved-message/',
            data=json.dumps(payload),
            content_type='application/json',
            **INTERNAL_HEADERS,
        )
        self.assertEqual(resp.status_code, 400)

    def test_endpoint_rejects_unknown_account(self):
        nonexistent_id = self.account.pk + 999999
        resp = self.client.post(
            '/api/internal/whatsapp/unresolved-message/',
            data=json.dumps(_unresolved_payload(worker_session_id=nonexistent_id)),
            content_type='application/json',
            **INTERNAL_HEADERS,
        )
        self.assertEqual(resp.status_code, 404)


class LidMappingLookupEndpointTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.account = _make_account(phone_number='971500000003', worker_session_id='test-session-4')
        cls.contact = WhatsAppContact.objects.create(
            account=cls.account,
            wa_contact_id='971544732206@s.whatsapp.net',
            lid_jid='16011805913098@lid',
            display_name='Azan',
        )

    def setUp(self):
        self.client = Client()
        from django.conf import settings
        settings.INTERNAL_API_TOKEN = 'test-token'

    def test_lookup_found(self):
        resp = self.client.get(
            f'/api/internal/whatsapp/lid-mapping/{self.account.pk}/',
            {'lid_jid': '16011805913098@lid'},
            **INTERNAL_HEADERS,
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body['found'])
        self.assertEqual(body['phone_jid'], '971544732206@s.whatsapp.net')

    def test_lookup_not_found(self):
        resp = self.client.get(
            f'/api/internal/whatsapp/lid-mapping/{self.account.pk}/',
            {'lid_jid': '00000000@lid'},
            **INTERNAL_HEADERS,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.json()['found'])

    def test_lookup_requires_lid_jid_param(self):
        resp = self.client.get(
            f'/api/internal/whatsapp/lid-mapping/{self.account.pk}/',
            **INTERNAL_HEADERS,
        )
        self.assertEqual(resp.status_code, 400)

    def test_lookup_rejects_missing_token(self):
        resp = self.client.get(
            f'/api/internal/whatsapp/lid-mapping/{self.account.pk}/',
            {'lid_jid': '16011805913098@lid'},
        )
        self.assertEqual(resp.status_code, 401)


class ContactsUpdateTriggersRecoveryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.account = _make_account(phone_number='971500000004', worker_session_id='test-session-5')

    def setUp(self):
        self.client = Client()
        from django.conf import settings
        settings.INTERNAL_API_TOKEN = 'test-token'
        self._proc_patch = patch('apps.whatsapp_bridge.services.ingestion_service._process_message_in_background')
        self._proc_patch.start()
        self.addCleanup(self._proc_patch.stop)

    def test_contacts_update_with_lid_triggers_recovery_synchronously_in_test(self):
        payload = _unresolved_payload(worker_session_id=self.account.pk)
        IngestionService().preserve_unresolved_message(self.account, payload)

        class _ImmediateThread:
            def __init__(self, target=None, args=(), daemon=None):
                self._target, self._args = target, args

            def start(self):
                self._target(*self._args)

        with patch('apps.whatsapp_bridge.views.threading.Thread', _ImmediateThread):
            resp = self.client.post(
                '/api/internal/whatsapp/contacts-update/',
                data=json.dumps({
                    'worker_session_id': self.account.pk,
                    'contacts': [{
                        'wa_contact_id': '971544732206@s.whatsapp.net',
                        'push_name': 'Azan',
                        'phone_number': '971544732206',
                        'lid_jid': '16011805913098@lid',
                    }],
                }),
                content_type='application/json',
                **INTERNAL_HEADERS,
            )
        self.assertEqual(resp.status_code, 200)

        row = WhatsAppUnresolvedMessage.objects.get(account=self.account, provider_message_id='ABC123')
        self.assertEqual(row.resolution_status, ResolutionStatus.RESOLVED)
        self.assertTrue(WhatsAppMessage.objects.filter(provider_message_id='ABC123').exists())

    def test_contacts_update_reports_updated_skipped_and_rejected_counts(self):
        resp = self.client.post(
            '/api/internal/whatsapp/contacts-update/',
            data=json.dumps({
                'worker_session_id': self.account.pk,
                'contacts': [
                    {
                        'wa_contact_id': '971544732206@s.whatsapp.net',
                        'push_name': 'Azan',
                        'phone_number': '971544732206',
                    },
                    {
                        'wa_contact_id': '971500000000@s.whatsapp.net',
                        'push_name': '',
                    },
                    {
                        'wa_contact_id': '16011805913098@lid',
                        'push_name': 'LID Primary',
                    },
                ],
            }),
            content_type='application/json',
            **INTERNAL_HEADERS,
        )

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {
            'status': 'ok',
            'updated': 1,
            'skipped': 1,
            'rejected': 1,
        })
        self.assertTrue(
            WhatsAppContact.objects.filter(
                account=self.account,
                wa_contact_id='971544732206@s.whatsapp.net',
            ).exists()
        )
        self.assertFalse(
            WhatsAppContact.objects.filter(account=self.account, wa_contact_id='16011805913098@lid').exists()
        )
