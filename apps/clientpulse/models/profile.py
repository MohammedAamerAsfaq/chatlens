from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class ClientProfile(models.Model):
    STAGES = [(value, value.replace('_', ' ').title()) for value in (
        'lead', 'prospect', 'active_customer', 'dormant', 'lost', 'blocked',
    )]
    STATUSES = [(value, value.title()) for value in ('active', 'paused', 'archived')]
    PRIORITIES = [(value, value.title()) for value in ('low', 'normal', 'high', 'critical')]
    SOURCES = [(value, value.replace('_', ' ').title()) for value in (
        'manual', 'whatsapp', 'google_contacts', 'import', 'referral', 'other',
    )]
    CHANNELS = [(value, value.title()) for value in ('whatsapp', 'email', 'phone', 'other')]

    company = models.ForeignKey('tenancy.Company', on_delete=models.CASCADE, related_name='client_profiles')
    contact = models.OneToOneField(
        'tenancy.CompanyContact', on_delete=models.CASCADE, related_name='client_profile',
    )
    owner = models.ForeignKey(
        'tenancy.CompanyMembership', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='owned_client_profiles',
    )
    lifecycle_stage = models.CharField(max_length=30, choices=STAGES, default='lead')
    status = models.CharField(max_length=20, choices=STATUSES, default='active')
    priority = models.CharField(max_length=20, choices=PRIORITIES, default='normal')
    source = models.CharField(max_length=30, choices=SOURCES, default='manual')
    preferred_channel = models.CharField(max_length=20, choices=CHANNELS, blank=True)
    preferred_language = models.CharField(max_length=20, blank=True)
    timezone = models.CharField(max_length=64, default='Asia/Dubai')
    company_name = models.CharField(max_length=255, blank=True)
    job_title = models.CharField(max_length=150, blank=True)
    website = models.URLField(max_length=500, blank=True)
    address_line1 = models.CharField(max_length=255, blank=True)
    address_line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state_region = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=30, blank=True)
    country = models.CharField(max_length=100, blank=True)
    last_contacted_at = models.DateTimeField(null=True, blank=True)
    last_inbound_at = models.DateTimeField(null=True, blank=True)
    next_follow_up_at = models.DateTimeField(null=True, blank=True)
    do_not_contact = models.BooleanField(default=False)
    do_not_contact_reason = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='client_profiles_created',
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='client_profiles_updated',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'clientpulse_profile'
        ordering = ['contact__display_name', '-updated_at']
        indexes = [
            models.Index(fields=['company', 'lifecycle_stage'], name='cp_profile_stage_idx'),
            models.Index(fields=['company', 'owner'], name='cp_profile_owner_idx'),
            models.Index(fields=['company', 'next_follow_up_at'], name='cp_profile_followup_idx'),
            models.Index(fields=['company', 'last_contacted_at'], name='cp_profile_contacted_idx'),
            models.Index(fields=['company', 'status'], name='cp_profile_status_idx'),
        ]

    def clean(self):
        if self.contact_id and self.contact.company_id != self.company_id:
            raise ValidationError('Client profile contact must belong to the same company.')
        if self.owner_id and self.owner.company_id != self.company_id:
            raise ValidationError('Client profile owner must belong to the same company.')

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
