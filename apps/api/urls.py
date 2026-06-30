from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import WhatsAppAccountViewSet, ChatViewSet, SyncLogViewSet, DroppedMessageViewSet

router = DefaultRouter()
router.register('accounts', WhatsAppAccountViewSet, basename='account')
router.register('chats', ChatViewSet, basename='chat')
router.register('activity', SyncLogViewSet, basename='activity')
router.register('dropped-messages', DroppedMessageViewSet, basename='dropped-messages')

urlpatterns = [
    path('', include(router.urls)),
]
