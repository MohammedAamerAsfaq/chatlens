from django.conf import settings
from rest_framework.throttling import SimpleRateThrottle


class ApiKeyRateThrottle(SimpleRateThrottle):
    """Rate-limit external calls per API key rather than per Django user/IP."""

    scope = 'apiconsumer'

    def get_rate(self):
        return getattr(settings, 'APICONSUMER_DEFAULT_RATE', '60/min')

    def get_cache_key(self, request, view):
        api_key = getattr(request, 'auth', None)
        if api_key is None:
            return None
        return self.cache_format % {'scope': self.scope, 'ident': api_key.pk}
