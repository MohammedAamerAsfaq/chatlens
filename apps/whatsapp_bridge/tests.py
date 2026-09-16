import json
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, Client
from django.utils import timezone

from apps.tenancy.models import CommunicationAccount, Company, ConnectionProvider
from .models import (
    WhatsAppAccount, WhatsAppChat, WhatsAppContact, WhatsAppMessage,
    WhatsAppAccountCapacity, WhatsAppGroup, WhatsAppUnresolvedMessage, ResolutionStatus,
)
from .services.destination_policy import classify_destination, evaluate_destination
from .services.group_metadata_service import upsert_group_metadata
from .services.ingestion_service import IngestionService, _classify_skip_reason

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
        self._automation_patch = patch('apps.whatsapp_bridge.services.ingestion_service._process_automation_in_background')
        self._embed_patch = patch('apps.whatsapp_bridge.services.ingestion_service._embed_in_background')
        self._proc_patch.start()
        self._automation_patch.start()
        self._embed_patch.start()
        self.addCleanup(self._proc_patch.stop)
        self.addCleanup(self._automation_patch.stop)
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
             patch('apps.whatsapp_bridge.services.ingestion_service._process_automation_in_background') as live_auto, \
             patch('apps.whatsapp_bridge.services.ingestion_service._embed_in_background') as embed_only:
            IngestionService().recover_unresolved_for_lid(
                self.account, '16011805913098@lid', '971544732206@s.whatsapp.net',
            )
            live_proc.assert_not_called()
            live_auto.assert_not_called()
            embed_only.assert_called_once()


class LiveIngestionAutomationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.account = _make_account(phone_number='971500000003', worker_session_id='test-session-4')

    def test_live_ingest_starts_classification_and_automation_background_paths(self):
        payload = {
            'worker_session_id': self.account.pk,
            'provider_message_id': 'LIVE-AUTO-1',
            'chat_id': '971544732207@s.whatsapp.net',
            'chat_type': 'individual',
            'direction': 'inbound',
            'message_text': 'Fresh price list',
            'message_type': 'text',
            'message_time': timezone.now().isoformat(),
            'sender_number': '971544732207',
            'push_name': 'Supplier',
        }

        with patch('apps.whatsapp_bridge.services.ingestion_service._process_message_in_background') as live_proc, \
             patch('apps.whatsapp_bridge.services.ingestion_service._process_automation_in_background') as live_auto:
            message = IngestionService().ingest_message(payload)

        live_proc.assert_called_once()
        live_auto.assert_called_once_with(message.pk)


class AccountSettingsEndpointTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.account = _make_account(
            phone_number='971500000020',
            worker_session_id='settings-session',
            outbound_sending_enabled=True,
            direct_sending_enabled=True,
            recipient_interval_ms=7000,
            account_interval_ms=2000,
            allow_concurrent_sends=True,
            max_concurrent_sends=3,
        )

    def setUp(self):
        self.client = Client()
        from django.conf import settings
        settings.INTERNAL_API_TOKEN = 'test-token'

    def test_worker_receives_outbound_safety_settings(self):
        resp = self.client.get(
            f'/api/internal/whatsapp/account-settings/{self.account.pk}/',
            **INTERNAL_HEADERS,
        )

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {
            'sync_history': True,
            'history_days': None,
            'idle_disconnect_minutes': 0,
            'auto_download_media': True,
            'outbound_sending_enabled': True,
            'direct_sending_enabled': True,
            'group_sending_enabled': False,
            'recipient_interval_ms': 7000,
            'account_interval_ms': 2000,
            'allow_concurrent_sends': True,
            'max_concurrent_sends': 3,
            'unknown_new_chat_policy': 'block',
        })

    def test_worker_settings_reject_missing_token(self):
        resp = self.client.get(
            f'/api/internal/whatsapp/account-settings/{self.account.pk}/',
        )

        self.assertEqual(resp.status_code, 401)


class CapacityTelemetryEndpointTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.account = _make_account(
            phone_number='971500000022',
            worker_session_id='capacity-session',
        )

    def setUp(self):
        self.client = Client()
        from django.conf import settings
        settings.INTERNAL_API_TOKEN = 'test-token'

    def _post(self, payload):
        return self.client.post(
            '/api/internal/whatsapp/account-capacity/',
            data=json.dumps({'worker_session_id': self.account.pk, **payload}),
            content_type='application/json',
            **INTERNAL_HEADERS,
        )

    def test_available_telemetry_is_persisted(self):
        resp = self._post({
            'source': 'baileys_v7',
            'cap': {
                'status': 'available',
                'checked_at': '2026-09-16T10:00:00Z',
                'data': {
                    'total_quota': 10,
                    'used_quota': 3,
                    'cycle_end_timestamp': '2026-09-17T00:00:00Z',
                    'capping_status': 'FIRST_WARNING',
                },
            },
            'reachout': {
                'status': 'available',
                'data': {
                    'is_active': True,
                    'time_enforcement_ends': '2026-09-16T12:00:00Z',
                    'enforcement_type': 'BIZ_QUALITY',
                },
            },
        })

        self.assertEqual(resp.status_code, 200)
        capacity = WhatsAppAccountCapacity.objects.get(account=self.account)
        self.assertEqual(capacity.remaining_quota, 7)
        self.assertEqual(capacity.capping_status, 'FIRST_WARNING')
        self.assertTrue(capacity.reachout_lock_active)
        self.assertEqual(capacity.reachout_enforcement_type, 'BIZ_QUALITY')

    def test_failed_refresh_preserves_last_valid_cap_sample(self):
        self._post({
            'cap': {
                'status': 'available',
                'data': {'total_quota': 10, 'used_quota': 3},
            },
        })
        resp = self._post({
            'cap': {
                'status': 'unavailable',
                'error': 'Provider returned 500',
            },
        })

        self.assertEqual(resp.status_code, 200)
        capacity = WhatsAppAccountCapacity.objects.get(account=self.account)
        self.assertEqual(capacity.cap_fetch_status, 'unavailable')
        self.assertEqual(capacity.total_quota, 10)
        self.assertEqual(capacity.used_quota, 3)
        self.assertEqual(capacity.cap_error, 'Provider returned 500')

    def test_endpoint_requires_internal_token(self):
        resp = self.client.post(
            '/api/internal/whatsapp/account-capacity/',
            data=json.dumps({'worker_session_id': self.account.pk, 'cap': {}}),
            content_type='application/json',
        )

        self.assertEqual(resp.status_code, 401)


class DestinationPolicyTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.account = _make_account(
            phone_number='971500000021',
            outbound_sending_enabled=True,
            direct_sending_enabled=True,
            group_sending_enabled=True,
        )

    def test_destination_types_are_mutually_exclusive(self):
        community = WhatsAppGroup.objects.create(
            account=self.account,
            wa_group_id='120001@g.us',
            is_community=True,
        )
        announcement = WhatsAppGroup.objects.create(
            account=self.account,
            wa_group_id='120002@g.us',
            is_community_announcement=True,
        )

        self.assertEqual(classify_destination('971500000001@s.whatsapp.net'), 'direct_contact')
        self.assertEqual(classify_destination('120001@g.us', community), 'community')
        self.assertEqual(
            classify_destination('120002@g.us', announcement),
            'community_announcement',
        )
        self.assertEqual(classify_destination('123@newsletter'), 'channel')
        self.assertEqual(classify_destination('status@broadcast'), 'status')

    def test_full_group_metadata_calculates_admin_send_permission(self):
        group = upsert_group_metadata(self.account, {
            'group_id': '120003@g.us',
            'name': 'Admin announcements',
            'announce': True,
            'restrict': True,
            'account_is_participant': True,
            'account_participant_role': 'admin',
            'metadata_complete': True,
            'participants': [],
        })

        self.assertTrue(group.can_send)
        self.assertEqual(group.send_block_reason, '')
        self.assertTrue(group.announce)
        self.assertTrue(group.restrict)
        self.assertIsNotNone(group.metadata_refreshed_at)
        self.assertTrue(evaluate_destination(self.account, group.wa_group_id, group)['allowed'])

    def test_announcement_group_blocks_non_admin_member(self):
        group = upsert_group_metadata(self.account, {
            'group_id': '120004@g.us',
            'is_community': True,
            'is_community_announcement': True,
            'announce': True,
            'account_is_participant': True,
            'account_participant_role': 'member',
            'metadata_complete': True,
        })

        result = evaluate_destination(self.account, group.wa_group_id, group)
        self.assertFalse(result['allowed'])
        self.assertEqual(result['reason'], 'group_admin_required')

    def test_partial_metadata_does_not_erase_permission_state(self):
        group = upsert_group_metadata(self.account, {
            'group_id': '120005@g.us',
            'name': 'Original',
            'announce': True,
            'account_is_participant': True,
            'account_participant_role': 'admin',
            'metadata_complete': True,
        })
        refreshed_at = group.metadata_refreshed_at

        group = upsert_group_metadata(self.account, {
            'group_id': group.wa_group_id,
            'name': 'Renamed',
            'metadata_complete': False,
        })

        self.assertEqual(group.name, 'Renamed')
        self.assertTrue(group.announce)
        self.assertTrue(group.can_send)
        self.assertEqual(group.metadata_refreshed_at, refreshed_at)


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

        with (
            patch('apps.whatsapp_bridge.views.threading.Thread', _ImmediateThread),
            patch('apps.whatsapp_bridge.views.close_old_connections'),
            patch('apps.whatsapp_bridge.views.connection.close'),
        ):
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

    def test_contacts_update_batches_lid_recovery_into_one_thread(self):
        thread_starts = []

        class _CapturedThread:
            def __init__(self, target=None, args=(), daemon=None):
                self._target, self._args, self.daemon = target, args, daemon

            def start(self):
                thread_starts.append((self._target, self._args, self.daemon))

        with patch('apps.whatsapp_bridge.views.threading.Thread', _CapturedThread):
            resp = self.client.post(
                '/api/internal/whatsapp/contacts-update/',
                data=json.dumps({
                    'worker_session_id': self.account.pk,
                    'contacts': [
                        {
                            'wa_contact_id': '971544732206@s.whatsapp.net',
                            'push_name': 'Azan',
                            'phone_number': '971544732206',
                            'lid_jid': '16011805913098@lid',
                        },
                        {
                            'wa_contact_id': '971555555555@s.whatsapp.net',
                            'push_name': 'Second',
                            'phone_number': '971555555555',
                            'lid_jid': '15552143724787@lid',
                        },
                    ],
                }),
                content_type='application/json',
                **INTERNAL_HEADERS,
            )

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(thread_starts), 1)
        target, args, daemon = thread_starts[0]
        self.assertEqual(target.__name__, '_recover_unresolved_for_lid_batch_background')
        self.assertEqual(daemon, True)
        self.assertEqual(args[0], self.account.pk)
        self.assertEqual(args[1], [
            ('16011805913098@lid', '971544732206@s.whatsapp.net'),
            ('15552143724787@lid', '971555555555@s.whatsapp.net'),
        ])

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


class CompanyAiParsingGateTests(TestCase):
    def test_company_disabled_skips_ai_parsing_before_chat_or_account_settings(self):
        owner = User.objects.create_user(username='company-ai-gate-owner')
        provider = ConnectionProvider.objects.get(key='baileys')
        company = Company.objects.create(
            name='AI Disabled Company',
            slug='ai-disabled-company',
            ai_parsing_enabled=False,
        )
        communication_account = CommunicationAccount.objects.create(
            company=company,
            provider=provider,
            channel='whatsapp',
            name='AI Disabled WhatsApp',
        )
        account = WhatsAppAccount.objects.create(
            owner=owner,
            communication_account=communication_account,
            display_name='AI Disabled Account',
            phone_number='971500000111',
            worker_session_id='ai-disabled-account',
            ai_parsing_enabled=True,
        )
        contact = WhatsAppContact.objects.create(
            account=account,
            wa_contact_id='971500000222@s.whatsapp.net',
            phone_number='971500000222',
            display_name='Sender',
        )
        chat = WhatsAppChat.objects.create(
            account=account,
            contact=contact,
            wa_chat_id='971500000222@s.whatsapp.net',
            chat_type='individual',
            ai_parsing=True,
        )
        message = WhatsAppMessage.objects.create(
            account=account,
            chat=chat,
            contact=contact,
            provider_message_id='COMPANY_DISABLED_1',
            sender_number='971500000222',
            direction='inbound',
            message_type='text',
            message_text='WTB iPhone 17 Pro Max 256 Blue',
            message_time=timezone.now(),
        )

        self.assertEqual(_classify_skip_reason(message), 'company_disabled')
