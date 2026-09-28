from django.db.models import F
from django.utils import timezone

from .inquiry_forwarding_formatter import build_forwarding_message
from .inquiry_forwarding_policy import ineligible_reason, source_destination_reason


def enqueue_inquiry_forwarding(inquiry_ids, source_message_id):
    """Enqueue only inquiry cards that already have deterministic product evidence."""
    from apps.queue_management.services import enqueue_task
    from apps.trading.models import Inquiry, InquiryForwardingRule

    inquiries = Inquiry.objects.filter(
        pk__in=inquiry_ids, products__isnull=False,
    ).exclude(products=[]).select_related('company')
    tasks = []
    for inquiry in inquiries:
        rule = InquiryForwardingRule.objects.filter(
            company=inquiry.company, inquiry_type=inquiry.inquiry_type, is_active=True,
        ).first()
        if not rule:
            continue
        tasks.append(enqueue_task(
            task_key='trading.forward_inquiry',
            payload={
                'version': 1,
                'inquiry_id': inquiry.pk,
                'source_message_id': source_message_id,
            },
            queue_name='automation',
            idempotency_key=f'inquiry-forwarding:{rule.pk}:{inquiry.pk}',
            correlation_id=f'inquiry:{inquiry.pk}',
            company=inquiry.company,
            created_by=rule.created_by,
        ))
    return tasks


def process_inquiry_forwarding(inquiry_id, source_message_id):
    from apps.trading.models import Inquiry, InquiryForwardingRule, InquiryForwardingRun

    inquiry = Inquiry.objects.select_related('company', 'contact').get(pk=inquiry_id)
    rule = InquiryForwardingRule.objects.prefetch_related(
        'targets__contact__account', 'targets__group__account',
        'exclusions__contact', 'exclusions__group',
    ).filter(
        company=inquiry.company, inquiry_type=inquiry.inquiry_type, is_active=True,
    ).first()
    if not rule:
        return {'forwarded': 0, 'skipped': True, 'reason': 'rule_inactive_or_missing'}

    source = _source_message(inquiry, source_message_id)
    run, created = InquiryForwardingRun.objects.get_or_create(
        rule=rule, inquiry=inquiry,
        defaults={'source_message': source},
    )
    if not created and run.finished_at:
        return _run_result(run)

    reason = ineligible_reason(rule, inquiry, source)
    if reason:
        return _finish_skipped(rule, run, reason)

    message = build_forwarding_message(rule, inquiry, source)
    if not message:
        return _finish_skipped(rule, run, 'message_content_unavailable')

    targets = list(rule.targets.all())
    run.message_snapshot = message
    run.destination_count = len(targets)
    run.save(update_fields=['message_snapshot', 'destination_count'])
    if not targets:
        return _finish_skipped(rule, run, 'no_destinations')

    queued = blocked = 0
    for target in targets:
        outcome = _send_target(rule, run, target, source, message)
        queued += outcome == 'queued'
        blocked += outcome != 'queued'

    run.queued_count = queued
    run.blocked_count = blocked
    run.status = (
        InquiryForwardingRun.STATUS_COMPLETE if queued and not blocked
        else InquiryForwardingRun.STATUS_PARTIAL if queued
        else InquiryForwardingRun.STATUS_FAILED
    )
    run.reason = '' if queued else 'all_destinations_blocked'
    run.finished_at = timezone.now()
    run.save(update_fields=['queued_count', 'blocked_count', 'status', 'reason', 'finished_at'])
    InquiryForwardingRule.objects.filter(pk=rule.pk).update(
        last_triggered_at=timezone.now(), forwarded_count=F('forwarded_count') + queued,
    )
    return _run_result(run)


def _source_message(inquiry, source_message_id):
    link = inquiry.inquiry_messages.select_related(
        'message__classification', 'message__chat', 'message__contact',
    ).filter(message_id=source_message_id).first()
    return link.message if link else None


def _send_target(rule, run, target, source, message):
    from apps.trading.models import InquiryForwardingDelivery
    from apps.whatsapp_bridge.outbound.message_service import create_outbound_message

    contact = target.contact
    group = target.group
    account = contact.account if contact else group.account
    jid = contact.wa_contact_id if contact else group.wa_group_id
    label = str(contact or group)
    source_reason = source_destination_reason(target, source)
    if source_reason:
        InquiryForwardingDelivery.objects.update_or_create(
            run=run, target=target,
            defaults={
                'outbound_message': None, 'status': 'skipped',
                'reason': source_reason, 'destination_label': label,
            },
        )
        return 'skipped'
    try:
        outbound, _ = create_outbound_message(
            account=account, destination_jid=jid, text=message,
            requested_by=rule.created_by,
            idempotency_key=f'inquiry-forward:{run.pk}:{target.pk}',
        )
        status = 'queued' if outbound.status == outbound.STATUS_QUEUED else 'blocked'
        reason = outbound.status_reason
    except (ValueError, RuntimeError) as exc:
        outbound, status, reason = None, 'blocked', str(exc)
    InquiryForwardingDelivery.objects.update_or_create(
        run=run, target=target,
        defaults={
            'outbound_message': outbound, 'status': status,
            'reason': reason, 'destination_label': label,
        },
    )
    return status


def _finish_skipped(rule, run, reason):
    from apps.trading.models import InquiryForwardingRule, InquiryForwardingRun

    run.status = InquiryForwardingRun.STATUS_SKIPPED
    run.reason = reason
    run.finished_at = timezone.now()
    run.save(update_fields=['status', 'reason', 'finished_at'])
    InquiryForwardingRule.objects.filter(pk=rule.pk).update(skipped_count=F('skipped_count') + 1)
    return _run_result(run)


def _run_result(run):
    return {
        'run_id': run.pk, 'status': run.status, 'reason': run.reason,
        'forwarded': run.queued_count, 'blocked': run.blocked_count,
    }
