from django.urls import path

from .views import (
    geography_source, locations, overview, sync_geography, test_geography_source,
)

urlpatterns = [
    path('integrations/overview/', overview, name='integrations-overview'),
    path('integrations/geography-source/', geography_source, name='integrations-geography-source'),
    path('integrations/geography-source/test/', test_geography_source, name='integrations-geography-test'),
    path('integrations/geography-source/sync/', sync_geography, name='integrations-geography-sync'),
    path('integrations/locations/', locations, name='integrations-locations'),
]
