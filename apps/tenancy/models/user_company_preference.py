from django.conf import settings
from django.db import models


class UserCompanyPreference(models.Model):
    THEME_CHATLENS = 'chatlens'
    THEME_INSPINIA = 'inspinia'
    THEME_CHOICES = [
        (THEME_CHATLENS, 'ChatLens'),
        (THEME_INSPINIA, 'Inspinia'),
    ]

    company = models.ForeignKey(
        'tenancy.Company', on_delete=models.CASCADE, related_name='user_preferences',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='company_preferences',
    )
    ui_theme = models.CharField(
        max_length=20, choices=THEME_CHOICES, default=THEME_CHATLENS,
    )
    inspinia_config = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tenant_user_company_preference'
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'user'], name='unique_user_company_preference',
            ),
        ]

    def __str__(self):
        return f'{self.company} -> {self.user} ({self.ui_theme})'
