from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register('products',        views.ProductViewSet,               basename='products')
router.register('inquiries',       views.InquiryViewSet,               basename='inquiries')
router.register('classifications', views.MessageClassificationViewSet, basename='classifications')
router.register('prompts',         views.PromptConfigViewSet,          basename='prompts')
router.register('agent-logs',     views.AgentCallLogViewSet,          basename='agent-logs')

urlpatterns = router.urls
