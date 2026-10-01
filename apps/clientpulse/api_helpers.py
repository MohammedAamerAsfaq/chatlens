from django.db.models import Q
from rest_framework import status
from rest_framework.response import Response

from apps.clientpulse.models import ClientProfile
from apps.tenancy.services.access import active_membership_for_user, default_company_for_user
from apps.tenancy.services.authorization import permission_scope


def denied(request, permission_code):
    return None if permission_scope(request.user, permission_code) else Response(
        {'detail': 'You do not have permission to perform this action.'},
        status=status.HTTP_403_FORBIDDEN,
    )


def scoped_profiles(request, permission_code='clientpulse.clients.view'):
    company = default_company_for_user(request.user)
    if not company:
        return ClientProfile.objects.none()
    queryset = ClientProfile.objects.filter(company=company)
    scope = permission_scope(request.user, permission_code, company)
    membership = active_membership_for_user(request.user)
    if scope == 'all':
        return queryset
    if scope == 'assigned' and membership:
        return queryset.filter(owner=membership)
    if scope == 'own':
        return queryset.filter(Q(created_by=request.user) | Q(owner=membership))
    return queryset.none()


def profile_or_none(request, profile_id, permission_code='clientpulse.clients.view'):
    return scoped_profiles(request, permission_code).filter(pk=profile_id).first()


def parse_bool(value, default=False):
    if value is None:
        return default
    return value in (True, 1, '1', 'true', 'yes', 'on')
