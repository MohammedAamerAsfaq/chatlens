from django.db import models


class ClientPulseSettings(models.Model):
    CONSENT_MODES = [('observational', 'Observational'), ('enforced', 'Enforced')]
    REMINDER_SOUNDS = [
        ('chime', 'Chime'),
        ('bell', 'Bell'),
        ('soft', 'Soft'),
    ]
    company = models.OneToOneField(
        'tenancy.Company', on_delete=models.CASCADE, related_name='clientpulse_settings',
    )
    automated_follow_up_enabled = models.BooleanField(default=False)
    consent_mode = models.CharField(max_length=20, choices=CONSENT_MODES, default='observational')
    reminders_enabled = models.BooleanField(default=True)
    reminder_popup_enabled = models.BooleanField(default=True)
    reminder_sound_enabled = models.BooleanField(default=True)
    reminder_sound = models.CharField(max_length=20, choices=REMINDER_SOUNDS, default='chime')
    reminder_sound_volume = models.PositiveSmallIntegerField(default=70)
    reminder_desktop_notifications_enabled = models.BooleanField(default=False)
    reminder_poll_interval_seconds = models.PositiveSmallIntegerField(default=30)
    default_timezone = models.CharField(max_length=64, default='Asia/Dubai')
    default_language = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'clientpulse_settings'
