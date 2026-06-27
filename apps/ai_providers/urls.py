from rest_framework.routers import DefaultRouter
from .views import AIProviderConfigViewSet

router = DefaultRouter()
router.register(r'ai-providers', AIProviderConfigViewSet, basename='ai-provider')

urlpatterns = router.urls
