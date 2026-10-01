from django.core.exceptions import ValidationError
from django.db import models


class ContactConsent(models.Model):
    PURPOSES = [(value, value.replace('_', ' ').title()) for value in ('transactional', 'follow_up', 'marketing')]
    STATUSES = [(value, value.title()) for value in ('unknown', 'granted', 'denied', 'revoked')]
    company = models.ForeignKey('tenancy.Company', on_delete=models.CASCADE, related_name='contact_consents')
    profile = models.ForeignKey('clientpulse.ClientProfile', on_delete=models.CASCADE, related_name='consents')
    channel = models.CharField(max_length=30)
    purpose = models.CharField(max_length=30, choices=PURPOSES)
    status = models.CharField(max_length=20, choices=STATUSES, default='unknown')
    source = models.CharField(max_length=100, blank=True)
    captured_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    evidence = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'clientpulse_contact_consent'
        ordering = ['channel', 'purpose']
        constraints = [models.UniqueConstraint(
            fields=['company', 'profile', 'channel', 'purpose'],
            name='unique_client_consent_scope',
        )]

    def clean(self):
        if self.profile_id and self.profile.company_id != self.company_id:
            raise ValidationError('Contact consent profile must belong to the same company.')

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
