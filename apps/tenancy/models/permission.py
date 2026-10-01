from django.db import models


class PermissionDefinition(models.Model):
    code = models.CharField(max_length=120, unique=True)
    area = models.CharField(max_length=50, db_index=True)
    label = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    supports_scope = models.BooleanField(default=False)
    is_sensitive = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tenant_permission_definition'
        ordering = ['area', 'code']

    def __str__(self):
        return self.code


class CompanyRolePermission(models.Model):
    SCOPE_OWN = 'own'
    SCOPE_ASSIGNED = 'assigned'
    SCOPE_ALL = 'all'
    SCOPE_CHOICES = [
        (SCOPE_OWN, 'Own records'),
        (SCOPE_ASSIGNED, 'Assigned records'),
        (SCOPE_ALL, 'All company records'),
    ]

    company = models.ForeignKey('tenancy.Company', on_delete=models.CASCADE, related_name='role_permissions')
    role = models.ForeignKey('tenancy.CompanyRole', on_delete=models.CASCADE, related_name='permission_grants')
    permission = models.ForeignKey(PermissionDefinition, on_delete=models.CASCADE, related_name='role_grants')
    record_scope = models.CharField(max_length=20, choices=SCOPE_CHOICES, default=SCOPE_ALL)
    created_by = models.ForeignKey(
        'auth.User', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='company_role_permissions_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'tenant_company_role_permission'
        constraints = [
            models.UniqueConstraint(fields=['role', 'permission'], name='unique_company_role_permission'),
        ]
        indexes = [models.Index(fields=['company', 'permission'])]

    def __str__(self):
        return f'{self.role}: {self.permission.code} ({self.record_scope})'
