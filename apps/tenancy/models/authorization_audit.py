from django.db import models


class AuthorizationAuditEvent(models.Model):
    company = models.ForeignKey('tenancy.Company', on_delete=models.CASCADE, related_name='authorization_events')
    actor = models.ForeignKey(
        'auth.User', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='authorization_events_performed',
    )
    target_membership = models.ForeignKey(
        'tenancy.CompanyMembership', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='authorization_events',
    )
    target_role = models.ForeignKey(
        'tenancy.CompanyRole', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='authorization_events',
    )
    event_type = models.CharField(max_length=80, db_index=True)
    before_snapshot = models.JSONField(default=dict, blank=True)
    after_snapshot = models.JSONField(default=dict, blank=True)
    correlation_id = models.CharField(max_length=255, blank=True, db_index=True)
    request_metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'tenant_authorization_audit_event'
        ordering = ['-created_at', '-id']
        indexes = [models.Index(fields=['company', 'created_at'])]

    def __str__(self):
        return f'{self.company}: {self.event_type}'
