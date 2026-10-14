import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth.js'
import LoginView           from '../views/LoginView.vue'
import SessionView          from '../views/SessionView.vue'
import ConversationsView    from '../views/ConversationsView.vue'
import ActivityView         from '../views/ActivityView.vue'
import StorageView          from '../views/StorageView.vue'
import MessageLogsView      from '../views/MessageLogsView.vue'
import AIProvidersView      from '../views/AIProvidersView.vue'
import DroppedMessagesView  from '../views/DroppedMessagesView.vue'
import WorkerAlertsView     from '../views/WorkerAlertsView.vue'
import BaileysEventsView    from '../views/BaileysEventsView.vue'
import StuckReceiptsView    from '../views/StuckReceiptsView.vue'
import UnresolvedMessagesView from '../views/UnresolvedMessagesView.vue'
import MessageTraceView     from '../views/MessageTraceView.vue'
import AiParsingLogView     from '../views/AiParsingLogView.vue'
import AiParseV2LogView     from '../views/AiParseV2LogView.vue'
import ContactsView         from '../views/ContactsView.vue'
import GroupsView           from '../views/GroupsView.vue'
import TradingView          from '../views/TradingView.vue'
import SellingOffersView    from '../views/SellingOffersView.vue'
import TradingAnalyticsView from '../views/TradingAnalyticsView.vue'
import ReportSummaryView    from '../views/ReportSummaryView.vue'
import InventoryProductMentionsReportView from '../views/InventoryProductMentionsReportView.vue'
import SellingOffersReportView from '../views/SellingOffersReportView.vue'
import InquiriesView        from '../views/InquiriesView.vue'
import InquiryProductsView  from '../views/InquiryProductsView.vue'
import NonInventoryProductsView from '../views/NonInventoryProductsView.vue'
import ProductsView         from '../views/ProductsView.vue'
import V2CandidateSearchView from '../views/V2CandidateSearchView.vue'
import ProductPriceUpdateView from '../views/ProductPriceUpdateView.vue'
import AutomationView from '../views/AutomationView.vue'
import AIInstructionsView   from '../views/AIInstructionsView.vue'
import V2SettingsView        from '../views/V2SettingsView.vue'
import BuyingInquiriesView  from '../views/BuyingInquiriesView.vue'
import GroupBuyingInquiriesView from '../views/GroupBuyingInquiriesView.vue'
import GroupSellingOffersView from '../views/GroupSellingOffersView.vue'
import TenantAdminView from '../views/TenantAdminView.vue'
import V2MatchTrainingView from '../views/V2MatchTrainingView.vue'
import TaskOperationsView from '../views/TaskOperationsView.vue'
import TaskQueueSettingsView from '../views/TaskQueueSettingsView.vue'
import KiwiRouterView from '../views/KiwiRouterView.vue'
import InquiryForwardingView from '../views/InquiryForwardingView.vue'
import CompanyUsersView from '../views/CompanyUsersView.vue'
import CompanyRolesView from '../views/CompanyRolesView.vue'
import ClientPulseDirectoryView from '../views/ClientPulseDirectoryView.vue'
import ClientPulseProfileView from '../views/ClientPulseProfileView.vue'
import ClientPulseSettingsView from '../views/ClientPulseSettingsView.vue'
import ClientPulseRemindersView from '../views/ClientPulseRemindersView.vue'
import RealEstatePropertiesView from '../views/RealEstatePropertiesView.vue'
import RealEstateListingsView from '../views/RealEstateListingsView.vue'
import RealEstateCandidatesView from '../views/RealEstateCandidatesView.vue'
import RealEstateMockDataView from '../views/RealEstateMockDataView.vue'

const APP_TITLE = 'ChatLens'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/login', name: 'login', component: LoginView, meta: { public: true, title: 'Login' } },
    { path: '/', name: 'sessions', component: SessionView, meta: { title: 'Sessions' } },
    { path: '/conversations', name: 'conversations', component: ConversationsView, meta: { title: 'WhatsApp Inbox' } },
    { path: '/activity', name: 'activity', component: ActivityView, meta: { title: 'Activity' } },
    { path: '/storage', name: 'storage', component: StorageView, meta: { title: 'Storage' } },
    { path: '/message-logs', name: 'message-logs', component: MessageLogsView, meta: { title: 'Message Logs' } },
    { path: '/ai-providers', name: 'ai-providers', component: AIProvidersView, meta: { title: 'AI Providers' } },
    { path: '/dropped-messages', name: 'dropped-messages', component: DroppedMessagesView, meta: { title: 'Dropped Messages' } },
    { path: '/worker-alerts', name: 'worker-alerts', component: WorkerAlertsView, meta: { title: 'Worker Alerts' } },
    { path: '/baileys-events', name: 'baileys-events', component: BaileysEventsView, meta: { title: 'Baileys Events' } },
    { path: '/stuck-receipts', name: 'stuck-receipts', component: StuckReceiptsView, meta: { title: 'Stuck Receipts' } },
    { path: '/unresolved-messages', name: 'unresolved-messages', component: UnresolvedMessagesView, meta: { title: 'Unresolved Messages' } },
    { path: '/message-trace', name: 'message-trace', component: MessageTraceView, meta: { title: 'Message Trace' } },
    { path: '/ai-parsing-log', name: 'ai-parsing-log', component: AiParsingLogView, meta: { title: 'AI Parsing Log', industries: ['trading'] } },
    { path: '/ai-parse-v2-log', name: 'ai-parse-v2-log', component: AiParseV2LogView, meta: { title: 'AI Parse V2 Logs', industries: ['trading'] } },
    { path: '/contacts', name: 'contacts', component: ContactsView, meta: { title: 'Contacts' } },
    { path: '/groups', name: 'groups', component: GroupsView, meta: { title: 'Groups' } },
    { path: '/trading', name: 'trading', component: TradingView, meta: { title: 'Trading Dashboard', industries: ['trading'] } },
    { path: '/selling-offers', name: 'selling-offers', component: SellingOffersView, meta: { title: 'Selling Offers', industries: ['trading'] } },
    { path: '/trading-analytics', name: 'trading-analytics', component: TradingAnalyticsView, meta: { title: 'Trading Analytics', industries: ['trading'] } },
    { path: '/report-summary', name: 'report-summary', component: ReportSummaryView, meta: { title: 'Report Summary', industries: ['trading'] } },
    { path: '/inventory-product-mentions', name: 'inventory-product-mentions', component: InventoryProductMentionsReportView, meta: { title: 'Product Mentions', industries: ['trading'] } },
    { path: '/selling-offers-report', name: 'selling-offers-report', component: SellingOffersReportView, meta: { title: 'Selling Offers Report', industries: ['trading'] } },
    { path: '/inquiries', name: 'inquiries', component: InquiriesView, meta: { title: 'Inquiries', industries: ['trading'] } },
    { path: '/inquiry-products', name: 'inquiry-products', component: InquiryProductsView, meta: { title: 'Inquiry Products', industries: ['trading'] } },
    { path: '/non-inventory-products', name: 'non-inventory-products', component: NonInventoryProductsView, meta: { title: 'Non-Inventory Products', industries: ['trading'] } },
    { path: '/products', name: 'products', component: ProductsView, meta: { title: 'Products', industries: ['trading'] } },
    { path: '/v2-candidate-search', name: 'v2-candidate-search', component: V2CandidateSearchView, meta: { title: 'V2 Candidate Search', industries: ['trading'] } },
    { path: '/product-price-update', name: 'product-price-update', component: ProductPriceUpdateView, meta: { title: 'Product Price Update', industries: ['trading'] } },
    { path: '/automation', name: 'price-automation', component: AutomationView, meta: { title: 'Price Automation', industries: ['trading'] } },
    { path: '/buying-inquiries', name: 'buying-inquiries', component: BuyingInquiriesView, meta: { title: 'Buying Inquiries', industries: ['trading'] } },
    { path: '/group-buying-inquiries', name: 'group-buying-inquiries', component: GroupBuyingInquiriesView, meta: { title: 'Group Buying Inquiries', industries: ['trading'] } },
    { path: '/group-selling-offers', name: 'group-selling-offers', component: GroupSellingOffersView, meta: { title: 'Group Selling Offers', industries: ['trading'] } },
    { path: '/ai-instructions', name: 'ai-instructions', component: AIInstructionsView, meta: { title: 'AI Instructions', industries: ['trading'] } },
    { path: '/v2-settings', name: 'v2-settings', component: V2SettingsView, meta: { title: 'V2 Settings', industries: ['trading'] } },
    { path: '/tenant-admin', name: 'tenant-admin', component: TenantAdminView, meta: { title: 'Tenant Admin' } },
    { path: '/v2-match-training', name: 'v2-match-training', component: V2MatchTrainingView, meta: { title: 'V2 Match Training', industries: ['trading'] } },
    { path: '/task-operations', name: 'task-operations', component: TaskOperationsView, meta: { title: 'Task Operations' } },
    { path: '/task-queues', name: 'task-queues', component: TaskQueueSettingsView, meta: { title: 'Task & Queues' } },
    { path: '/kiwi-router', name: 'kiwi-router', component: KiwiRouterView, meta: { title: 'KiwiRouter' } },
    { path: '/inquiry-forwarding', name: 'inquiry-forwarding', component: InquiryForwardingView, meta: { title: 'Inquiry Forwarding', industries: ['trading'] } },
    { path: '/company-users', name: 'company-users', component: CompanyUsersView, meta: { title: 'Users', permission: 'users.memberships.view' } },
    { path: '/company-roles', name: 'company-roles', component: CompanyRolesView, meta: { title: 'Roles & Permissions', permission: 'users.roles.view' } },
    { path: '/clientpulse', name: 'clientpulse', component: ClientPulseDirectoryView, meta: { title: 'ClientPulse', permission: 'clientpulse.clients.view' } },
    { path: '/clientpulse/:id', name: 'clientpulse-profile', component: ClientPulseProfileView, meta: { title: 'Client Profile', permission: 'clientpulse.clients.view' } },
    { path: '/clientpulse-settings', name: 'clientpulse-settings', component: ClientPulseSettingsView, meta: { title: 'ClientPulse Settings', permission: 'settings.company.view' } },
    { path: '/clientpulse-reminders', name: 'clientpulse-reminders', component: ClientPulseRemindersView, meta: { title: 'ClientPulse Reminders', permission: 'clientpulse.reminders.view' } },
    { path: '/real-estate/properties', name: 'real-estate-properties', component: RealEstatePropertiesView, meta: { title: 'Properties', permission: 'real_estate.properties.view', industries: ['real_estate'] } },
    { path: '/real-estate/listings', name: 'real-estate-listings', component: RealEstateListingsView, meta: { title: 'Listings', permission: 'real_estate.listings.view', industries: ['real_estate'] } },
    { path: '/real-estate/candidates', name: 'real-estate-candidates', component: RealEstateCandidatesView, meta: { title: 'Candidate Review', permission: 'real_estate.opportunities.view', industries: ['real_estate'] } },
    { path: '/real-estate/mock-data', name: 'real-estate-mock-data', component: RealEstateMockDataView, meta: { title: 'Real Estate Mock Data', permission: 'real_estate.properties.manage', industries: ['real_estate'] } },
  ],
})

router.beforeEach(async (to) => {
  if (to.meta.public) return true
  const auth = useAuthStore()
  if (!auth.ready) await auth.init()
  if (!auth.user) return { name: 'login' }
  const industries = to.meta.industries
  if (Array.isArray(industries) && !industries.includes(auth.currentCompany?.industry_type)) {
    return auth.currentCompany?.industry_type === 'real_estate' ? { name: 'real-estate-properties' } : { name: 'sessions' }
  }
  if (typeof to.meta.permission === 'string' && !auth.hasPermission(to.meta.permission)) {
    return { name: 'sessions' }
  }
})

router.afterEach((to) => {
  const title = typeof to.meta.title === 'string' ? to.meta.title : ''
  document.title = title ? `${APP_TITLE} - ${title}` : APP_TITLE
})

export default router
