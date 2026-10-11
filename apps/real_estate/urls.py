from rest_framework.routers import DefaultRouter

from .views_inventory import ListingViewSet, PropertyAddressViewSet, PropertyMediaViewSet, PropertyViewSet
from .views_opportunities import CandidateViewSet, OpportunityViewSet, RequirementViewSet

router = DefaultRouter()
router.register('real-estate/properties', PropertyViewSet, basename='real-estate-properties')
router.register('real-estate/property-addresses', PropertyAddressViewSet, basename='real-estate-property-addresses')
router.register('real-estate/property-media', PropertyMediaViewSet, basename='real-estate-property-media')
router.register('real-estate/listings', ListingViewSet, basename='real-estate-listings')
router.register('real-estate/opportunities', OpportunityViewSet, basename='real-estate-opportunities')
router.register('real-estate/requirements', RequirementViewSet, basename='real-estate-requirements')
router.register('real-estate/candidates', CandidateViewSet, basename='real-estate-candidates')

urlpatterns = router.urls
