from rest_framework.permissions import BasePermission, SAFE_METHODS

from apps.tenancy.models import CompanyMembership
from apps.tenancy.services.access import active_membership_for_user


class TenantRolePermission(BasePermission):
    """Company role policy shared by operational API viewsets."""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        membership = active_membership_for_user(request.user)
        role = membership.role if membership else (
            CompanyMembership.ROLE_SUPER_USER if request.user.is_superuser else ''
        )
        if request.method in SAFE_METHODS:
            return bool(role)
        if role == CompanyMembership.ROLE_VIEWER:
            return False
        if request.method == 'DELETE':
            return role in {
                CompanyMembership.ROLE_SUPER_USER,
                CompanyMembership.ROLE_ADMIN,
                CompanyMembership.ROLE_MANAGER,
            }
        return role in {
            CompanyMembership.ROLE_SUPER_USER,
            CompanyMembership.ROLE_ADMIN,
            CompanyMembership.ROLE_MANAGER,
            CompanyMembership.ROLE_USER,
        }


class CompanyAdminPermission(BasePermission):
    """Restrict sensitive company configuration to company administrators."""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        membership = active_membership_for_user(request.user)
        role = membership.role if membership else (
            CompanyMembership.ROLE_SUPER_USER if request.user.is_superuser else ''
        )
        return role in {
            CompanyMembership.ROLE_SUPER_USER,
            CompanyMembership.ROLE_ADMIN,
        }
