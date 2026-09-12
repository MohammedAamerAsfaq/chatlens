from rest_framework.routers import DefaultRouter
from .views import AIProviderConfigViewSet, KiwiRouterViewSet

router = DefaultRouter()
router.register(r'ai-providers', AIProviderConfigViewSet, basename='ai-provider')
router.register(r'kiwi-routers', KiwiRouterViewSet, basename='kiwi-router')

urlpatterns = router.urls
