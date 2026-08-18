from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register('products',        views.ProductViewSet,               basename='products')
router.register('inquiries',       views.InquiryViewSet,               basename='inquiries')
router.register('inquiry-products', views.InquiryProductViewSet,       basename='inquiry-products')
router.register('non-inventory-products', views.NonInventoryProductViewSet, basename='non-inventory-products')
router.register('classifications', views.MessageClassificationViewSet, basename='classifications')
router.register('prompts',         views.PromptConfigViewSet,          basename='prompts')
router.register('agent-logs',     views.AgentCallLogViewSet,          basename='agent-logs')
router.register('ai-parsing-logs', views.AiParsingLogViewSet,         basename='ai-parsing-logs')
router.register('ai-parse-v2-logs', views.AiParseV2LogViewSet,        basename='ai-parse-v2-logs')
router.register('buying-inquiries', views.BuyingInquiryViewSet,       basename='buying-inquiries')
router.register('selling-offers',   views.SellingOfferViewSet,        basename='selling-offers')
router.register('supplier-quotes',  views.SupplierQuoteViewSet,       basename='supplier-quotes')
router.register('reports',          views.ReportViewSet,              basename='reports')
router.register('trading-settings', views.TradingSettingsViewSet,     basename='trading-settings')
router.register('product-price-update', views.ProductPriceUpdateViewSet, basename='product-price-update')
router.register('automation-rules', views.AutomationRuleViewSet, basename='automation-rules')
router.register('automated-price-captures', views.AutomatedPriceCaptureViewSet, basename='automated-price-captures')

urlpatterns = router.urls
