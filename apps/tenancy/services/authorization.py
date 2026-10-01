from django.db.models import F

from apps.tenancy.models import CompanyMembership, CompanyRolePermission, PermissionDefinition
from apps.tenancy.services.access import active_membership_for_user, default_company_for_user
from .permission_catalog import ROLE_GRANTS, default_scope, PERMISSION_SPECS

SCOPE_WEIGHT = {'own': 1, 'assigned': 2, 'all': 3}


def _legacy_grants(membership):
    specs = {item['code']: item for item in PERMISSION_SPECS}
    return {
        code: default_scope(membership.role, specs[code])
        for code in ROLE_GRANTS.get(membership.role, set())
    }


def effective_permission_grants(user, company=None):
    company = company or default_company_for_user(user)
    if not company:
        return {}, None
    membership = active_membership_for_user(user)
    if membership and membership.company_id != company.pk:
        membership = CompanyMembership.objects.filter(
            company=company, user=user, is_active=True,
        ).first()
    if not membership:
        if user.is_superuser:
            return {code: 'all' for code in PermissionDefinition.objects.filter(is_active=True).values_list('code', flat=True)}, None
        return {}, None

    rows = CompanyRolePermission.objects.filter(
        role__membership_assignments__membership=membership,
        role__membership_assignments__company=company,
        role__is_active=True,
        permission__is_active=True,
    ).values_list('permission__code', 'record_scope')
    grants = {}
    for code, scope in rows:
        if SCOPE_WEIGHT[scope] > SCOPE_WEIGHT.get(grants.get(code), 0):
            grants[code] = scope
    return (grants or _legacy_grants(membership)), membership


def has_company_permission(user, permission_code, company=None):
    grants, _ = effective_permission_grants(user, company)
    return permission_code in grants


def permission_scope(user, permission_code, company=None):
    grants, _ = effective_permission_grants(user, company)
    return grants.get(permission_code)


def bump_authorization_version(membership):
    CompanyMembership.objects.filter(pk=membership.pk).update(
        authorization_version=F('authorization_version') + 1,
    )
    membership.refresh_from_db(fields=['authorization_version'])
