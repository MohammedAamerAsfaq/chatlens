"""The only place Inquiry.status changes, so every change lands in InquiryStatusEvent.

Owners, admins and anyone else who can see an inquiry's account set its one status here.
(Recipients of a shared inquiry keep their own status in inquiry_sharing instead.)
"""

from django.db import transaction
from django.utils.timezone import now

from apps.tenancy.models import CommunicationAccountAssignment
from apps.trading.models import Inquiry, InquiryStatus, InquiryStatusEvent

CLOSING_STATUSES = (InquiryStatus.CLOSED, InquiryStatus.DEAL_DONE)


class InquiryStatusError(ValueError):
    """An invalid status request; the message is user-facing."""


def _validate(status):
    if status not in InquiryStatus.values:
        raise InquiryStatusError(f'Unsupported status: {status}.')


def _user_or_none(user):
    return user if getattr(user, 'is_authenticated', False) else None


@transaction.atomic
def set_status(inquiry, status, *, user, source=InquiryStatusEvent.SOURCE_UPDATE, remarks=None):
    """Set the inquiry's status (and remarks, when given) and record who did it.

    Re-setting the current status records nothing (remarks, if given, are still saved).
    """
    _validate(status)
    locked = Inquiry.objects.select_for_update().get(pk=inquiry.pk)
    old_status = locked.status
    if old_status == status:
        if remarks is not None:
            inquiry.remarks = remarks
            inquiry.save(update_fields=['remarks', 'updated_at'])
        return None
    inquiry.status = status
    update_fields = ['status', 'updated_at']
    if status in CLOSING_STATUSES:
        inquiry.closed_at = now()
        update_fields.append('closed_at')
    if remarks is not None:
        inquiry.remarks = remarks
        update_fields.append('remarks')
    inquiry.save(update_fields=update_fields)
    return InquiryStatusEvent.objects.create(
        company_id=inquiry.company_id, inquiry=inquiry, user=_user_or_none(user),
        old_status=old_status, new_status=status,
        remarks=remarks if remarks is not None else '', source=source,
    )


@transaction.atomic
def close_open_inquiries(queryset, *, user):
    """Close every Open inquiry in queryset (Close stale), one history row each."""
    rows = list(
        queryset.filter(status=InquiryStatus.OPEN).order_by()
        .select_for_update().values_list('pk', 'company_id')
    )
    if not rows:
        return 0
    moment = now()
    Inquiry.objects.filter(pk__in=[pk for pk, _ in rows]).update(
        status=InquiryStatus.CLOSED, closed_at=moment, updated_at=moment,
    )
    actor = _user_or_none(user)
    InquiryStatusEvent.objects.bulk_create([
        InquiryStatusEvent(
            company_id=company_id, inquiry_id=pk, user=actor,
            old_status=InquiryStatus.OPEN, new_status=InquiryStatus.CLOSED,
            source=InquiryStatusEvent.SOURCE_CLOSE_STALE,
        )
        for pk, company_id in rows
    ])
    return len(rows)


def record_initial_status(inquiry, *, user):
    """History row for an inquiry a person created with a chosen first status."""
    return InquiryStatusEvent.objects.create(
        company_id=inquiry.company_id, inquiry=inquiry, user=_user_or_none(user),
        old_status='', new_status=inquiry.status, remarks=inquiry.remarks,
        source=InquiryStatusEvent.SOURCE_MANUAL_CREATE,
    )


def _label(user):
    if user is None:
        return 'System'
    return user.get_full_name() or user.username


def status_history(inquiry):
    return [
        {
            'id': event.pk,
            'user_name': _label(event.user),
            'old_status': event.old_status,
            'old_status_label': InquiryStatus(event.old_status).label if event.old_status else '',
            'new_status': event.new_status,
            'new_status_label': InquiryStatus(event.new_status).label,
            'remarks': event.remarks,
            'source': event.source,
            'source_label': event.get_source_display(),
            'created_at': event.created_at.isoformat(),
        }
        for event in inquiry.status_events.select_related('user').order_by('-created_at', '-id')
    ]


def attach_last_change(inquiries):
    """Set inquiry.viewer_status_change to the latest change, in two queries.

    by_owner says whether that user owns the inquiry's WhatsApp account, so the board can
    point out changes made by someone else (an admin, a colleague with account access).
    """
    inquiries = list(inquiries)
    if not inquiries:
        return inquiries
    latest = {}
    for event in (
        InquiryStatusEvent.objects.filter(inquiry__in=inquiries)
        .select_related('user').order_by('inquiry_id', '-created_at', '-id')
        .distinct('inquiry_id')
    ):
        latest[event.inquiry_id] = event
    owners = {}
    for comm_id, user_id in CommunicationAccountAssignment.objects.filter(
        communication_account_id__in={inq.account.communication_account_id for inq in inquiries},
        access_level=CommunicationAccountAssignment.ACCESS_OWNER,
        is_active=True,
    ).values_list('communication_account_id', 'membership__user_id'):
        owners.setdefault(comm_id, set()).add(user_id)
    for inq in inquiries:
        event = latest.get(inq.pk)
        inq.viewer_status_change = None if event is None else {
            'user_name': _label(event.user),
            'by_owner': event.user_id in owners.get(inq.account.communication_account_id, set()),
            'status_label': InquiryStatus(event.new_status).label,
            'source': event.source,
            'created_at': event.created_at.isoformat(),
        }
    return inquiries
