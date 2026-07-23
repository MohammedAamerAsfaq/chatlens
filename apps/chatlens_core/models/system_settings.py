from django.db import models


class SystemSettings(models.Model):
    company = models.ForeignKey(
        'tenancy.Company',
        null=True, blank=True,
        on_delete=models.CASCADE,
        related_name='system_settings',
    )
    key = models.CharField(max_length=255)
    value = models.TextField(blank=True)
    description = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'chatlens_system_settings'
        verbose_name = 'System Setting'
        verbose_name_plural = 'System Settings'
        constraints = [
            models.UniqueConstraint(fields=['company', 'key'], name='system_setting_company_key_uniq'),
        ]

    def __str__(self):
        return f"{self.key} = {self.value}"
