from rest_framework import permissions

from apps.tenancy.services.access import active_membership_for_user, default_company_for_user
from apps.tenancy.services.authorization import has_company_permission

# A view's read_permission may be ANY_MEMBER: every active member of the company may read.
ANY_MEMBER = 'any-member'

# The product catalog is read by the trading board, campaigns and manual inquiries, not
# only the Products pages, so any of those features' view permissions may read it.
# Changing the catalog still needs trading.products.manage.
CATALOG_READ_PERMISSIONS = ('trading.products.view', 'trading.board.view', 'campaigns.campaigns.view')


def _required_codes(view, request):
    if hasattr(view, 'permission_code_for'):
        return view.permission_code_for(request)
    attribute = 'read_permission' if request.method in permissions.SAFE_METHODS else 'write_permission'
    # No declared permission means nobody passes: a view must say what it needs.
    return getattr(view, attribute, None)


class CompanyPermissionRequired(permissions.BasePermission):
    """Resolve a view's permission code against the active company membership.

    A view either implements permission_code_for(request), or declares read_permission
    (safe methods) and write_permission (every change). Either may be one code, a tuple
    of codes of which any one is enough, or ANY_MEMBER (reads only).
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        company = default_company_for_user(request.user)
        if not company or not company.access_is_valid:
            return False
        codes = _required_codes(view, request)
        if not codes:
            return False
        if codes == ANY_MEMBER:
            if request.method not in permissions.SAFE_METHODS:
                return False
            return bool(request.user.is_superuser or active_membership_for_user(request.user))
        if isinstance(codes, str):
            codes = (codes,)
        return any(has_company_permission(request.user, code, company) for code in codes)
