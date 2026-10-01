from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class ClientActivity(models.Model):
    TYPES = [(value, value.replace('_', ' ').title()) for value in (
        'inbound_message', 'outbound_message', 'note', 'call', 'meeting',
        'reminder', 'status_change', 'sequence_event', 'sync_event',
    )]
    company = models.ForeignKey('tenancy.Company', on_delete=models.CASCADE, related_name='client_activities')
    profile = models.ForeignKey('clientpulse.ClientProfile', on_delete=models.CASCADE, related_name='activities')
    activity_type = models.CharField(max_length=30, choices=TYPES)
    occurred_at = models.DateTimeField()
    title = models.CharField(max_length=255)
    summary = models.TextField(blank=True)
    channel = models.CharField(max_length=30, blank=True)
    direction = models.CharField(max_length=20, blank=True)
    source_model = models.CharField(max_length=100, blank=True)
    source_id = models.CharField(max_length=100, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='client_activities_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'clientpulse_activity'
        ordering = ['-occurred_at', '-id']
        constraints = [models.UniqueConstraint(
            fields=['company', 'profile', 'source_model', 'source_id'],
            condition=~models.Q(source_model='') & ~models.Q(source_id=''),
            name='unique_client_activity_source',
        )]

    def clean(self):
        if self.profile_id and self.profile.company_id != self.company_id:
            raise ValidationError('Client activity profile must belong to the same company.')

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
