"""Sharing Trading inquiries between users of one company.

An inquiry belongs to a WhatsApp account, and the account owner works it through
Inquiry.status. Sharing lets other users work the same inquiry without touching that
status: each recipient's action lives in SharedInquiryAction (current state) and
SharedInquiryActionEvent (history). Nothing a recipient does is written back to the
inquiry; the owner only sees who handled it and how.

Two ways to share:
- InquirySharingRule: "share all my inquiries with this user". It covers inquiries on
  the accounts the owner owns that arrive at or after started_at, while it is active.
- InquiryShare: one inquiry shared with one user.
"""

from django.conf import settings
from django.db import models
from django.db.models import F, Q

from .inquiry import InquiryStatus


class InquirySharingRule(models.Model):
    company = models.ForeignKey(
        'tenancy.Company', on_delete=models.CASCADE, related_name='inquiry_sharing_rules',
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='inquiry_sharing_rules_given',
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='inquiry_sharing_rules_received',
    )
    # Only inquiries first seen at or after this moment are shared ("from now on").
    started_at = models.DateTimeField()
    # Set when sharing is turned off; switching it back on starts a new rule.
    ended_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'trading_inquiry_sharing_rule'
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'owner', 'recipient'],
                condition=Q(ended_at__isnull=True),
                name='trading_inquiry_sharing_rule_one_active',
            ),
            models.CheckConstraint(
                condition=~Q(owner=F('recipient')),
                name='trading_inquiry_sharing_rule_not_self',
            ),
        ]

    def __str__(self):
        return f'InquirySharingRule({self.owner_id} -> {self.recipient_id})'


class InquiryShare(models.Model):
    company = models.ForeignKey(
        'tenancy.Company', on_delete=models.CASCADE, related_name='inquiry_shares',
    )
    inquiry = models.ForeignKey(
        'trading.Inquiry', on_delete=models.CASCADE, related_name='shares',
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='inquiry_shares_received',
    )
    shared_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='inquiry_shares_given',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'trading_inquiry_share'
        constraints = [
            models.UniqueConstraint(
                fields=['inquiry', 'recipient'],
                condition=Q(revoked_at__isnull=True),
                name='trading_inquiry_share_one_active',
            ),
        ]

    def __str__(self):
        return f'InquiryShare({self.inquiry_id} -> {self.recipient_id})'


class SharedInquiryAction(models.Model):
    """A recipient's own current action on an inquiry shared with them."""

    company = models.ForeignKey(
        'tenancy.Company', on_delete=models.CASCADE, related_name='shared_inquiry_actions',
    )
    inquiry = models.ForeignKey(
        'trading.Inquiry', on_delete=models.CASCADE, related_name='shared_actions',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='shared_inquiry_actions',
    )
    status = models.CharField(max_length=20, choices=InquiryStatus.choices, default=InquiryStatus.OPEN)
    remarks = models.TextField(blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'trading_shared_inquiry_action'
        constraints = [
            models.UniqueConstraint(fields=['inquiry', 'user'], name='trading_shared_inquiry_action_one_per_user'),
        ]

    def __str__(self):
        return f'SharedInquiryAction({self.inquiry_id}, {self.user_id}, {self.status})'


class SharedInquiryActionEvent(models.Model):
    """Append-only history of every action a recipient took on a shared inquiry."""

    company = models.ForeignKey(
        'tenancy.Company', on_delete=models.CASCADE, related_name='shared_inquiry_action_events',
    )
    inquiry = models.ForeignKey(
        'trading.Inquiry', on_delete=models.CASCADE, related_name='shared_action_events',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='shared_inquiry_action_events',
    )
    status = models.CharField(max_length=20, choices=InquiryStatus.choices)
    remarks = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'trading_shared_inquiry_action_event'
        ordering = ['created_at', 'id']

    def __str__(self):
        return f'SharedInquiryActionEvent({self.inquiry_id}, {self.user_id}, {self.status})'
