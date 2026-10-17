from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .management_views import ApiKeyViewSet

router = DefaultRouter()
router.register('keys', ApiKeyViewSet, basename='apiconsumer-key')

urlpatterns = [
    path('', include(router.urls)),
]
