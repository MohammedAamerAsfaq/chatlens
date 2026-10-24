from django.urls import path

from .api_users import (
    company_communication_accounts_view, company_user_communication_accounts_view,
    company_user_detail_view, company_users_view,
)
from .api_views import company_permissions_view, company_role_detail_view, company_roles_view

urlpatterns = [
    path('company/users/', company_users_view, name='company-users'),
    path('company/users/<int:membership_id>/', company_user_detail_view, name='company-user-detail'),
    path('company/communication-accounts/', company_communication_accounts_view, name='company-communication-accounts'),
    path('company/users/<int:membership_id>/communication-accounts/', company_user_communication_accounts_view, name='company-user-communication-accounts'),
    path('company/roles/', company_roles_view, name='company-roles'),
    path('company/roles/<int:role_id>/', company_role_detail_view, name='company-role-detail'),
    path('company/permissions/', company_permissions_view, name='company-permissions'),
]
