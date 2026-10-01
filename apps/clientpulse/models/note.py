from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class ClientNote(models.Model):
    company = models.ForeignKey('tenancy.Company', on_delete=models.CASCADE, related_name='client_notes')
    profile = models.ForeignKey('clientpulse.ClientProfile', on_delete=models.CASCADE, related_name='notes')
    body = models.TextField()
    is_pinned = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='client_notes_created',
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='client_notes_updated',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'clientpulse_note'
        ordering = ['-is_pinned', '-created_at']

    def clean(self):
        if self.profile_id and self.profile.company_id != self.company_id:
            raise ValidationError('Client note profile must belong to the same company.')

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
