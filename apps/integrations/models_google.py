from django.conf import settings
from django.db import models
from django.db.models import Q


class GeographyExternalReference(models.Model):
    PROVIDER_GOOGLE_MAPS = 'google_maps'
    STATUS_SUGGESTED = 'suggested'
    STATUS_VERIFIED = 'verified'
    STATUS_CONFLICT = 'conflict'
    STATUS_REVOKED = 'revoked'

    locality = models.ForeignKey(
        'integrations.Locality', on_delete=models.CASCADE,
        related_name='external_references',
    )
    city = models.ForeignKey(
        'integrations.City', on_delete=models.PROTECT,
        related_name='external_locality_references',
    )
    provider = models.CharField(
        max_length=40, default=PROVIDER_GOOGLE_MAPS,
        choices=[(PROVIDER_GOOGLE_MAPS, 'Google Maps')],
    )
    external_id = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=[
        (STATUS_SUGGESTED, 'Suggested'),
        (STATUS_VERIFIED, 'Verified'),
        (STATUS_CONFLICT, 'Conflict'),
        (STATUS_REVOKED, 'Revoked'),
    ], default=STATUS_VERIFIED, db_index=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='geography_resolutions',
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    last_checked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'geo_external_reference'
        ordering = ['locality_id', 'provider']
        constraints = [
            models.UniqueConstraint(
                fields=['locality', 'provider'], name='unique_locality_provider_reference',
            ),
            models.UniqueConstraint(
                fields=['provider', 'external_id'],
                condition=~Q(status='revoked'),
                name='unique_active_geography_external_id',
            ),
        ]


class IntegrationUsagePeriod(models.Model):
    connection = models.ForeignKey(
        'integrations.IntegrationConnection', on_delete=models.CASCADE,
        related_name='usage_periods',
    )
    period_start = models.DateField()
    request_count = models.PositiveIntegerField(default=0)
    operation_counts = models.JSONField(default=dict, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'integration_usage_period'
        ordering = ['-period_start']
        constraints = [
            models.UniqueConstraint(
                fields=['connection', 'period_start'], name='unique_integration_usage_period',
            ),
        ]
