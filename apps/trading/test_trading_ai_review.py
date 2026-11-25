from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.tenancy.models import Company, CommunicationAccount, ConnectionProvider
from apps.tenancy.testing import create_member
from apps.trading.models import MessageClassification, TradingMessageReview
from apps.whatsapp_bridge.models import WhatsAppAccount, WhatsAppChat, WhatsAppMessage


class TradingReviewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='reviewer')
        self.company = Company.objects.create(name='Review Co', slug='review-co', industry_type=Company.INDUSTRY_TRADING)
        create_member(company=self.company, user=self.user, role='super_user')
        provider = ConnectionProvider.objects.get(key='baileys')
        def message(company, key):
            comm = CommunicationAccount.objects.create(company=company, provider=provider, channel='whatsapp', name=key)
            account = WhatsAppAccount.objects.create(owner=self.user, communication_account=comm, display_name=key, phone_number=key)
            chat = WhatsAppChat.objects.create(account=account, wa_chat_id=key, chat_type='individual')
            msg = WhatsAppMessage.objects.create(account=account, chat=chat, provider_message_id=key, direction='inbound', message_type='text', message_text='Need 2 phones', message_time=timezone.now())
            MessageClassification.objects.create(message=msg, is_inquiry=True, inquiry_type='buy', products=[{'canonical_name': 'phones'}])
            return msg
        self.message = message(self.company, 'one')
        other = Company.objects.create(name='Other Co', slug='other-review-co', industry_type=Company.INDUSTRY_TRADING)
        self.foreign = message(other, 'two')
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_review_records_snapshot_and_excludes_reviewed(self):
        url = '/api/trading-ai-review/'
        result = self.client.get(url + 'next/')
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()['message_id'], self.message.id)
        label = {'is_inquiry': True, 'direction': 'buy', 'products': [{'name': 'phones', 'quantity': '2'}]}
        result = self.client.post(url + 'submit/', {'message_id': self.message.id, 'label': label}, format='json')
        self.assertEqual(result.status_code, 201, result.content)
        review = TradingMessageReview.objects.get()
        self.assertEqual(review.source_text, 'Need 2 phones')
        self.assertEqual(review.reviewed_by, self.user)
        self.assertEqual(review.label['products'][0]['quantity'], '2')
        self.assertEqual(self.client.get(url + 'next/').json(), {'done': True})
        self.assertEqual(self.client.post(url + 'submit/', {'message_id': self.message.id, 'label': label}, format='json').status_code, 409)

    def test_cannot_submit_foreign_message_or_inconsistent_label(self):
        url = '/api/trading-ai-review/submit/'
        label = {'is_inquiry': False, 'direction': '', 'products': []}
        self.assertEqual(self.client.post(url, {'message_id': self.foreign.id, 'label': label}, format='json').status_code, 404)
        label['direction'] = 'buy'
        self.assertEqual(self.client.post(url, {'message_id': self.message.id, 'label': label}, format='json').status_code, 400)
        self.assertFalse(TradingMessageReview.objects.exists())

    def test_pool_and_skip_select_expected_messages(self):
        url = '/api/trading-ai-review/next/'
        self.assertEqual(self.client.get(url, {'pool': 'sell'}).json(), {'done': True})
        self.assertEqual(self.client.get(url, {'pool': 'buy'}).json()['message_id'], self.message.pk)
        self.assertEqual(self.client.get(url, {'pool': 'buy', 'after': self.message.pk}).json(), {'done': True})
        self.assertEqual(self.client.get(url, {'after': 'bad'}).status_code, 400)

    def test_export_excludes_ai_from_human_and_evaluation(self):
        import io
        import json
        from django.core.management import call_command
        label = {'is_inquiry': False, 'direction': '', 'products': [], 'notes': 'AI review by OpenAI Codex; not human-verified.'}
        review = TradingMessageReview.objects.create(company=self.company, message=self.message, source_text=self.message.message_text, ai_snapshot={}, label=label)
        output = io.StringIO()
        call_command('export_trading_reviews', company_id=self.company.pk, stdout=output)
        self.assertEqual(output.getvalue(), '')
        output = io.StringIO()
        call_command('export_trading_reviews', company_id=self.company.pk, origin='ai', stdout=output)
        row = json.loads(output.getvalue())
        self.assertEqual(row['review_origin'], 'ai')
        output = io.StringIO()
        call_command('export_trading_reviews', company_id=self.company.pk, origin='all', split=row['split'] if row['split'] != 'train' else 'test', stdout=output)
        self.assertEqual(output.getvalue(), '')
    def test_batch_progress_and_human_correction_keep_ai_history(self):
        from apps.trading.models import TradingReviewBatch, TradingReviewBatchItem, TradingReviewRevision
        batch = TradingReviewBatch.objects.create(company=self.company, name='Batch 1')
        TradingReviewBatchItem.objects.create(batch=batch, message=self.message, position=1, group_id='a' * 64, sampling_pool='buy')
        response = self.client.get('/api/trading-ai-review/batch-next/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual((response.json()['completed'], response.json()['total']), (0, 1))
        ai_label = {'is_inquiry': True, 'direction': 'sell', 'products': [], 'notes': 'AI review by OpenAI Codex; not human-verified.'}
        review = TradingMessageReview.objects.create(company=self.company, message=self.message, source_text=self.message.message_text, ai_snapshot={}, label=ai_label)
        self.assertEqual(self.client.get('/api/trading-ai-review/batch-next/').json()['completed'], 1)
        self.assertEqual(self.client.get('/api/trading-ai-review/review-next/', {'origin': 'ai'}).json()['review_id'], review.id)
        label = {'is_inquiry': True, 'direction': 'buy', 'products': [{'name': 'phones', 'quantity': '2'}], 'notes': ''}
        response = self.client.post('/api/trading-ai-review/correct/', {'review_id': review.pk, 'label': label, 'expected_label': ai_label}, format='json')
        self.assertEqual(response.status_code, 200, response.content)
        review.refresh_from_db()
        self.assertEqual(review.reviewed_by, self.user)
        self.assertEqual(review.label['direction'], 'buy')
        self.assertEqual(TradingReviewRevision.objects.get(review=review).previous_label, ai_label)
        self.assertTrue(self.client.get('/api/trading-ai-review/review-next/', {'origin': 'ai'}).json()['done'])

    def test_cannot_correct_other_company_review(self):
        review = TradingMessageReview.objects.create(company=self.foreign.account.communication_account.company, message=self.foreign, source_text='other', ai_snapshot={}, label={'is_inquiry': False})
        response = self.client.post('/api/trading-ai-review/correct/', {'review_id': review.pk, 'label': {'is_inquiry': False, 'direction': '', 'products': []}}, format='json')
        self.assertEqual(response.status_code, 404)
    def test_batch_import_is_company_scoped_and_atomic(self):
        import json
        import tempfile
        from pathlib import Path
        from django.core.management import call_command, CommandError
        from apps.trading.models import TradingReviewBatch
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'batch.jsonl'
            entries = [{'message_id': self.message.id, 'group_id': 'a' * 64, 'sampling_pool': 'buy', 'duplicate_message_ids': []},
                       {'message_id': self.foreign.id, 'group_id': 'b' * 64, 'sampling_pool': 'buy', 'duplicate_message_ids': []}]
            path.write_text(''.join(json.dumps(row) + '\n' for row in entries), encoding='utf-8')
            with self.assertRaises(CommandError):
                call_command('import_trading_review_batch', company_id=self.company.id, name='Bad batch', file=str(path))
            self.assertFalse(TradingReviewBatch.objects.exists())
            path.write_text(json.dumps(entries[0]) + '\n', encoding='utf-8')
            call_command('import_trading_review_batch', company_id=self.company.id, name='Good batch', file=str(path))
            self.assertEqual(TradingReviewBatch.objects.get().items.count(), 1)
    def test_evaluation_queue_only_returns_held_out_ai_reviews(self):
        from unittest.mock import patch
        label = {'is_inquiry': False, 'direction': '', 'products': [], 'notes': 'AI review by OpenAI Codex; not human-verified.'}
        review = TradingMessageReview.objects.create(company=self.company, message=self.message, source_text='source', ai_snapshot={}, label=label)
        with patch('apps.trading.management.commands.export_trading_reviews.group_split', return_value='train'):
            self.assertTrue(self.client.get('/api/trading-ai-review/review-next/', {'origin': 'ai', 'sample': 'evaluation'}).json()['done'])
        with patch('apps.trading.management.commands.export_trading_reviews.group_split', return_value='test'):
            self.assertEqual(self.client.get('/api/trading-ai-review/review-next/', {'origin': 'ai', 'sample': 'evaluation'}).json()['review_id'], review.id)
        self.assertEqual(self.client.get('/api/trading-ai-review/review-next/', {'origin': 'human', 'sample': 'evaluation'}).status_code, 400)
    def test_long_stock_list_can_be_reviewed_and_corrected(self):
        products = [{'name': f'Product {index}', 'quantity': '1'} for index in range(146)]
        label = {'is_inquiry': True, 'direction': 'sell', 'products': products}
        response = self.client.post('/api/trading-ai-review/submit/', {'message_id': self.message.id, 'label': label}, format='json')
        self.assertEqual(response.status_code, 201, response.content)
        review = TradingMessageReview.objects.get(message=self.message)
        self.assertEqual(len(review.label['products']), 146)
        updated = {**label, 'products': products + [{'name': 'Another product'}]}
        response = self.client.post('/api/trading-ai-review/correct/', {'review_id': review.id, 'expected_label': review.label, 'label': updated}, format='json')
        self.assertEqual(response.status_code, 200, response.content)
        review.refresh_from_db()
        self.assertEqual(len(review.label['products']), 147)

    def test_excessive_product_list_is_rejected(self):
        products = [{'name': 'Product'}] * 1001
        label = {'is_inquiry': True, 'direction': 'sell', 'products': products}
        response = self.client.post('/api/trading-ai-review/submit/', {'message_id': self.message.id, 'label': label}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(TradingMessageReview.objects.filter(message=self.message).exists())
    def test_mlx_dataset_excludes_held_out_and_notes(self):
        import io
        import json
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from django.core.management import call_command
        label = {'is_inquiry': True, 'direction': 'buy', 'products': [{'name': 'Phone', 'quantity': '2'}], 'notes': 'private reviewer note'}
        TradingMessageReview.objects.create(company=self.company, message=self.message, source_text=self.message.message_text, ai_snapshot={}, label=label, reviewed_by=self.user)
        with tempfile.TemporaryDirectory() as directory:
            with patch('apps.trading.management.commands.prepare_trading_mlx_dataset.group_split', return_value='train'):
                call_command('prepare_trading_mlx_dataset', company_id=self.company.pk, output_dir=directory, stdout=io.StringIO())
            row = json.loads((Path(directory) / 'candidates.jsonl').read_text(encoding='utf-8'))
            answer = json.loads(row['messages'][-1]['content'])
            self.assertEqual(answer['products'][0]['name'], 'Phone')
            self.assertNotIn('notes', answer)
            self.assertEqual(row['messages'][1]['content'], self.message.message_text)
            provenance = json.loads((Path(directory) / 'provenance.jsonl').read_text(encoding='utf-8'))
            self.assertEqual(provenance['origin'], 'human')
            self.assertEqual(provenance['message_id'], self.message.id)

    def test_mlx_dataset_refuses_held_out_only_and_existing_output(self):
        import tempfile
        from unittest.mock import patch
        from django.core.management import call_command, CommandError
        label = {'is_inquiry': False, 'direction': '', 'products': []}
        TradingMessageReview.objects.create(company=self.company, message=self.message, source_text='test', ai_snapshot={}, label=label, reviewed_by=self.user)
        with tempfile.TemporaryDirectory() as directory:
            with patch('apps.trading.management.commands.prepare_trading_mlx_dataset.group_split', return_value='test'):
                with self.assertRaises(CommandError):
                    call_command('prepare_trading_mlx_dataset', company_id=self.company.pk, output_dir=directory)
