from django.utils import timezone
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from .models import ApiKey

LAST_USED_REFRESH_SECONDS = 60


class ApiConsumerPrincipal:
    """Non-human request principal for an authenticated API key — not a Django User."""

    is_authenticated = True
    is_anonymous = False
    pk = None

    def __init__(self, api_key):
        self.api_key = api_key
        self.company = api_key.company

    def __str__(self):
        return f'apikey:{self.api_key.key_prefix}'


class ApiKeyAuthentication(BaseAuthentication):
    """Authenticate external callers via `Authorization: Api-Key <prefix>.<secret>`."""

    keyword = 'Api-Key'

    def authenticate(self, request):
        header = request.headers.get('Authorization', '')
        if not header:
            return None
        parts = header.split(' ', 1)
        if len(parts) != 2 or parts[0] != self.keyword:
            return None
        token = parts[1].strip()
        if '.' not in token:
            raise AuthenticationFailed('Invalid API key.')
        key_prefix, _, secret = token.partition('.')

        api_key = ApiKey.objects.select_related('company').filter(key_prefix=key_prefix).first()
        if not api_key or not api_key.verify_secret(secret) or not api_key.is_usable:
            raise AuthenticationFailed('Invalid API key.')
        if not api_key.company.access_is_valid:
            raise AuthenticationFailed('Invalid API key.')

        self._touch_last_used(api_key)
        return ApiConsumerPrincipal(api_key), api_key

    def _touch_last_used(self, api_key):
        now = timezone.now()
        if api_key.last_used_at and (now - api_key.last_used_at).total_seconds() < LAST_USED_REFRESH_SECONDS:
            return
        ApiKey.objects.filter(pk=api_key.pk).update(last_used_at=now)

    def authenticate_header(self, request):
        return self.keyword
