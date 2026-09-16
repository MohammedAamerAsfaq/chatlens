from django.db import models


class TelemetryFetchStatus(models.TextChoices):
    UNKNOWN = 'unknown', 'Unknown'
    AVAILABLE = 'available', 'Available'
    UNAVAILABLE = 'unavailable', 'Unavailable'
    UNSUPPORTED = 'unsupported', 'Unsupported'


class WhatsAppAccountCapacity(models.Model):
    account = models.OneToOneField(
        'whatsapp_bridge.WhatsAppAccount',
        on_delete=models.CASCADE,
        related_name='message_capacity',
    )
    source = models.CharField(max_length=50, default='baileys_v7')

    total_quota = models.PositiveIntegerField(null=True, blank=True)
    used_quota = models.PositiveIntegerField(null=True, blank=True)
    cycle_started_at = models.DateTimeField(null=True, blank=True)
    cycle_ends_at = models.DateTimeField(null=True, blank=True)
    server_sent_at = models.DateTimeField(null=True, blank=True)
    capping_status = models.CharField(max_length=40, blank=True)
    ote_status = models.CharField(max_length=50, blank=True)
    mv_status = models.CharField(max_length=50, blank=True)
    cap_fetch_status = models.CharField(
        max_length=20,
        choices=TelemetryFetchStatus.choices,
        default=TelemetryFetchStatus.UNKNOWN,
    )
    cap_checked_at = models.DateTimeField(null=True, blank=True)
    cap_updated_at = models.DateTimeField(null=True, blank=True)
    cap_error = models.TextField(blank=True)

    reachout_lock_active = models.BooleanField(default=False)
    reachout_lock_ends_at = models.DateTimeField(null=True, blank=True)
    reachout_enforcement_type = models.CharField(max_length=100, blank=True)
    reachout_fetch_status = models.CharField(
        max_length=20,
        choices=TelemetryFetchStatus.choices,
        default=TelemetryFetchStatus.UNKNOWN,
    )
    reachout_checked_at = models.DateTimeField(null=True, blank=True)
    reachout_updated_at = models.DateTimeField(null=True, blank=True)
    reachout_error = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'whatsapp_account_capacity'

    @property
    def remaining_quota(self):
        if self.total_quota is None or self.used_quota is None:
            return None
        return max(0, self.total_quota - self.used_quota)

    def __str__(self):
        return f'Capacity for WhatsApp account {self.account_id}'
