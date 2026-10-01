from django.db import models


class CompanyRole(models.Model):
    company = models.ForeignKey('tenancy.Company', on_delete=models.CASCADE, related_name='roles')
    key = models.SlugField(max_length=50)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_system_role = models.BooleanField(default=False)
    is_owner_role = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        'auth.User', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='company_roles_created',
    )
    updated_by = models.ForeignKey(
        'auth.User', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='company_roles_updated',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tenant_company_role'
        ordering = ['company__name', 'name']
        constraints = [
            models.UniqueConstraint(fields=['company', 'key'], name='unique_company_role_key'),
            models.UniqueConstraint(
                fields=['company'], condition=models.Q(is_owner_role=True),
                name='unique_company_owner_role',
            ),
        ]

    def __str__(self):
        return f'{self.company}: {self.name}'


class MembershipRoleAssignment(models.Model):
    SOURCE_LEGACY = 'legacy'
    SOURCE_MANUAL = 'manual'
    SOURCE_CHOICES = [(SOURCE_LEGACY, 'Legacy role'), (SOURCE_MANUAL, 'Manual')]

    company = models.ForeignKey('tenancy.Company', on_delete=models.CASCADE, related_name='role_assignments')
    membership = models.ForeignKey(
        'tenancy.CompanyMembership', on_delete=models.CASCADE, related_name='role_assignments',
    )
    role = models.ForeignKey(CompanyRole, on_delete=models.CASCADE, related_name='membership_assignments')
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default=SOURCE_MANUAL)
    assigned_by = models.ForeignKey(
        'auth.User', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='company_role_assignments_created',
    )
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'tenant_membership_role_assignment'
        constraints = [
            models.UniqueConstraint(fields=['membership', 'role'], name='unique_membership_role_assignment'),
        ]
        indexes = [models.Index(fields=['company', 'membership'])]

    def __str__(self):
        return f'{self.membership} -> {self.role.name}'
