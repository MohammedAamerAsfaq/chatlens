from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    WhatsAppAccountViewSet, ChatViewSet, SyncLogViewSet, DroppedMessageViewSet,
    ContactViewSet, GroupViewSet, WorkerAlertViewSet, StuckReceiptViewSet,
    UnresolvedMessageViewSet,
    auth_login_view, auth_logout_view, auth_me_view, auth_select_company_view,
    admin_companies_view, admin_company_enroll_view, admin_company_users_view,
)

router = DefaultRouter()
router.register('accounts', WhatsAppAccountViewSet, basename='account')
router.register('chats', ChatViewSet, basename='chat')
router.register('activity', SyncLogViewSet, basename='activity')
router.register('dropped-messages', DroppedMessageViewSet, basename='dropped-messages')
router.register('worker-alerts', WorkerAlertViewSet, basename='worker-alerts')
router.register('stuck-receipts', StuckReceiptViewSet, basename='stuck-receipts')
router.register('unresolved-messages', UnresolvedMessageViewSet, basename='unresolved-messages')
router.register('contacts', ContactViewSet, basename='contacts')
router.register('groups', GroupViewSet, basename='groups')

urlpatterns = [
    path('', include(router.urls)),
    path('auth/login/',  auth_login_view,  name='auth-login'),
    path('auth/logout/', auth_logout_view, name='auth-logout'),
    path('auth/me/',     auth_me_view,     name='auth-me'),
    path('auth/select-company/', auth_select_company_view, name='auth-select-company'),
    path('admin/companies/', admin_companies_view, name='admin-companies'),
    path('admin/companies/enroll/', admin_company_enroll_view, name='admin-company-enroll'),
    path('admin/users/', admin_company_users_view, name='admin-company-users'),
]
