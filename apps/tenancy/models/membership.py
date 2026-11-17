from django.conf import settings
from django.db import models


class CompanyMembership(models.Model):
    """A user's place in a company. What they may do comes from the roles assigned to
    the membership (MembershipRoleAssignment), never from a field on this row."""

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
    is_active = models.BooleanField(default=True)
    authorization_version = models.PositiveIntegerField(default=1)
    joined_at = models.DateTimeField(auto_now_add=True)
    # Set when an admin removes the user from the company (Users page → Remove). The row
    # stays so their history keeps its name; removed members never come back active.
    removed_at = models.DateTimeField(null=True, blank=True)
    removed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
    )

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
        return f'{self.company} -> {self.user}'
