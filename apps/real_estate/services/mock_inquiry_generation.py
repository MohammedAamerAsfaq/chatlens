import logging

from django.db import transaction
from django.utils import timezone

from apps.real_estate.models import (
    RealEstateMockInquiry, RealEstateMockInquiryRun, RealEstateMockSourceRecord,
)
from apps.whatsapp_bridge.services.live_ingestion_queue import enqueue_live_message

from .mock_inquiry_account import ensure_mock_account
from .mock_inquiry_profiles import PROFILES, build_mock_message, parse_source_record


logger = logging.getLogger(__name__)


def _payload(account, run, record, data, message):
    provider_id = f're-mock-{run.pk}-{record.pk}'
    jid = f'{data["phone"]}@s.whatsapp.net'
    return provider_id, {
        'worker_session_id': account.pk,
        'provider_message_id': provider_id,
        'transport_key': provider_id,
        'chat_id': jid,
        'chat_type': 'individual',
        'chat_name': data['name'],
        'sender_number': data['phone'],
        'push_name': data['name'],
        'direction': 'inbound',
        'message_type': 'text',
        'message_text': message,
        'message_time': timezone.now().isoformat(),
        'raw_payload': {
            'mock': True, 'mock_run_id': str(run.pk),
            'mock_source_record_id': record.pk,
        },
    }


def generate_mock_inquiries(run_id):
    run = RealEstateMockInquiryRun.objects.select_related('company', 'created_by').get(pk=run_id)
    profile = PROFILES.get(run.source_file_name)
    if not profile or profile.activity_type != run.activity_type:
        raise ValueError('The selected source dataset is not supported for mock generation.')
    existing = run.inquiries.all()
    run.generated_count = existing.exclude(status=RealEstateMockInquiry.STATUS_FAILED).count()
    run.failed_count = existing.filter(status=RealEstateMockInquiry.STATUS_FAILED).count()
    run.status = run.STATUS_RUNNING
    run.started_at = timezone.now()
    run.error = ''
    run.save(update_fields=[
        'status', 'started_at', 'error', 'generated_count', 'failed_count', 'updated_at',
    ])
    try:
        account = ensure_mock_account(run.company, run.created_by)
        run.mock_account = account
        run.save(update_fields=['mock_account', 'updated_at'])
        remaining = max(0, run.requested_count - run.generated_count)
        records = RealEstateMockSourceRecord.objects.filter(
            company=run.company, source_file_name=run.source_file_name,
            row_kind='data', processing_status='pending',
        ).order_by('source_sheet_index', 'source_row_number')
        for record in records.iterator(chunk_size=200):
            if remaining <= 0:
                break
            data = parse_source_record(record, profile)
            if not data:
                continue
            message = build_mock_message(profile, data)
            provider_id, payload = _payload(account, run, record, data, message)
            try:
                live_task, _ = enqueue_live_message(account, payload)
                with transaction.atomic():
                    RealEstateMockInquiry.objects.create(
                        company=run.company, run=run, source_record=record,
                        activity_type=run.activity_type, contact_name=data['name'],
                        contact_number=data['phone'], generated_message=message,
                        provider_message_id=provider_id, live_task=live_task,
                    )
                    record.processing_status = 'processed'
                    record.processing_notes = f'Mocked by inquiry run {run.pk}.'
                    record.save(update_fields=['processing_status', 'processing_notes'])
                run.generated_count += 1
                remaining -= 1
            except Exception as exc:
                run.failed_count += 1
                logger.exception('Mock inquiry dispatch failed for source row %s', record.pk)
                error = str(exc)[:1000]
                with transaction.atomic():
                    RealEstateMockInquiry.objects.update_or_create(
                        provider_message_id=provider_id,
                        defaults={
                            'company': run.company, 'run': run, 'source_record': record,
                            'activity_type': run.activity_type, 'contact_name': data['name'],
                            'contact_number': data['phone'], 'generated_message': message,
                            'status': RealEstateMockInquiry.STATUS_FAILED, 'error': error,
                        },
                    )
                    record.processing_status = 'failed'
                    record.processing_notes = error
                    record.save(update_fields=['processing_status', 'processing_notes'])
        run.status = run.STATUS_COMPLETE
        run.finished_at = timezone.now()
        if run.generated_count < run.requested_count:
            run.error = (
                f'Generated {run.generated_count} of {run.requested_count}; '
                'remaining pending rows did not contain a usable contact and property context.'
            )
        run.save(update_fields=[
            'status', 'generated_count', 'failed_count', 'error', 'finished_at', 'updated_at',
        ])
        return {
            'run_id': str(run.pk), 'generated': run.generated_count,
            'failed': run.failed_count, 'mock_account_id': account.pk,
        }
    except Exception as exc:
        run.status = run.STATUS_FAILED
        run.error = str(exc)
        run.finished_at = timezone.now()
        run.save(update_fields=['status', 'error', 'finished_at', 'updated_at'])
        raise
