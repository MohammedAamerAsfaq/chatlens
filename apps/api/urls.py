from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    WhatsAppAccountViewSet, ChatViewSet, SyncLogViewSet, DroppedMessageViewSet,
    ContactViewSet, GroupViewSet,
    auth_login_view, auth_logout_view, auth_me_view,
)

router = DefaultRouter()
router.register('accounts', WhatsAppAccountViewSet, basename='account')
router.register('chats', ChatViewSet, basename='chat')
router.register('activity', SyncLogViewSet, basename='activity')
router.register('dropped-messages', DroppedMessageViewSet, basename='dropped-messages')
router.register('contacts', ContactViewSet, basename='contacts')
router.register('groups', GroupViewSet, basename='groups')

urlpatterns = [
    path('', include(router.urls)),
    path('auth/login/',  auth_login_view,  name='auth-login'),
    path('auth/logout/', auth_logout_view, name='auth-logout'),
    path('auth/me/',     auth_me_view,     name='auth-me'),
]
