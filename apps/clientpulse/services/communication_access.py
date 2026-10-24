from apps.tenancy.services.access import visible_accounts_queryset
from apps.whatsapp_bridge.models import WhatsAppAccount


def visible_clientpulse_accounts(user, company):
    """Return company WhatsApp accounts visible in ClientPulse to this user."""
    queryset = WhatsAppAccount.objects.filter(
        communication_account__company=company,
    )
    return visible_accounts_queryset(user, queryset)


def visible_clientpulse_account_ids(user, company):
    return set(
        visible_clientpulse_accounts(user, company).values_list('pk', flat=True),
    )
