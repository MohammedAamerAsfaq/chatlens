from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .external_views import (
    ChatViewSet, ContactViewSet, InquiryViewSet, MessageViewSet, OutboundMessageViewSet, PingView,
    ProductMentionsView, ProductViewSet, SendMessageView, WebhookDeliveryAttemptViewSet,
    WebhookSubscriptionViewSet,
)

router = DefaultRouter()
router.register('contacts', ContactViewSet, basename='external-contact')
router.register('chats', ChatViewSet, basename='external-chat')
router.register('messages', MessageViewSet, basename='external-message')
router.register('inquiries', InquiryViewSet, basename='external-inquiry')
router.register('products', ProductViewSet, basename='external-product')
router.register('outbound-messages', OutboundMessageViewSet, basename='external-outbound-message')
router.register('webhooks', WebhookSubscriptionViewSet, basename='external-webhook')

urlpatterns = [
    path('ping/', PingView.as_view(), name='external-ping'),
    path('product-mentions/', ProductMentionsView.as_view(), name='external-product-mentions'),
    path('send-message/', SendMessageView.as_view(), name='external-send-message'),
    path(
        'webhooks/<int:subscription_pk>/deliveries/',
        WebhookDeliveryAttemptViewSet.as_view({'get': 'list'}),
        name='external-webhook-deliveries',
    ),
    path('', include(router.urls)),
]
