import logging

from apps.tenancy.models import Company
from django.http import JsonResponse

from apps.tenancy.models import CompanyMembership
from apps.tenancy.services.access import (
    active_membership_for_user,
    can_user_access_company,
    default_company_for_user,
)

logger = logging.getLogger(__name__)


class ActiveCompanyMiddleware:
    SESSION_KEY = 'active_company_id'

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, 'user', None)
        if user and user.is_authenticated:
            company = None
            company_id = request.session.get(self.SESSION_KEY)
            if company_id and can_user_access_company(user, company_id):
                user.active_company = Company.objects.filter(pk=company_id, is_active=True).first()
                company = user.active_company
            if company is None:
                company = default_company_for_user(user)
                user.active_company = company
                request.session[self.SESSION_KEY] = company.pk if company else None
        return self.get_response(request)


class TenantRoleMiddleware:
    """Enforce the role matrix for API endpoints, including function-based views."""

    ADMIN_PREFIXES = (
        '/api/accounts/',
        '/api/ai-providers/',
        '/api/kiwi-routers/',
        '/api/admin/',
    )
    MANAGER_PREFIXES = (
        '/api/prompts/',
        '/api/trading-settings/',
        '/api/automation-rules/',
        '/api/product-price-update/',
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, 'user', None)
        path = request.path
        if (
            not path.startswith('/api/')
            or path.startswith('/api/auth/')
            or path.startswith('/api/internal/')
            or not user
            or not user.is_authenticated
        ):
            return self.get_response(request)

        company = default_company_for_user(user)
        if not company:
            return JsonResponse({'detail': 'No accessible company is selected.'}, status=403)
        if company.validity_status != 'valid' and not company.enforce_validity_period:
            logger.warning(
                'Company validity observation | company_id=%s status=%s path=%s',
                company.pk, company.validity_status, path,
            )
        if not company.access_is_valid:
            return JsonResponse({
                'detail': 'Company access is outside its enforced validity period.',
                'validity_status': company.validity_status,
            }, status=403)

        membership = active_membership_for_user(user)
        role = membership.role if membership else (
            CompanyMembership.ROLE_SUPER_USER if user.is_superuser else ''
        )
        if request.method in {'GET', 'HEAD', 'OPTIONS'}:
            return self.get_response(request)
        if role == CompanyMembership.ROLE_VIEWER:
            return JsonResponse({'detail': 'Viewer access is read-only.'}, status=403)
        if path.startswith(self.ADMIN_PREFIXES) and role not in {
            CompanyMembership.ROLE_SUPER_USER, CompanyMembership.ROLE_ADMIN,
        }:
            return JsonResponse({'detail': 'Company admin access required.'}, status=403)
        if path.startswith(self.MANAGER_PREFIXES) and role not in {
            CompanyMembership.ROLE_SUPER_USER,
            CompanyMembership.ROLE_ADMIN,
            CompanyMembership.ROLE_MANAGER,
        }:
            return JsonResponse({'detail': 'Company manager access required.'}, status=403)
        if request.method == 'DELETE' and role not in {
            CompanyMembership.ROLE_SUPER_USER,
            CompanyMembership.ROLE_ADMIN,
            CompanyMembership.ROLE_MANAGER,
        }:
            return JsonResponse({'detail': 'Company manager access required.'}, status=403)
        return self.get_response(request)
