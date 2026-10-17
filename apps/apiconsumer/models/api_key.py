import hashlib
import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone


class ApiKey(models.Model):
    STATUS_ACTIVE = 'active'
    STATUS_REVOKED = 'revoked'
    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Active'),
        (STATUS_REVOKED, 'Revoked'),
    ]

    SCOPE_DATA_READ = 'data:read'
    SCOPE_MESSAGES_SEND = 'messages:send'
    SCOPE_WEBHOOKS_MANAGE = 'webhooks:manage'
    SCOPE_CHOICES = [
        (SCOPE_DATA_READ, 'Read company data'),
        (SCOPE_MESSAGES_SEND, 'Send outbound messages'),
        (SCOPE_WEBHOOKS_MANAGE, 'Manage webhook subscriptions'),
    ]

    company = models.ForeignKey('tenancy.Company', on_delete=models.CASCADE, related_name='api_keys')
    name = models.CharField(max_length=255)
    key_prefix = models.CharField(max_length=16, unique=True, db_index=True)
    secret_hash = models.CharField(max_length=64)
    scopes = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='api_keys_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'apiconsumer_api_key'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['company', 'status'])]

    def __str__(self):
        return f'{self.name} ({self.key_prefix})'

    @staticmethod
    def _hash_secret(secret):
        return hashlib.sha256(secret.encode('utf-8')).hexdigest()

    @classmethod
    def generate(cls, *, company, name, scopes, created_by=None, expires_at=None):
        key_prefix = secrets.token_hex(6)
        secret = secrets.token_urlsafe(32)
        instance = cls.objects.create(
            company=company, name=name, key_prefix=key_prefix,
            secret_hash=cls._hash_secret(secret), scopes=list(scopes),
            created_by=created_by, expires_at=expires_at,
        )
        return instance, f'{key_prefix}.{secret}'

    def verify_secret(self, secret):
        import hmac
        return hmac.compare_digest(self._hash_secret(secret), self.secret_hash)

    def revoke(self):
        self.status = self.STATUS_REVOKED
        self.revoked_at = timezone.now()
        self.save(update_fields=['status', 'revoked_at'])

    @property
    def is_usable(self):
        if self.status != self.STATUS_ACTIVE:
            return False
        if self.expires_at and self.expires_at <= timezone.now():
            return False
        return True
