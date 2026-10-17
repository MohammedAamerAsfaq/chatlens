from rest_framework.routers import DefaultRouter

from .views_inventory import (
    ListingViewSet, PropertyAddressViewSet, PropertyDevelopmentViewSet,
    PropertyMediaViewSet, PropertyTypeViewSet,
    PropertyViewSet,
)
from .views_opportunities import CandidateViewSet, OpportunityViewSet, RequirementViewSet
from .views_mock_source import MockSourceRecordViewSet
from .views_mock_inquiry import MockInquiryViewSet
from .views_prompts import RealEstatePromptViewSet

router = DefaultRouter()
router.register('real-estate/properties', PropertyViewSet, basename='real-estate-properties')
router.register('real-estate/property-types', PropertyTypeViewSet, basename='real-estate-property-types')
router.register('real-estate/property-addresses', PropertyAddressViewSet, basename='real-estate-property-addresses')
router.register('real-estate/property-developments', PropertyDevelopmentViewSet, basename='real-estate-property-developments')
router.register('real-estate/property-media', PropertyMediaViewSet, basename='real-estate-property-media')
router.register('real-estate/listings', ListingViewSet, basename='real-estate-listings')
router.register('real-estate/opportunities', OpportunityViewSet, basename='real-estate-opportunities')
router.register('real-estate/requirements', RequirementViewSet, basename='real-estate-requirements')
router.register('real-estate/candidates', CandidateViewSet, basename='real-estate-candidates')
router.register('real-estate/mock-source-records', MockSourceRecordViewSet, basename='real-estate-mock-source-records')
router.register('real-estate/mock-inquiries', MockInquiryViewSet, basename='real-estate-mock-inquiries')
router.register('real-estate/prompts', RealEstatePromptViewSet, basename='real-estate-prompts')

urlpatterns = router.urls
