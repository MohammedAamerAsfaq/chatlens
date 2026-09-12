from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase

from apps.queue_management.runtime_settings import get_task_runtime_settings
from apps.task_management.registry import task_registry


class ClassificationQueueTests(TestCase):
    def setUp(self):
        self.runtime = get_task_runtime_settings()
        self.runtime.classification_mode = 'db_queue'
        self.runtime.save(update_fields=['classification_mode', 'updated_at'])

    def test_message_enqueues_current_classification_task(self):
        message = SimpleNamespace(pk=12, account=object())
        with patch(
            'apps.tenancy.services.access.company_for_message', return_value=None,
        ), patch('apps.queue_management.services.enqueue_task') as enqueue:
            from apps.trading.services.classification_dispatch import enqueue_classification
            self.assertTrue(enqueue_classification(message))

        self.assertEqual(enqueue.call_args.kwargs['task_key'], 'trading.classify_message')
        self.assertEqual(enqueue.call_args.kwargs['payload'], {'version': 1, 'message_id': 12})
        self.assertEqual(enqueue.call_args.kwargs['idempotency_key'], 'classification:12')

    def test_handler_runs_current_classifier(self):
        from apps.task_management import handlers  # noqa: F401

        definition = task_registry.get('trading.classify_message')
        payload = {'version': 1, 'message_id': 3}
        message = SimpleNamespace(pk=3)
        with patch('apps.whatsapp_bridge.models.WhatsAppMessage.objects.select_related') as select, patch(
            'apps.trading.services.classification_service.classify_message',
        ) as classify:
            select.return_value.get.return_value = message
            result = definition.handler(payload, None)

        classify.assert_called_once_with(message, propagate_errors=True)
        self.assertEqual(result, {'message_id': 3, 'classified': True})

    def test_handler_propagates_classifier_failure(self):
        from apps.task_management import handlers  # noqa: F401

        definition = task_registry.get('trading.classify_message')
        with patch('apps.whatsapp_bridge.models.WhatsAppMessage.objects.select_related') as select, patch(
            'apps.trading.services.classification_service.classify_message',
            side_effect=RuntimeError('classification failed'),
        ):
            select.return_value.get.return_value = SimpleNamespace(pk=9)
            with self.assertRaisesMessage(RuntimeError, 'classification failed'):
                definition.handler({'version': 1, 'message_id': 9}, None)
