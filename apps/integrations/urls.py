from django.urls import path

from .views import (
    geography_source, locations, overview, sync_geography, test_geography_source,
)
from .views_google_maps import (
    google_maps_source, locality_suggestions, resolve_locality, test_google_maps_source,
)
from .views_property_maps import (
    property_address_suggestions, property_map_config, property_place_details,
    property_reverse_geocode,
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
        'integrations/google-maps/property-map-config/', property_map_config,
        name='integrations-google-maps-property-map-config',
    ),
    path(
        'integrations/google-maps/property-address-suggestions/',
        property_address_suggestions,
        name='integrations-google-maps-property-address-suggestions',
    ),
    path(
        'integrations/google-maps/property-place-details/', property_place_details,
        name='integrations-google-maps-property-place-details',
    ),
    path(
        'integrations/google-maps/property-reverse-geocode/', property_reverse_geocode,
        name='integrations-google-maps-property-reverse-geocode',
    ),
    path(
        'integrations/google-maps/localities/<int:locality_id>/suggestions/',
        locality_suggestions, name='integrations-google-maps-locality-suggestions',
    ),
    path(
        'integrations/google-maps/localities/<int:locality_id>/resolve/',
        resolve_locality, name='integrations-google-maps-locality-resolve',
    ),
]
