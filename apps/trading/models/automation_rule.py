from django.db import models


class AutomationRule(models.Model):
    """
    A watch rule for the Product Price Update page's "Automated Price Updates"
    section (Sale Price tab only) — when an inbound message from one of this rule's
    watched sources satisfies its trigger condition, the message text is run through
    the same AI sale-price matching process as the manual flow
    (PromptConfig.KEY_SALE_PRICE_UPDATE). Per action_mode, the result is queued for
    human review, applied immediately, or — for ACTION_TEST — just recorded as a
    "this rule fires correctly" confirmation with no inventory change and nothing
    left needing review.
    """
    ACTION_REVIEW = 'review'
    ACTION_AUTO   = 'auto'
    ACTION_TEST   = 'test'
    ACTION_CHOICES = [
        (ACTION_REVIEW, 'Send for review'),
        (ACTION_AUTO,   'Auto-apply'),
        (ACTION_TEST,   'Test rule'),
    ]

    name       = models.CharField(max_length=200)
    is_active  = models.BooleanField(default=True)

    # Content trigger — OR'd together: matches if the heading text is found (when
    # set), or if trigger_ai_detect is on and the AI parse actually returns priced
    # items. Both blank/false means "any message from a watched source".
    trigger_heading    = models.CharField(max_length=200, blank=True)
    trigger_ai_detect  = models.BooleanField(default=False)

    action_mode = models.CharField(max_length=10, choices=ACTION_CHOICES, default=ACTION_REVIEW)

    last_triggered_at = models.DateTimeField(null=True, blank=True)
    trigger_count     = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'trading_automation_rule'
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class AutomationRuleSource(models.Model):
    """
    One watched source for an AutomationRule. Three independent, combinable kinds —
    a rule can have any mix of all three:
      - CONTACT: that contact's direct messages only.
      - GROUP: any member's messages in that group.
      - CONTACT_IN_GROUP: only that specific contact's messages, and only when
        posted inside that specific group (not their DMs, not other members).
    """
    SOURCE_CONTACT          = 'contact'
    SOURCE_GROUP            = 'group'
    SOURCE_CONTACT_IN_GROUP = 'contact_in_group'
    SOURCE_TYPE_CHOICES = [
        (SOURCE_CONTACT,          'Contact (direct messages)'),
        (SOURCE_GROUP,            'Group (any member)'),
        (SOURCE_CONTACT_IN_GROUP, 'Specific contact within a group'),
    ]

    rule = models.ForeignKey(AutomationRule, on_delete=models.CASCADE, related_name='sources')
    source_type = models.CharField(max_length=20, choices=SOURCE_TYPE_CHOICES)
    contact = models.ForeignKey(
        'whatsapp_bridge.WhatsAppContact', on_delete=models.CASCADE,
        null=True, blank=True, related_name='+',
    )
    group = models.ForeignKey(
        'whatsapp_bridge.WhatsAppGroup', on_delete=models.CASCADE,
        null=True, blank=True, related_name='+',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'trading_automation_rule_source'

    def __str__(self):
        return f'{self.get_source_type_display()} (rule {self.rule_id})'


class AutomatedPriceCapture(models.Model):
    """
    One row per inbound message that matched an AutomationRule — the "Recent
    detections" feed and review queue. `items` is the same shape the manual Sale
    Price parse returns: [{product_id, canonical_name, sale_price, currency}].
    One capture per message (a message triggers at most the first rule it matches).
    """
    STATUS_QUEUED  = 'queued'
    STATUS_APPLIED = 'applied'
    STATUS_IGNORED = 'ignored'
    STATUS_TEST    = 'test'
    STATUS_CHOICES = [
        (STATUS_QUEUED,  'Queued'),
        (STATUS_APPLIED, 'Applied'),
        (STATUS_IGNORED, 'Ignored'),
        (STATUS_TEST,    'Test match'),
    ]

    rule = models.ForeignKey(
        AutomationRule, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='captures',
    )
    message = models.OneToOneField(
        'whatsapp_bridge.WhatsAppMessage', on_delete=models.CASCADE, related_name='price_capture',
    )
    items  = models.JSONField(default=list)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_QUEUED)

    created_at = models.DateTimeField(auto_now_add=True)
    applied_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'trading_automated_price_capture'
        ordering = ['-created_at']

    def __str__(self):
        return f'capture {self.pk} | {self.status}'
