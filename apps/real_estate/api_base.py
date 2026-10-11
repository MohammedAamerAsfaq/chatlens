from rest_framework import permissions, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.pagination import PageNumberPagination

from apps.tenancy.models import Company
from apps.tenancy.services.access import default_company_for_user
from apps.tenancy.services.authorization import has_company_permission, permission_scope


class RealEstatePagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = 'page_size'
    max_page_size = 100


class RealEstatePermission(permissions.BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        company = default_company_for_user(request.user)
        if not company or not company.access_is_valid:
            return False
        if company.industry_type != Company.INDUSTRY_REAL_ESTATE and company.company_type != Company.TYPE_CONTROL:
            return False
        code = view.permission_code_for(request)
        return bool(code and has_company_permission(request.user, code, company))

    def has_object_permission(self, request, view, obj):
        company = default_company_for_user(request.user)
        if not company or getattr(obj, 'company_id', None) != company.pk:
            return False
        scope = permission_scope(request.user, view.permission_code_for(request), company)
        if scope == 'assigned' and view.scope_filter_field:
            current = obj
            for part in view.scope_filter_field.split('__'):
                current = getattr(current, part, None)
            return current == request.user.pk
        return True


class CompanyOwnedViewSet(viewsets.ModelViewSet):
    permission_classes = [RealEstatePermission]
    pagination_class = RealEstatePagination
    read_permission = ''
    write_permission = ''
    scope_filter_field = ''

    def active_company(self):
        company = default_company_for_user(self.request.user)
        if not company:
            raise PermissionDenied('No active company is selected.')
        return company

    def permission_code_for(self, request):
        return self.read_permission if request.method in permissions.SAFE_METHODS else self.write_permission

    def get_queryset(self):
        company = self.active_company()
        qs = self.queryset.filter(company=company)
        scope = permission_scope(self.request.user, self.permission_code_for(self.request), company)
        if scope == 'assigned' and self.scope_filter_field:
            qs = qs.filter(**{self.scope_filter_field: self.request.user.pk})
        return qs

    def perform_create(self, serializer):
        serializer.save(company=self.active_company())
