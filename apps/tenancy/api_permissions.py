from rest_framework import permissions

from apps.tenancy.services.access import default_company_for_user
from apps.tenancy.services.authorization import has_company_permission


class CompanyPermissionRequired(permissions.BasePermission):
    """Resolve a view's permission code against the active company membership."""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        company = default_company_for_user(request.user)
        if not company or not company.access_is_valid:
            return False
        code = view.permission_code_for(request)
        return bool(code and has_company_permission(request.user, code, company))
