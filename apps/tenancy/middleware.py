from apps.tenancy.models import Company
from apps.tenancy.services.access import can_user_access_company, default_company_for_user


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
