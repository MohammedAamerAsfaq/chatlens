from django.urls import path

from .views import (
    geography_source, locations, overview, sync_geography, test_geography_source,
)
from .views_google_maps import (
    google_maps_source, locality_suggestions, resolve_locality, test_google_maps_source,
)

urlpatterns = [
    path('integrations/overview/', overview, name='integrations-overview'),
    path('integrations/geography-source/', geography_source, name='integrations-geography-source'),
    path('integrations/geography-source/test/', test_geography_source, name='integrations-geography-test'),
    path('integrations/geography-source/sync/', sync_geography, name='integrations-geography-sync'),
    path('integrations/locations/', locations, name='integrations-locations'),
    path('integrations/google-maps/', google_maps_source, name='integrations-google-maps'),
    path('integrations/google-maps/test/', test_google_maps_source, name='integrations-google-maps-test'),
    path(
        'integrations/google-maps/localities/<int:locality_id>/suggestions/',
        locality_suggestions, name='integrations-google-maps-locality-suggestions',
    ),
    path(
        'integrations/google-maps/localities/<int:locality_id>/resolve/',
        resolve_locality, name='integrations-google-maps-locality-resolve',
    ),
]
