"""
Cross-table message lifecycle trace.

Every log/audit source in the ingestion pipeline can carry the WhatsApp
provider message id (Baileys' own message key `id`) in one form or another —
this joins all of them into a single ordered timeline for one (account,
provider_message_id) pair. Read-only: builds a report, writes nothing.

Sources joined, in the order they're queried below (the final timeline is
sorted by timestamp, not by this order):
  - BaileysEvent      — worker-side per-stage audit (received/filtered/forwarded/failed/history)
  - WhatsAppMessage   — the successfully ingested row, if any
  - SyncLog           — the message_ingest event (metadata carries provider_message_id)
  - DroppedMessage    — msg_id is the same raw provider id
  - WhatsAppUnresolvedMessage — preserved pending LID resolution
  - StuckReceipt      — message_id is the same id, for WhatsApp's retry-receipt protocol
  - WorkerAlert       — best-effort only; context is free-form JSON with no dedicated
                         provider_message_id column, so this is a text search over the
                         raw JSON, not a structured match. May miss alerts whose context
                         shape doesn't happen to include this id.
  - AiParsingLog / MessageEmbedding / MessageClassification / InquiryMessage — the
    downstream Django-side pipeline, only reachable once a WhatsAppMessage row exists.

An empty timeline is a real, meaningful result: it means nothing in this system
ever recorded this id, at any stage — see docs/Silent Message Drop Investigation.md
for the one confirmed failure mode this can't explain (a message that never reached
this linked device at all, so nothing here ever had anything to log).
"""
from django.db.models import TextField, Min, Max, Count
from django.db.models.functions import Cast

from apps.whatsapp_bridge.models import (
    WhatsAppAccount, WhatsAppMessage, SyncLog, DroppedMessage,
    WhatsAppUnresolvedMessage, StuckReceipt, WorkerAlert, BaileysEvent,
)


def list_traced_messages(user, account_id=None, search: str = '', page: int = 1, page_size: int = 25) -> dict:
    """
    Browsable list of every distinct (account, provider_message_id) BaileysEvent
    has ever recorded — BaileysEvent is used as the index here because it's the
    widest-reaching source (the worker writes to it at every stage, success or
    failure), so it's the best available proxy for "every message this system
    has ever touched". Each row gets a quick outcome guess from bulk existence
    checks against the other tables (no per-row full trace_message() join —
    that's reserved for the expand/detail action so the list stays cheap).

    account_id=None lists across every account visible to the requesting user,
    same default-to-all-visible-accounts convention every other Logs list uses.
    """
    from apps.tenancy.services.access import scope_queryset_to_visible_accounts

    qs = scope_queryset_to_visible_accounts(
        BaileysEvent.objects.exclude(provider_message_id=''),
        user,
    )
    if account_id:
        qs = qs.filter(account_id=account_id)
    if search:
        qs = qs.filter(provider_message_id__icontains=search)

    grouped = (
        qs.values('account_id', 'provider_message_id')
        .annotate(first_seen=Min('created_at'), last_seen=Max('created_at'), event_count=Count('id'))
        .order_by('-last_seen')
    )

    total = grouped.count()
    start = (page - 1) * page_size
    page_rows = list(grouped[start:start + page_size])

    account_ids = {r['account_id'] for r in page_rows}
    pids = {r['provider_message_id'] for r in page_rows}
    keys = {(r['account_id'], r['provider_message_id']) for r in page_rows}

    latest_events = {
        (e.account_id, e.provider_message_id): e
        for e in BaileysEvent.objects.filter(
            account_id__in=account_ids, provider_message_id__in=pids,
        ).order_by('account_id', 'provider_message_id', '-created_at')
        .distinct('account_id', 'provider_message_id')
        if (e.account_id, e.provider_message_id) in keys
    }

    from apps.trading.models import InquiryMessage

    delivered = set(
        WhatsAppMessage.objects.filter(account_id__in=account_ids, provider_message_id__in=pids)
        .values_list('account_id', 'provider_message_id')
    )
    dropped = set(
        DroppedMessage.objects.filter(account_id__in=account_ids, msg_id__in=pids)
        .values_list('account_id', 'msg_id')
    )
    unresolved = set(
        WhatsAppUnresolvedMessage.objects.filter(account_id__in=account_ids, provider_message_id__in=pids)
        .values_list('account_id', 'provider_message_id')
    )
    inquiry_linked = set(
        InquiryMessage.objects.filter(
            message__account_id__in=account_ids, message__provider_message_id__in=pids,
        ).values_list('message__account_id', 'message__provider_message_id')
    )
    account_names = dict(
        WhatsAppAccount.objects.filter(pk__in=account_ids).values_list('pk', 'display_name')
    )

    def outcome_for(key):
        if key in inquiry_linked:
            return 'delivered_and_linked_to_inquiry'
        if key in delivered:
            return 'delivered'
        if key in unresolved:
            return 'unresolved'
        if key in dropped:
            return 'dropped'
        return 'no_final_record'

    results = []
    for r in page_rows:
        key = (r['account_id'], r['provider_message_id'])
        latest = latest_events.get(key)
        results.append({
            'account_id': r['account_id'],
            'account_name': account_names.get(r['account_id']) or f'Account #{r["account_id"]}',
            'provider_message_id': r['provider_message_id'],
            'first_seen': r['first_seen'],
            'last_seen': r['last_seen'],
            'event_count': r['event_count'],
            'sender_number': latest.sender_number if latest else '',
            'push_name': latest.push_name if latest else '',
            'direction': latest.direction if latest else '',
            'message_type': latest.message_type if latest else '',
            'outcome': outcome_for(key),
        })

    return {'count': total, 'results': results}


def trace_message(account, provider_message_id: str) -> dict:
    events = []

    for e in BaileysEvent.objects.filter(
        account=account, provider_message_id=provider_message_id,
    ).order_by('created_at'):
        events.append({
            'timestamp': e.created_at,
            'source': 'baileys_event',
            'stage': e.event_stage,
            'status': e.status,
            'detail': e.reason or e.error_message or e.event_type,
            'meta': {
                'event_type': e.event_type,
                'direction': e.direction,
                'message_type': e.message_type,
                'sender_number': e.sender_number,
                'push_name': e.push_name,
                'upsert_type': e.upsert_type,
            },
        })

    message = WhatsAppMessage.objects.filter(
        account=account, provider_message_id=provider_message_id,
    ).select_related('chat', 'contact').first()
    if message:
        events.append({
            'timestamp': message.created_at,
            'source': 'whatsapp_message',
            'stage': 'ingested',
            'status': 'success',
            'detail': f'{message.direction} {message.message_type} message ingested',
            'meta': {
                'message_id': message.pk,
                'chat_id': message.chat_id,
                'message_time': message.message_time,
                'message_text': (message.message_text or '')[:200],
            },
        })

    for log in SyncLog.objects.filter(
        account=account, event_type='message_ingest',
        metadata__provider_message_id=provider_message_id,
    ).order_by('created_at'):
        events.append({
            'timestamp': log.created_at,
            'source': 'sync_log',
            'stage': 'message_ingest',
            'status': log.status,
            'detail': log.message or 'ingest logged',
            'meta': log.metadata,
        })

    for d in DroppedMessage.objects.filter(
        account=account, msg_id=provider_message_id,
    ).order_by('created_at'):
        events.append({
            'timestamp': d.created_at,
            'source': 'dropped_message',
            'stage': 'dropped',
            'status': 'self_healed' if d.resolved_at else 'dropped',
            'detail': f'dropped: {d.reason}' + (' (a later resend was ingested)' if d.resolved_at else ''),
            'meta': {'reason': d.reason, 'resolved_at': d.resolved_at},
        })

    for u in WhatsAppUnresolvedMessage.objects.filter(
        account=account, provider_message_id=provider_message_id,
    ).order_by('created_at'):
        events.append({
            'timestamp': u.created_at,
            'source': 'unresolved_message',
            'stage': 'unresolved',
            'status': u.resolution_status,
            'detail': f'preserved unresolved (lid={u.lid_jid or "unknown"})',
            'meta': {
                'lid_jid': u.lid_jid,
                'resolution_status': u.resolution_status,
                'resolution_error': u.resolution_error,
                'resolved_at': u.resolved_at,
            },
        })

    for s in StuckReceipt.objects.filter(
        account=account, message_id=provider_message_id,
    ).order_by('first_seen_at'):
        events.append({
            'timestamp': s.first_seen_at,
            'source': 'stuck_receipt',
            'stage': 'stuck_receipt',
            'status': 'resolved' if s.resolved_at else 'unresolved',
            'detail': f'WhatsApp retry-request stuck, seen {s.occurrence_count}x',
            'meta': {'occurrence_count': s.occurrence_count, 'last_seen_at': s.last_seen_at},
        })

    alert_qs = (
        WorkerAlert.objects
        .filter(account=account, context__isnull=False)
        .annotate(context_text=Cast('context', output_field=TextField()))
        .filter(context_text__icontains=provider_message_id)
        .order_by('created_at')
    )
    for a in alert_qs:
        events.append({
            'timestamp': a.created_at,
            'source': 'worker_alert',
            'stage': 'worker_alert',
            'status': a.severity,
            'detail': f'{a.alert_type}: {a.message}',
            'meta': {'alert_type': a.alert_type, 'acknowledged': a.acknowledged_at is not None},
        })

    if message:
        from apps.trading.models import AiParsingLog, MessageClassification, InquiryMessage
        from apps.message_intelligence.models import MessageEmbedding

        parsing_log = AiParsingLog.objects.filter(message=message).first()
        if parsing_log:
            events.append({
                'timestamp': parsing_log.created_at,
                'source': 'ai_parsing_log',
                'stage': 'ai_parsing',
                'status': parsing_log.status,
                'detail': (
                    f'AI parsing: {parsing_log.status}'
                    + (f' ({parsing_log.skip_reason})' if parsing_log.skip_reason else '')
                ),
                'meta': {'skip_reason': parsing_log.skip_reason},
            })

        if MessageEmbedding.objects.filter(message=message).exists():
            events.append({
                'timestamp': message.message_time,
                'source': 'message_embedding',
                'stage': 'embedded',
                'status': 'success',
                'detail': 'embedding stored',
                'meta': {},
            })

        classification = MessageClassification.objects.filter(message=message).first()
        if classification:
            events.append({
                'timestamp': classification.classified_at,
                'source': 'message_classification',
                'stage': 'classified',
                'status': 'success',
                'detail': f'tags={classification.tags}, is_inquiry={classification.is_inquiry}',
                'meta': {
                    'tags': classification.tags,
                    'is_inquiry': classification.is_inquiry,
                    'inquiry_type': classification.inquiry_type,
                    'summary': classification.ai_summary,
                },
            })

        inquiry_link = InquiryMessage.objects.filter(message=message).select_related('inquiry').first()
        if inquiry_link:
            inquiry = inquiry_link.inquiry
            events.append({
                'timestamp': inquiry_link.added_at,
                'source': 'inquiry',
                'stage': 'linked_to_inquiry',
                'status': inquiry.status,
                'detail': f'linked to Inquiry #{inquiry.pk} ({inquiry.inquiry_type}, status={inquiry.status})',
                'meta': {'inquiry_id': inquiry.pk, 'inquiry_status': inquiry.status},
            })

    events.sort(key=lambda e: e['timestamp'])

    return {
        'account_id': account.pk,
        'provider_message_id': provider_message_id,
        'found': bool(events),
        'outcome': _derive_outcome(events, message),
        'timeline': events,
    }


def _derive_outcome(events: list, message) -> str:
    if not events:
        return 'no_trace_found'
    if any(e['source'] == 'inquiry' for e in events):
        return 'delivered_and_linked_to_inquiry'
    if message:
        return 'delivered'
    unresolved = [e for e in events if e['source'] == 'unresolved_message']
    if unresolved:
        return f'unresolved_{unresolved[-1]["status"]}'
    dropped = [e for e in events if e['source'] == 'dropped_message']
    if dropped:
        return dropped[-1]['status']  # 'dropped' or 'self_healed'
    return 'partial_trace_no_final_outcome'
