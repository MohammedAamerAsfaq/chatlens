"""Inquiry sharing between users of one company (see models/inquiry_sharing.py).

An inquiry is "own" for a user when they can see it through their WhatsApp account
access; owners work it through Inquiry.status as before. It is "shared" with a user who
cannot see it that way but has an active InquirySharingRule from an owner of its account
(and it arrived after the rule started), or an active InquiryShare. A shared inquiry's
status for that user is their SharedInquiryAction (Open until they act). Recipients never
write to the Inquiry itself.
"""

import re

from django.db import transaction
from django.db.models import Q
from django.utils.timezone import now

from apps.tenancy.models import CommunicationAccountAssignment, CompanyMembership
from apps.tenancy.services.access import visible_accounts_queryset
from apps.tenancy.services.authorization import permission_scope_for_membership
from apps.trading.models import (
    Inquiry, InquiryShare, InquirySharingRule, InquiryStatus,
    SharedInquiryAction, SharedInquiryActionEvent,
)

BOARD_PERMISSION = 'trading.board.view'
CLOSING_STATUSES = (InquiryStatus.CLOSED, InquiryStatus.DEAL_DONE)


class SharingError(ValueError):
    """A sharing request that cannot be honoured; the message is user-facing."""


def user_label(user):
    return user.get_full_name() or user.username


# ── Who may share and receive ────────────────────────────────────────────────────────

def eligible_recipients(company, exclude_user):
    """Active members of the company, other than exclude_user, who can view the board."""
    memberships = (
        CompanyMembership.objects
        .filter(company=company, is_active=True, user__is_active=True)
        .exclude(user=exclude_user)
        .select_related('user')
        .order_by('user__first_name', 'user__username')
    )
    return [m.user for m in memberships if permission_scope_for_membership(m, BOARD_PERMISSION)]


def _validated_recipients(company, actor, recipient_ids):
    if not isinstance(recipient_ids, list) or not all(isinstance(pk, int) for pk in recipient_ids):
        raise SharingError('recipient_ids must be a list of user ids.')
    eligible = {user.pk: user for user in eligible_recipients(company, actor)}
    unknown = sorted(set(recipient_ids) - set(eligible))
    if unknown:
        raise SharingError(f'These users cannot receive shared inquiries: {unknown}.')
    return [eligible[pk] for pk in dict.fromkeys(recipient_ids)]


def owned_communication_account_ids(user, company):
    return list(
        CommunicationAccountAssignment.objects.filter(
            company=company,
            membership__user=user,
            membership__is_active=True,
            access_level=CommunicationAccountAssignment.ACCESS_OWNER,
            is_active=True,
        ).values_list('communication_account_id', flat=True)
    )


# ── Share all (settings) ─────────────────────────────────────────────────────────────

def sharing_settings(owner, company):
    active = {
        rule.recipient_id: rule
        for rule in InquirySharingRule.objects.filter(company=company, owner=owner, ended_at__isnull=True)
    }
    return {
        'owns_accounts': bool(owned_communication_account_ids(owner, company)),
        'recipients': [
            {
                'id': user.pk,
                'name': user_label(user),
                'shared': user.pk in active,
                'since': active[user.pk].started_at.isoformat() if user.pk in active else None,
            }
            for user in eligible_recipients(company, owner)
        ],
    }


@transaction.atomic
def set_sharing_recipients(owner, company, recipient_ids):
    """Share all of the owner's new inquiries with exactly these users."""
    recipients = _validated_recipients(company, owner, recipient_ids)
    if recipients and not owned_communication_account_ids(owner, company):
        raise SharingError('You do not own any WhatsApp account, so there are no inquiries of yours to share.')
    wanted = {user.pk for user in recipients}
    moment = now()
    InquirySharingRule.objects.filter(
        company=company, owner=owner, ended_at__isnull=True,
    ).exclude(recipient_id__in=wanted).update(ended_at=moment)
    existing = set(
        InquirySharingRule.objects.filter(company=company, owner=owner, ended_at__isnull=True)
        .values_list('recipient_id', flat=True)
    )
    for user in recipients:
        if user.pk not in existing:
            InquirySharingRule.objects.create(company=company, owner=owner, recipient=user, started_at=moment)
    return sharing_settings(owner, company)


# ── Share one inquiry ────────────────────────────────────────────────────────────────

def _rule_recipient_ids(inquiry):
    """Users this inquiry reaches through an owner's active share-all rule."""
    rules = InquirySharingRule.objects.filter(
        company_id=inquiry.company_id, ended_at__isnull=True, started_at__lte=inquiry.first_seen_at,
    )
    owners = set(
        CommunicationAccountAssignment.objects.filter(
            company_id=inquiry.company_id,
            communication_account_id=inquiry.account.communication_account_id,
            access_level=CommunicationAccountAssignment.ACCESS_OWNER,
            is_active=True,
            membership__is_active=True,
        ).values_list('membership__user_id', flat=True)
    )
    return {rule.recipient_id: rule.owner_id for rule in rules if rule.owner_id in owners}


def inquiry_shares(inquiry, actor):
    company = inquiry.company
    direct = set(
        InquiryShare.objects.filter(inquiry=inquiry, revoked_at__isnull=True).values_list('recipient_id', flat=True)
    )
    by_rule = _rule_recipient_ids(inquiry)
    return {
        'recipients': [
            {
                'id': user.pk,
                'name': user_label(user),
                'shared': user.pk in direct,
                'shared_by_rule': user.pk in by_rule,
            }
            for user in eligible_recipients(company, actor)
        ],
    }


@transaction.atomic
def set_inquiry_shares(inquiry, actor, recipient_ids):
    """Share this inquiry individually with exactly these users (share-all is separate)."""
    if inquiry.company_id is None:
        raise SharingError('This inquiry has no company and cannot be shared.')
    recipients = _validated_recipients(inquiry.company, actor, recipient_ids)
    wanted = {user.pk for user in recipients}
    InquiryShare.objects.filter(
        inquiry=inquiry, revoked_at__isnull=True,
    ).exclude(recipient_id__in=wanted).update(revoked_at=now())
    existing = set(
        InquiryShare.objects.filter(inquiry=inquiry, revoked_at__isnull=True).values_list('recipient_id', flat=True)
    )
    for user in recipients:
        if user.pk not in existing:
            InquiryShare.objects.create(
                company=inquiry.company, inquiry=inquiry, recipient=user, shared_by=actor,
            )
    return inquiry_shares(inquiry, actor)


# ── What a user sees ─────────────────────────────────────────────────────────────────

def _own_account_q(user):
    return Q(account_id__in=visible_accounts_queryset(user).values('pk'))


def shared_with_user_q(user, company):
    """Inquiries shared with the user by rule or individually (before excluding own ones)."""
    if company is None:
        return Q(pk__in=[])
    condition = Q(
        shares__recipient=user, shares__revoked_at__isnull=True, shares__company=company,
    )
    condition = Q(pk__in=Inquiry.objects.filter(condition).values('pk'))
    rules = InquirySharingRule.objects.filter(company=company, recipient=user, ended_at__isnull=True)
    for rule in rules:
        account_ids = owned_communication_account_ids(rule.owner, company)
        if account_ids:
            condition |= Q(
                account__communication_account_id__in=account_ids,
                first_seen_at__gte=rule.started_at,
            )
    return condition & Q(company=company)


def shared_inquiry_queryset(user, company, queryset):
    """The inquiries in queryset that are shared with the user and not already their own."""
    return queryset.filter(shared_with_user_q(user, company)).exclude(_own_account_q(user))


def is_shared_with(inquiry, user, company):
    return shared_inquiry_queryset(user, company, Inquiry.objects.filter(pk=inquiry.pk)).exists()


# ── Recipient actions ────────────────────────────────────────────────────────────────

@transaction.atomic
def record_shared_action(inquiry, user, *, status=None, remarks=None):
    """Set the recipient's own status/remarks on a shared inquiry; logs every change."""
    if status is not None and status not in InquiryStatus.values:
        raise SharingError(f'Unsupported status: {status}.')
    action, _ = SharedInquiryAction.objects.select_for_update().get_or_create(
        inquiry=inquiry, user=user, defaults={'company_id': inquiry.company_id},
    )
    if status is not None:
        action.status = status
        action.closed_at = now() if status in CLOSING_STATUSES else None
    if remarks is not None:
        action.remarks = remarks
    action.save()
    SharedInquiryActionEvent.objects.create(
        company_id=inquiry.company_id, inquiry=inquiry, user=user,
        status=action.status, remarks=action.remarks,
    )
    return action


# ── Board annotations ────────────────────────────────────────────────────────────────

def attach_viewer_context(inquiries, user, company, shared_ids):
    """Set the per-viewer attributes InquirySerializer reads, in a fixed number of queries.

    Shared inquiries get the viewer's own status/remarks and who shared them; own
    inquiries get how each recipient handled them.
    """
    inquiries = list(inquiries)
    shared_ids = set(shared_ids)
    shared = [inq for inq in inquiries if inq.pk in shared_ids]
    own = [inq for inq in inquiries if inq.pk not in shared_ids]

    if shared:
        actions = {
            action.inquiry_id: action
            for action in SharedInquiryAction.objects.filter(inquiry__in=shared, user=user)
        }
        sharers = _sharers(shared, user, company)
        for inq in shared:
            action = actions.get(inq.pk)
            inq.viewer_is_shared = True
            inq.viewer_status = action.status if action else InquiryStatus.OPEN
            inq.viewer_remarks = action.remarks if action else ''
            inq.viewer_shared_by = sharers.get(inq.pk, [])
    if own:
        handling = {}
        for action in (
            SharedInquiryAction.objects.filter(inquiry__in=own)
            .select_related('user').order_by('-updated_at')
        ):
            handling.setdefault(action.inquiry_id, []).append({
                'user_id': action.user_id,
                'user_name': user_label(action.user),
                'status': action.status,
                'status_label': InquiryStatus(action.status).label,
                'remarks': action.remarks,
                'updated_at': action.updated_at.isoformat(),
            })
        for inq in own:
            inq.viewer_shared_handling = handling.get(inq.pk, [])
    return inquiries


def _sharers(inquiries, user, company):
    names = {}
    for share in InquiryShare.objects.filter(
        inquiry__in=inquiries, recipient=user, revoked_at__isnull=True,
    ).select_related('shared_by'):
        names.setdefault(share.inquiry_id, []).append(user_label(share.shared_by))
    rules = list(
        InquirySharingRule.objects.filter(company=company, recipient=user, ended_at__isnull=True)
        .select_related('owner')
    )
    rule_accounts = [(rule, set(owned_communication_account_ids(rule.owner, company))) for rule in rules]
    for inq in inquiries:
        for rule, account_ids in rule_accounts:
            if inq.account.communication_account_id in account_ids and inq.first_seen_at >= rule.started_at:
                label = user_label(rule.owner)
                if label not in names.setdefault(inq.pk, []):
                    names[inq.pk].append(label)
    return names


# ── Messaging the customer from the recipient's own account ─────────────────────────

def recipient_direct_chat(inquiry, account):
    """The recipient's own 1:1 chat with the inquiry's contact, keyed by phone JID."""
    from apps.whatsapp_bridge.models import WhatsAppChat, WhatsAppContact

    source = inquiry.contact
    if source is None:
        raise SharingError('This inquiry has no contact to message.')
    jid = (source.wa_contact_id or '').strip().lower()
    phone = re.sub(r'\D', '', source.phone_number or '')
    if not jid.endswith('@s.whatsapp.net'):
        jid = f'{phone}@s.whatsapp.net' if phone else ''
    if not jid:
        raise SharingError('This contact has no resolved WhatsApp phone number.')
    phone = phone or jid.split('@', 1)[0]

    # is_existing_chat drives the outbound new-chat safety checks (new-chat cap, unknown
    # new-chat policy). The model defaults it to True, which would let the first message to
    # a customer this account has never talked to skip those checks, so a contact created
    # here is existing only if this account already has message history with them.
    has_history = WhatsAppChat.objects.filter(account=account, wa_chat_id=jid, messages__isnull=False).exists()
    contact, _ = WhatsAppContact.objects.get_or_create(
        account=account, wa_contact_id=jid,
        defaults={
            'phone_number': phone,
            'display_name': source.display_name or source.push_name,
            'company_contact_id': source.company_contact_id,
            'is_existing_chat': has_history,
        },
    )
    chat, _ = WhatsAppChat.objects.get_or_create(
        account=account, wa_chat_id=jid, defaults={'chat_type': 'individual', 'contact': contact},
    )
    if chat.contact_id != contact.pk:
        chat.contact = contact
        chat.save(update_fields=['contact', 'updated_at'])
    return chat

