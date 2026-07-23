from django.db import models


class AccountEndpoint(models.Model):
    TYPE_PHONE = 'phone'
    TYPE_EMAIL = 'email'
    TYPE_HANDLE = 'handle'
    TYPE_DEVICE = 'device'

    ENDPOINT_TYPE_CHOICES = [
        (TYPE_PHONE, 'Phone'),
        (TYPE_EMAIL, 'Email'),
        (TYPE_HANDLE, 'Handle / Username'),
        (TYPE_DEVICE, 'Device Session'),
    ]

    communication_account = models.ForeignKey(
        'tenancy.CommunicationAccount',
        on_delete=models.CASCADE,
        related_name='endpoints',
    )
    endpoint_type = models.CharField(max_length=20, choices=ENDPOINT_TYPE_CHOICES)
    value = models.CharField(max_length=255)
    is_primary = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    metadata = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'tenant_account_endpoint'
        ordering = ['communication_account__name', '-is_primary', 'value']

    def __str__(self):
        return self.value

