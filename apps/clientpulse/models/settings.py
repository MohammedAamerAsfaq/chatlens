from django.db import models


class ClientPulseSettings(models.Model):
    CONSENT_MODES = [('observational', 'Observational'), ('enforced', 'Enforced')]
    company = models.OneToOneField(
        'tenancy.Company', on_delete=models.CASCADE, related_name='clientpulse_settings',
    )
    automated_follow_up_enabled = models.BooleanField(default=False)
    consent_mode = models.CharField(max_length=20, choices=CONSENT_MODES, default='observational')
    reminders_enabled = models.BooleanField(default=True)
    default_timezone = models.CharField(max_length=64, default='Asia/Dubai')
    default_language = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'clientpulse_settings'
