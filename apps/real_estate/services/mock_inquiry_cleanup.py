from django.db import transaction
from django.db.models import Q

from apps.real_estate.models import (
    RealEstateAgentCallLog, RealEstateMockInquiry, RealEstateMockInquiryRun,
    RealEstateMockSourceRecord, RealEstateOpportunity, RealEstateParseLog,
)
from apps.task_management.models import BackgroundTask
from apps.whatsapp_bridge.models import WhatsAppMessage

from .mock_inquiry_account import get_mock_account


def reconcile_mock_inquiries(company):
    items = list(RealEstateMockInquiry.objects.filter(
        company=company, message__isnull=True,
    ).select_related('live_task'))
    account = get_mock_account(company)
    if account and items:
        messages = {
            row.provider_message_id: row for row in WhatsAppMessage.objects.filter(
                account=account,
                provider_message_id__in=[item.provider_message_id for item in items],
            )
        }
        for item in items:
            message = messages.get(item.provider_message_id)
            if message:
                item.message = message
                item.status = item.STATUS_INGESTED
                item.save(update_fields=['message', 'status', 'updated_at'])
            elif item.live_task and item.live_task.status in {
                BackgroundTask.STATUS_FAILED, BackgroundTask.STATUS_CANCELLED,
            }:
                item.status = item.STATUS_FAILED
                item.error = item.live_task.last_error
                item.save(update_fields=['status', 'error', 'updated_at'])


def _related_tasks(company, account_id, message_ids, run_task_ids, live_task_ids):
    correlations = [f'whatsapp-message:{message_id}' for message_id in message_ids]
    return BackgroundTask.objects.filter(company=company).filter(
        Q(pk__in=[*run_task_ids, *live_task_ids])
        | Q(payload__account_id=account_id)
        | Q(payload__message_id__in=message_ids)
        | Q(correlation_id__in=correlations)
    ).distinct()


@transaction.atomic
def clear_mock_inquiries(company):
    reconcile_mock_inquiries(company)
    runs = RealEstateMockInquiryRun.objects.select_for_update().filter(company=company)
    if runs.filter(status__in=[
        RealEstateMockInquiryRun.STATUS_PENDING, RealEstateMockInquiryRun.STATUS_RUNNING,
    ]).exists():
        raise RuntimeError('Wait for the active mock inquiry run to finish before clearing data.')
    account = get_mock_account(company)
    items = RealEstateMockInquiry.objects.filter(company=company)
    source_ids = list(items.exclude(source_record_id=None).values_list('source_record_id', flat=True))
    message_ids = list(items.exclude(message_id=None).values_list('message_id', flat=True))
    live_task_ids = list(items.exclude(live_task_id=None).values_list('live_task_id', flat=True))
    run_task_ids = list(runs.exclude(task_id=None).values_list('task_id', flat=True))
    tasks = _related_tasks(company, account.pk if account else 0, message_ids, run_task_ids, live_task_ids)
    if tasks.filter(status__in=BackgroundTask.ACTIVE_STATUSES).exists():
        raise RuntimeError('Wait for mock ingestion and AI tasks to finish before clearing data.')

    RealEstateOpportunity.objects.filter(company=company, source_message_id__in=message_ids).delete()
    RealEstateParseLog.objects.filter(company=company, message_id__in=message_ids).delete()
    RealEstateAgentCallLog.objects.filter(company=company, wa_message_id__in=message_ids).delete()
    message_count = len(message_ids)
    task_count = tasks.count()
    WhatsAppMessage.objects.filter(pk__in=message_ids).delete()
    tasks.delete()
    if account:
        account.chats.all().delete()
        account.contacts.all().delete()
    RealEstateMockSourceRecord.objects.filter(company=company, pk__in=source_ids).update(
        processing_status='pending', processing_notes='',
    )
    inquiry_count = items.count()
    run_count = runs.count()
    items.delete()
    runs.delete()
    return {
        'runs_deleted': run_count, 'inquiries_deleted': inquiry_count,
        'source_rows_reset': len(set(source_ids)),
        'messages_deleted': message_count, 'tasks_deleted': task_count,
    }
