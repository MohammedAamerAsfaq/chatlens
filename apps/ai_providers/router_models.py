from django.db import models

from .models import AIProviderConfig


class KiwiRouter(models.Model):
    STRATEGY_ORDERED_CAPACITY_FILL = 'ordered_capacity_fill'
    STRATEGY_CHOICES = [(STRATEGY_ORDERED_CAPACITY_FILL, 'Ordered capacity fill')]

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    capability = models.CharField(max_length=50, choices=AIProviderConfig.CAPABILITY_CHOICES)
    strategy = models.CharField(max_length=50, choices=STRATEGY_CHOICES, default=STRATEGY_ORDERED_CAPACITY_FILL)
    default_request_timeout_seconds = models.PositiveIntegerField(default=60)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class KiwiRouterMember(models.Model):
    METADATA_PROVIDER_PUBLISHED = 'provider_published'
    METADATA_OPERATOR_SUPPLIED = 'operator_supplied'
    METADATA_INCOMPLETE = 'incomplete'
    METADATA_CHOICES = [
        (METADATA_PROVIDER_PUBLISHED, 'Provider published'),
        (METADATA_OPERATOR_SUPPLIED, 'Operator supplied'),
        (METADATA_INCOMPLETE, 'Incomplete'),
    ]

    router = models.ForeignKey(KiwiRouter, on_delete=models.CASCADE, related_name='members')
    provider_config = models.ForeignKey(AIProviderConfig, on_delete=models.PROTECT, related_name='kiwi_router_members')
    priority = models.PositiveIntegerField()
    is_enabled = models.BooleanField(default=True)
    rpm_limit = models.PositiveIntegerField(null=True, blank=True)
    tpm_limit = models.PositiveIntegerField(null=True, blank=True)
    max_concurrency = models.PositiveIntegerField(null=True, blank=True)
    input_cost_per_million = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    output_cost_per_million = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    metadata_source = models.CharField(max_length=30, choices=METADATA_CHOICES, default=METADATA_INCOMPLETE)
    metadata_verified_at = models.DateTimeField(null=True, blank=True)
    metadata_review_due_at = models.DateTimeField(null=True, blank=True)
    request_timeout_seconds = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['priority', 'id']
        constraints = [models.UniqueConstraint(fields=['router', 'priority'], name='unique_kiwi_router_priority')]

    def __str__(self):
        return f'{self.router.name} #{self.priority}: {self.provider_config.display_name}'


class KiwiRouterReservation(models.Model):
    STATUS_RESERVED = 'reserved'
    STATUS_DISPATCHED = 'dispatched'
    STATUS_SUCCEEDED = 'succeeded'
    STATUS_FAILED = 'failed'
    STATUS_EXPIRED = 'expired'
    STATUS_CHOICES = [(value, value.title()) for value in (STATUS_RESERVED, STATUS_DISPATCHED, STATUS_SUCCEEDED, STATUS_FAILED, STATUS_EXPIRED)]

    member = models.ForeignKey(KiwiRouterMember, on_delete=models.CASCADE, related_name='reservations')
    correlation_id = models.CharField(max_length=255, db_index=True)
    task_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    estimated_input_tokens = models.PositiveIntegerField(default=0)
    estimated_output_tokens = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_RESERVED)
    reserved_at = models.DateTimeField(auto_now_add=True, db_index=True)
    expires_at = models.DateTimeField(db_index=True)
    released_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=['member', 'reserved_at'])]


class KiwiRoutingDecision(models.Model):
    DECISION_SELECTED = 'selected'
    DECISION_DEFERRED = 'deferred'
    DECISION_SKIPPED = 'skipped'
    DECISION_CHOICES = [(value, value.title()) for value in (DECISION_SELECTED, DECISION_DEFERRED, DECISION_SKIPPED)]

    router = models.ForeignKey(KiwiRouter, null=True, blank=True, on_delete=models.SET_NULL, related_name='decisions')
    member = models.ForeignKey(KiwiRouterMember, null=True, blank=True, on_delete=models.SET_NULL, related_name='decisions')
    provider_config = models.ForeignKey(AIProviderConfig, null=True, blank=True, on_delete=models.SET_NULL, related_name='kiwi_routing_decisions')
    task_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    correlation_id = models.CharField(max_length=255, db_index=True)
    workflow_key = models.CharField(max_length=100)
    strategy = models.CharField(max_length=50)
    decision = models.CharField(max_length=20, choices=DECISION_CHOICES)
    reason = models.TextField(blank=True)
    estimated_input_tokens = models.PositiveIntegerField(default=0)
    estimated_output_tokens = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)


class DefaultAgentTarget(models.Model):
    """The global default used when an AI operation has no explicit target."""

    kiwi_router = models.ForeignKey(
        KiwiRouter,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='default_agent_targets',
    )
    updated_at = models.DateTimeField(auto_now=True)
