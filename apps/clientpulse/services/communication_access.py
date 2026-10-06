from apps.tenancy.models import CompanyMembership
from apps.tenancy.services.access import active_membership_for_user
from apps.whatsapp_bridge.models import WhatsAppAccount


ADMIN_ROLES = {
    CompanyMembership.ROLE_SUPER_USER,
    CompanyMembership.ROLE_ADMIN,
}


def visible_clientpulse_accounts(user, company):
    """Return company WhatsApp accounts visible in ClientPulse to this user."""
    queryset = WhatsAppAccount.objects.filter(
        communication_account__company=company,
    )
    membership = active_membership_for_user(user)
    if user.is_superuser or (membership and membership.role in ADMIN_ROLES):
        return queryset
    return queryset.filter(owner=user)
