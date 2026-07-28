from django.contrib import admin
from django.urls import include, path, re_path

from apps.chatlens_core.views import frontend_spa

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('apps.api.urls')),
    path('api/', include('apps.ai_providers.urls')),
    path('api/', include('apps.message_intelligence.urls')),
    path('api/', include('apps.trading.urls')),
    path('', include('apps.whatsapp_bridge.urls')),
    path('', frontend_spa, name='frontend-root'),
    re_path(
        r'^(?!api/|admin/|static/|media/|worker-media/)(?P<path>.*)$',
        frontend_spa,
        name='frontend-spa',
    ),
]
