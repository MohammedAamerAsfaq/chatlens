from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.clientpulse.models import ClientActivity, ClientProfile
from apps.clientpulse.services.activity_projection import (
    enqueue_message_projection, project_message_activity,
)
from apps.queue_management.models import BackgroundWorker
from apps.queue_management.services import TaskExecutor, claim_tasks
from apps.task_management.models import BackgroundTask
from apps.tenancy.models import CommunicationAccount, Company, CompanyContact, ConnectionProvider
from apps.whatsapp_bridge.models import (
    ChatType, MessageDirection, MessageType, WhatsAppAccount, WhatsAppChat,
    WhatsAppContact, WhatsAppMessage,
)


class ClientActivityProjectionTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name='Projection Co', slug='projection-co')
        provider, _ = ConnectionProvider.objects.get_or_create(
            key='projection-baileys',
            defaults={'name': 'Projection Baileys', 'channel': 'whatsapp'},
        )
        communication = CommunicationAccount.objects.create(
            company=self.company, provider=provider, channel='whatsapp', name='Projection Account',
        )
        owner = get_user_model().objects.create_user('projection-owner')
        account = WhatsAppAccount.objects.create(owner=owner, communication_account=communication)
        contact = CompanyContact.objects.create(company=self.company, display_name='Projected Client')
        self.profile = ClientProfile.objects.create(company=self.company, contact=contact)
        wa_contact = WhatsAppContact.objects.create(
            account=account, company_contact=contact,
            wa_contact_id='971500001234@s.whatsapp.net',
        )
        chat = WhatsAppChat.objects.create(
            account=account, contact=wa_contact,
            wa_chat_id='971500001234@s.whatsapp.net', chat_type=ChatType.INDIVIDUAL,
        )
        self.message = WhatsAppMessage.objects.create(
            account=account, chat=chat, contact=wa_contact, provider_message_id='projection-1',
            direction=MessageDirection.INBOUND, message_type=MessageType.TEXT,
            message_text='Private customer message body', message_time=timezone.now(),
        )

    def test_durable_projection_is_idempotent_and_does_not_copy_message_body(self):
        first = enqueue_message_projection(self.message)
        second = enqueue_message_projection(self.message)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(BackgroundTask.objects.filter(task_key='clientpulse.project_activity').count(), 1)

        now = timezone.now()
        BackgroundWorker.objects.create(
            worker_id='projection-worker', hostname='test', process_id=1,
            queue_names=['clientpulse'], status=BackgroundWorker.STATUS_RUNNING,
            started_at=now, last_heartbeat_at=now,
        )
        task = claim_tasks('clientpulse', 'projection-worker', limit=1)[0]
        self.assertTrue(TaskExecutor('projection-worker').execute(task.pk))

        activity = ClientActivity.objects.get(source_model='whatsapp_message')
        self.assertEqual(activity.activity_type, 'inbound_message')
        self.assertNotIn(self.message.message_text, activity.summary)
        self.assertNotIn(self.message.message_text, str(activity.metadata))
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.last_inbound_at, self.message.message_time)

    def test_projection_resolves_direct_contact_from_chat(self):
        self.message.contact = None
        self.message.save(update_fields=['contact'])

        task = enqueue_message_projection(self.message)
        result = project_message_activity(self.message.pk, self.company.pk)

        self.assertIsNotNone(task)
        self.assertEqual(result['profile_id'], self.profile.pk)
