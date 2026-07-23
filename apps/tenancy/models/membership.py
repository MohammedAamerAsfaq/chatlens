from django.conf import settings
from django.db import models


class CompanyMembership(models.Model):
    ROLE_SUPER_USER = 'super_user'
    ROLE_ADMIN = 'admin'
    ROLE_MANAGER = 'manager'
    ROLE_USER = 'user'
    ROLE_VIEWER = 'viewer'

    ROLE_CHOICES = [
        (ROLE_SUPER_USER, 'Super User'),
        (ROLE_ADMIN, 'Admin'),
        (ROLE_MANAGER, 'Manager'),
        (ROLE_USER, 'User'),
        (ROLE_VIEWER, 'Viewer'),
    ]

    company = models.ForeignKey(
        'tenancy.Company',
        on_delete=models.CASCADE,
        related_name='memberships',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='company_memberships',
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    is_active = models.BooleanField(default=True)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'tenant_company_membership'
        ordering = ['company__name', 'user__username']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'user'],
                name='unique_company_membership',
            ),
        ]

    def __str__(self):
        return f'{self.company} -> {self.user} ({self.role})'

