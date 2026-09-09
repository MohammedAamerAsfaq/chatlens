from unittest.mock import patch

from django.test import TestCase

from apps.queue_management.runtime_settings import get_task_runtime_settings
from apps.queue_management.services import TaskWorker
from apps.task_management.models import BackgroundTask
from apps.task_management.registry import task_registry


class EmbeddingQueueDispatchTests(TestCase):
    def setUp(self):
        self.runtime = get_task_runtime_settings()

    def test_queue_mode_creates_idempotent_message_task(self):
        self.runtime.embedding_mode = 'db_queue'
        self.runtime.save(update_fields=['embedding_mode', 'updated_at'])

        with patch('apps.queue_management.services.enqueue_task') as enqueue:
            from apps.message_intelligence.services.embedding_dispatch import enqueue_embedding
            self.assertTrue(enqueue_embedding('message', 42))

        self.assertEqual(enqueue.call_args.kwargs['task_key'], 'whatsapp.embed_message')
        self.assertEqual(enqueue.call_args.kwargs['payload'], {'version': 1, 'object_id': 42})
        self.assertEqual(enqueue.call_args.kwargs['idempotency_key'], 'embedding:message:42')

    def test_message_lineage_overrides_default_embedding_correlation(self):
        self.runtime.embedding_mode = 'db_queue'
        self.runtime.save(update_fields=['embedding_mode', 'updated_at'])

        with patch('apps.queue_management.services.enqueue_task') as enqueue:
            from apps.message_intelligence.services.embedding_dispatch import enqueue_embedding
            enqueue_embedding('message', 42, correlation_id='whatsapp-message:42')

        self.assertEqual(enqueue.call_args.kwargs['correlation_id'], 'whatsapp-message:42')

    def test_thread_mode_does_not_create_task(self):
        self.runtime.embedding_mode = 'thread'
        self.runtime.save(update_fields=['embedding_mode', 'updated_at'])

        with patch('apps.queue_management.services.enqueue_task') as enqueue:
            from apps.message_intelligence.services.embedding_dispatch import enqueue_embeddings
            self.assertFalse(enqueue_embeddings('product', [1, 2]))

        enqueue.assert_not_called()

    def test_registered_handler_executes_embedding_service(self):
        from apps.message_intelligence import embedding_task_handlers  # noqa: F401

        definition = task_registry.get('embedding.product')
        with patch(
            'apps.message_intelligence.services.embedding_service.embed_product',
            return_value=True,
        ) as embed:
            result = definition.handler({'version': 1, 'object_id': 7}, None)

        embed.assert_called_once_with(7)
        self.assertEqual(result, {'object_id': 7, 'embedded': True})

    def test_embedding_worker_claims_and_completes_queued_task(self):
        self.runtime.embedding_mode = 'db_queue'
        self.runtime.save(update_fields=['embedding_mode', 'updated_at'])
        from apps.message_intelligence.services.embedding_dispatch import enqueue_embedding

        enqueue_embedding('product', 9)
        task = BackgroundTask.objects.get(task_key='embedding.product')
        worker = TaskWorker(['embeddings'], worker_id='embedding-test-worker')
        worker.start()
        try:
            with patch(
                'apps.message_intelligence.services.embedding_service.embed_product',
                return_value=True,
            ):
                worker.run_once()
        finally:
            worker.stop()

        task.refresh_from_db()
        self.assertEqual(task.status, BackgroundTask.STATUS_SUCCEEDED)
        self.assertEqual(task.result['object_id'], 9)
