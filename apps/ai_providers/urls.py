from rest_framework.routers import DefaultRouter
from .views import AIProviderConfigViewSet, KiwiRouterViewSet
from .views_operations import AIOperationsViewSet

router = DefaultRouter()
router.register(r'ai-providers', AIProviderConfigViewSet, basename='ai-provider')
router.register(r'kiwi-routers', KiwiRouterViewSet, basename='kiwi-router')
router.register(r'ai-operations', AIOperationsViewSet, basename='ai-operations')

urlpatterns = router.urls
