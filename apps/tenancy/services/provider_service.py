from apps.tenancy.models import ConnectionProvider


class ProviderService:
    def default_provider_for_channel(self, channel: str) -> ConnectionProvider:
        return ConnectionProvider.objects.get(channel=channel, is_default_for_channel=True)

