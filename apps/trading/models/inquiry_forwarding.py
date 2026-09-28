from django.conf import settings
from django.db import models


class InquiryForwardingRule(models.Model):
    TYPE_WTB = 'buy'
    TYPE_WTS = 'sell'
    TYPE_CHOICES = [(TYPE_WTB, 'WTB'), (TYPE_WTS, 'WTS')]

    company = models.ForeignKey(
        'tenancy.Company', on_delete=models.CASCADE, related_name='inquiry_forwarding_rules',
    )
    inquiry_type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    name = models.CharField(max_length=200)
    is_active = models.BooleanField(default=False)
    include_original_message = models.BooleanField(default=True)
    include_summary = models.BooleanField(default=True)
    include_stock_suggestions = models.BooleanField(default=True)
    include_sender_link = models.BooleanField(default=True)
    include_inquiry_id = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='inquiry_forwarding_rules_created',
    )
    last_triggered_at = models.DateTimeField(null=True, blank=True)
    forwarded_count = models.PositiveIntegerField(default=0)
    skipped_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'trading_inquiry_forwarding_rule'
        ordering = ['inquiry_type']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'inquiry_type'], name='unique_company_inquiry_forwarding_type',
            ),
        ]


class InquiryForwardingTarget(models.Model):
    CONTACT = 'contact'
    GROUP = 'group'
    TYPE_CHOICES = [(CONTACT, 'Direct contact'), (GROUP, 'Group')]

    rule = models.ForeignKey(InquiryForwardingRule, on_delete=models.CASCADE, related_name='targets')
    target_type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    contact = models.ForeignKey(
        'whatsapp_bridge.WhatsAppContact', null=True, blank=True,
        on_delete=models.CASCADE, related_name='+',
    )
    group = models.ForeignKey(
        'whatsapp_bridge.WhatsAppGroup', null=True, blank=True,
        on_delete=models.CASCADE, related_name='+',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'trading_inquiry_forwarding_target'
        constraints = [
            models.UniqueConstraint(fields=['rule', 'contact'], name='unique_forward_rule_contact'),
            models.UniqueConstraint(fields=['rule', 'group'], name='unique_forward_rule_group'),
            models.CheckConstraint(
                condition=(
                    models.Q(target_type='contact', contact__isnull=False, group__isnull=True)
                    | models.Q(target_type='group', contact__isnull=True, group__isnull=False)
                ),
                name='valid_forward_target_endpoint',
            ),
        ]


class InquiryForwardingExclusion(models.Model):
    CONTACT = 'contact'
    GROUP = 'group'
    TYPE_CHOICES = [(CONTACT, 'Source contact'), (GROUP, 'Source group')]

    rule = models.ForeignKey(InquiryForwardingRule, on_delete=models.CASCADE, related_name='exclusions')
    exclusion_type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    contact = models.ForeignKey(
        'whatsapp_bridge.WhatsAppContact', null=True, blank=True,
        on_delete=models.CASCADE, related_name='+',
    )
    group = models.ForeignKey(
        'whatsapp_bridge.WhatsAppGroup', null=True, blank=True,
        on_delete=models.CASCADE, related_name='+',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'trading_inquiry_forwarding_exclusion'
        constraints = [
            models.UniqueConstraint(fields=['rule', 'contact'], name='unique_forward_exclusion_contact'),
            models.UniqueConstraint(fields=['rule', 'group'], name='unique_forward_exclusion_group'),
            models.CheckConstraint(
                condition=(
                    models.Q(exclusion_type='contact', contact__isnull=False, group__isnull=True)
                    | models.Q(exclusion_type='group', contact__isnull=True, group__isnull=False)
                ),
                name='valid_forward_exclusion_endpoint',
            ),
        ]


class InquiryForwardingRun(models.Model):
    STATUS_QUEUED = 'queued'
    STATUS_SKIPPED = 'skipped'
    STATUS_PARTIAL = 'partial'
    STATUS_COMPLETE = 'complete'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [(value, value.title()) for value in (
        STATUS_QUEUED, STATUS_SKIPPED, STATUS_PARTIAL, STATUS_COMPLETE, STATUS_FAILED,
    )]

    rule = models.ForeignKey(InquiryForwardingRule, on_delete=models.CASCADE, related_name='runs')
    inquiry = models.ForeignKey('trading.Inquiry', on_delete=models.CASCADE, related_name='forwarding_runs')
    source_message = models.ForeignKey(
        'whatsapp_bridge.WhatsAppMessage', null=True, on_delete=models.SET_NULL, related_name='+',
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_QUEUED)
    reason = models.CharField(max_length=120, blank=True)
    message_snapshot = models.TextField(blank=True)
    destination_count = models.PositiveIntegerField(default=0)
    queued_count = models.PositiveIntegerField(default=0)
    blocked_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'trading_inquiry_forwarding_run'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['rule', 'inquiry'], name='unique_forward_rule_inquiry'),
        ]


class InquiryForwardingDelivery(models.Model):
    run = models.ForeignKey(InquiryForwardingRun, on_delete=models.CASCADE, related_name='deliveries')
    target = models.ForeignKey(
        InquiryForwardingTarget, null=True, on_delete=models.SET_NULL, related_name='deliveries',
    )
    outbound_message = models.ForeignKey(
        'whatsapp_bridge.OutboundMessage', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='inquiry_forwarding_deliveries',
    )
    status = models.CharField(max_length=30)
    reason = models.CharField(max_length=120, blank=True)
    destination_label = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'trading_inquiry_forwarding_delivery'
        ordering = ['id']
        constraints = [
            models.UniqueConstraint(fields=['run', 'target'], name='unique_forward_run_target'),
        ]
