from django.core.exceptions import ValidationError
from django.db import models


class CommunicationAccountAssignment(models.Model):
    ACCESS_OWNER = 'owner'
    ACCESS_MEMBER = 'member'
    ACCESS_CHOICES = [
        (ACCESS_OWNER, 'Account owner'),
        (ACCESS_MEMBER, 'Assigned member'),
    ]

    company = models.ForeignKey(
        'tenancy.Company', on_delete=models.CASCADE,
        related_name='communication_account_assignments',
    )
    communication_account = models.ForeignKey(
        'tenancy.CommunicationAccount', on_delete=models.CASCADE,
        related_name='user_assignments',
    )
    membership = models.ForeignKey(
        'tenancy.CompanyMembership', on_delete=models.CASCADE,
        related_name='communication_account_assignments',
    )
    access_level = models.CharField(
        max_length=20, choices=ACCESS_CHOICES, default=ACCESS_MEMBER,
    )
    is_active = models.BooleanField(default=True)
    assigned_by = models.ForeignKey(
        'auth.User', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='communication_account_assignments_created',
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tenant_communication_account_assignment'
        constraints = [
            models.UniqueConstraint(
                fields=['communication_account', 'membership'],
                name='unique_communication_account_assignment',
            ),
        ]
        indexes = [
            models.Index(
                fields=['company', 'membership', 'is_active'],
                name='tenant_comm_company_806a23_idx',
            ),
            models.Index(
                fields=['company', 'communication_account', 'is_active'],
                name='tenant_comm_company_ef35b2_idx',
            ),
        ]

    def clean(self):
        super().clean()
        if self.communication_account_id and self.membership_id:
            if self.communication_account.company_id != self.membership.company_id:
                raise ValidationError('Account and membership must belong to the same company.')
            if self.company_id != self.communication_account.company_id:
                raise ValidationError('Assignment company must match the communication account company.')
            if self.company_id != self.membership.company_id:
                raise ValidationError('Assignment company must match the membership company.')

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.membership} -> {self.communication_account}'
