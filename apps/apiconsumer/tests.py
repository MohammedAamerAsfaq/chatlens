import json
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.tenancy.models import CommunicationAccount, Company, CompanyMembership, ConnectionProvider
from apps.whatsapp_bridge.models import WhatsAppAccount

from .models import ApiKey, WebhookDeliveryAttempt, WebhookSubscription
from .task_handlers import deliver_webhook


def _make_company(**overrides):
    defaults = {'name': 'Acme External', 'slug': 'acme-external'}
    defaults.update(overrides)
    return Company.objects.create(**defaults)


def _make_account(company, owner):
    provider = ConnectionProvider.objects.get(key='baileys')
    communication_account = CommunicationAccount.objects.create(
        company=company, provider=provider, channel='whatsapp', name='Acme WhatsApp',
    )
    return WhatsAppAccount.objects.create(
        owner=owner, communication_account=communication_account,
        display_name='Acme Account', phone_number='971500000001',
        worker_session_id='acme-account', outbound_sending_enabled=True,
    )


class ApiKeyManagementViewTests(TestCase):
    def setUp(self):
        self.company = _make_company(name='Mgmt Co', slug='mgmt-co')
        self.admin = User.objects.create_user(username='mgmt-admin', password='pass12345')
        CompanyMembership.objects.create(company=self.company, user=self.admin, role=CompanyMembership.ROLE_ADMIN)
        self.client = Client()
        self.client.force_login(self.admin)

    def test_create_key_returns_the_secret_exactly_once(self):
        response = self.client.post(
            '/api/apiconsumer/keys/',
            data=json.dumps({'name': 'Test key', 'scopes': ['data:read', 'webhooks:manage']}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 201, response.content)
        body = response.json()
        self.assertTrue(body['secret'])
        self.assertTrue(body['secret'].startswith(body['key_prefix'] + '.'))
        self.assertEqual(body['name'], 'Test key')
        self.assertNotIn('secret_hash', body)
        self.assertEqual(ApiKey.objects.get(pk=body['id']).company, self.company)

    def test_revoke_key(self):
        api_key, _ = ApiKey.generate(company=self.company, name='To revoke', scopes=[ApiKey.SCOPE_DATA_READ])
        response = self.client.post(f'/api/apiconsumer/keys/{api_key.pk}/revoke/')
        self.assertEqual(response.status_code, 200)
        api_key.refresh_from_db()
        self.assertEqual(api_key.status, ApiKey.STATUS_REVOKED)


class ApiKeyAuthenticationTests(TestCase):
    def setUp(self):
        self.company = _make_company()
        self.api_key, self.secret = ApiKey.generate(
            company=self.company, name='Test key', scopes=[ApiKey.SCOPE_DATA_READ],
        )
        self.client = APIClient()
        self.url = reverse('external-contact-list')

    def _auth(self, token):
        return self.client.get(self.url, HTTP_AUTHORIZATION=f'Api-Key {token}')

    def test_valid_key_is_accepted(self):
        response = self._auth(self.secret)
        self.assertEqual(response.status_code, 200)

    def test_wrong_secret_is_rejected(self):
        prefix = self.secret.split('.')[0]
        response = self._auth(f'{prefix}.wrong-secret')
        self.assertEqual(response.status_code, 401)

    def test_revoked_key_is_rejected(self):
        self.api_key.revoke()
        response = self._auth(self.secret)
        self.assertEqual(response.status_code, 401)

    def test_expired_key_is_rejected(self):
        self.api_key.expires_at = timezone.now() - timezone.timedelta(seconds=1)
        self.api_key.save(update_fields=['expires_at'])
        response = self._auth(self.secret)
        self.assertEqual(response.status_code, 401)

    def test_inactive_company_is_rejected(self):
        self.company.is_active = False
        self.company.save(update_fields=['is_active'])
        response = self._auth(self.secret)
        self.assertEqual(response.status_code, 401)

    def test_missing_scope_is_forbidden(self):
        key, secret = ApiKey.generate(company=self.company, name='No scopes', scopes=[])
        response = self._auth(secret)
        self.assertEqual(response.status_code, 403)

    def test_cross_tenant_data_is_not_visible(self):
        other_company = _make_company(name='Other Co', slug='other-co')
        owner = User.objects.create_user(username='owner-1')
        _make_account(other_company, owner)
        response = self._auth(self.secret)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['results'] if 'results' in response.json() else response.json(), [])


class SendMessageViewTests(TestCase):
    def setUp(self):
        self.company = _make_company()
        self.owner = User.objects.create_user(username='owner-send')
        self.account = _make_account(self.company, self.owner)
        self.api_key, self.secret = ApiKey.generate(
            company=self.company, name='Send key', scopes=[ApiKey.SCOPE_MESSAGES_SEND],
        )
        self.client = APIClient()
        self.url = reverse('external-send-message')

    def _post(self, data, secret=None):
        return self.client.post(
            self.url, data, format='json',
            HTTP_AUTHORIZATION=f'Api-Key {secret or self.secret}',
        )

    def test_missing_scope_is_forbidden(self):
        _, read_only_secret = ApiKey.generate(
            company=self.company, name='Read only', scopes=[ApiKey.SCOPE_DATA_READ],
        )
        response = self._post({'whatsapp_account_id': self.account.pk, 'destination_jid': 'x@s.whatsapp.net'}, read_only_secret)
        self.assertEqual(response.status_code, 403)

    def test_unknown_account_returns_404(self):
        response = self._post({'whatsapp_account_id': 999999, 'destination_jid': 'x@s.whatsapp.net'})
        self.assertEqual(response.status_code, 404)

    def test_disabled_outbound_sending_is_blocked(self):
        self.account.outbound_sending_enabled = False
        self.account.save(update_fields=['outbound_sending_enabled'])
        response = self._post({'whatsapp_account_id': self.account.pk, 'destination_jid': 'x@s.whatsapp.net'})
        self.assertEqual(response.status_code, 403)

    def test_happy_path_delegates_to_message_service_with_actor_label(self):
        fake_message = MagicMock(pk=1)
        with patch('apps.whatsapp_bridge.outbound.message_service.create_outbound_message') as mock_create:
            mock_create.return_value = (fake_message, True)
            with patch(
                'apps.apiconsumer.external_views.OutboundMessageSerializer',
                return_value=MagicMock(data={'id': 1}),
            ):
                response = self._post({
                    'whatsapp_account_id': self.account.pk,
                    'destination_jid': 'x@s.whatsapp.net',
                    'text': 'hello',
                })
        self.assertEqual(response.status_code, 201)
        _, kwargs = mock_create.call_args
        self.assertEqual(kwargs['actor_label'], f'apikey:{self.api_key.key_prefix}')
        self.assertIsNone(kwargs['requested_by'])


class WebhookDeliveryTaskTests(TestCase):
    def setUp(self):
        self.company = _make_company()
        self.subscription = WebhookSubscription.objects.create(
            company=self.company, target_url='https://example.test/hook',
            event_types=[WebhookSubscription.EVENT_OUTBOUND_STATUS_CHANGED],
        )

    def test_successful_delivery_is_signed_and_recorded(self):
        from apps.queue_management.services import enqueue_task
        from apps.task_management.models import BackgroundTask

        task = enqueue_task(
            task_key='apiconsumer.deliver_webhook',
            payload={
                'version': 1, 'subscription_id': self.subscription.pk,
                'event_type': WebhookSubscription.EVENT_OUTBOUND_STATUS_CHANGED,
                'event_payload': {'status': 'delivered'},
            },
            queue_name='apiconsumer_webhooks',
            idempotency_key=f'webhook:{self.subscription.pk}:test',
            company=self.company,
        )

        class _Context:
            task_id = task.pk
            worker_id = 'test-worker'
            correlation_id = 'test-correlation'

        with patch('apps.apiconsumer.task_handlers.requests.post') as mock_post:
            mock_post.return_value = MagicMock(status_code=200, text='ok')
            deliver_webhook(task.payload, _Context())

        attempt = WebhookDeliveryAttempt.objects.get(subscription=self.subscription)
        self.assertTrue(attempt.succeeded)
        self.assertEqual(attempt.response_status, 200)
        _, call_kwargs = mock_post.call_args
        self.assertIn('X-ChatLens-Signature', call_kwargs['headers'])

    def test_inactive_subscription_is_skipped_without_delivery(self):
        self.subscription.is_active = False
        self.subscription.save(update_fields=['is_active'])

        class _Context:
            task_id = 0
            worker_id = 'test-worker'
            correlation_id = 'test-correlation'

        with patch('apps.apiconsumer.task_handlers.requests.post') as mock_post:
            result = deliver_webhook({
                'version': 1, 'subscription_id': self.subscription.pk,
                'event_type': WebhookSubscription.EVENT_OUTBOUND_STATUS_CHANGED,
                'event_payload': {},
            }, _Context())

        mock_post.assert_not_called()
        self.assertEqual(result, {'skipped': 'subscription_inactive_or_missing'})


@override_settings(APICONSUMER_DEFAULT_RATE='2/min')
class ApiKeyRateThrottleTests(TestCase):
    def setUp(self):
        self.company = _make_company()
        self.api_key, self.secret = ApiKey.generate(
            company=self.company, name='Throttle key', scopes=[ApiKey.SCOPE_DATA_READ],
        )
        self.client = APIClient()
        self.url = reverse('external-contact-list')

    def test_exceeding_rate_returns_429(self):
        for _ in range(2):
            response = self.client.get(self.url, HTTP_AUTHORIZATION=f'Api-Key {self.secret}')
            self.assertEqual(response.status_code, 200)
        response = self.client.get(self.url, HTTP_AUTHORIZATION=f'Api-Key {self.secret}')
        self.assertEqual(response.status_code, 429)
