from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class ClientTag(models.Model):
    company = models.ForeignKey('tenancy.Company', on_delete=models.CASCADE, related_name='client_tags')
    name = models.CharField(max_length=100)
    normalized_name = models.CharField(max_length=100)
    color = models.CharField(max_length=20, default='#23865b')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'clientpulse_tag'
        ordering = ['name']
        constraints = [models.UniqueConstraint(
            fields=['company', 'normalized_name'], name='unique_client_tag_name_per_company',
        )]

    def save(self, *args, **kwargs):
        self.name = ' '.join(self.name.split())
        self.normalized_name = self.name.casefold()
        super().save(*args, **kwargs)


class ClientTagAssignment(models.Model):
    company = models.ForeignKey('tenancy.Company', on_delete=models.CASCADE, related_name='client_tag_assignments')
    profile = models.ForeignKey('clientpulse.ClientProfile', on_delete=models.CASCADE, related_name='tag_assignments')
    tag = models.ForeignKey(ClientTag, on_delete=models.CASCADE, related_name='assignments')
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='client_tags_assigned',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'clientpulse_tag_assignment'
        constraints = [models.UniqueConstraint(
            fields=['profile', 'tag'], name='unique_client_profile_tag',
        )]

    def clean(self):
        if self.profile_id and self.profile.company_id != self.company_id:
            raise ValidationError('Tag assignment profile company mismatch.')
        if self.tag_id and self.tag.company_id != self.company_id:
            raise ValidationError('Tag assignment tag company mismatch.')

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
