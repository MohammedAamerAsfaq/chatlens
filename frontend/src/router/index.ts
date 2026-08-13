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
import TradingAnalyticsView from '../views/TradingAnalyticsView.vue'
import ReportSummaryView    from '../views/ReportSummaryView.vue'
import InventoryProductMentionsReportView from '../views/InventoryProductMentionsReportView.vue'
import InquiriesView        from '../views/InquiriesView.vue'
import InquiryProductsView  from '../views/InquiryProductsView.vue'
import NonInventoryProductsView from '../views/NonInventoryProductsView.vue'
import ProductsView         from '../views/ProductsView.vue'
import V2CandidateSearchView from '../views/V2CandidateSearchView.vue'
import ProductPriceUpdateView from '../views/ProductPriceUpdateView.vue'
import AIInstructionsView   from '../views/AIInstructionsView.vue'
import V2SettingsView        from '../views/V2SettingsView.vue'
import BuyingInquiriesView  from '../views/BuyingInquiriesView.vue'
import TenantAdminView from '../views/TenantAdminView.vue'

const APP_TITLE = 'ChatLens'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/login', name: 'login', component: LoginView, meta: { public: true, title: 'Login' } },
    { path: '/', name: 'sessions', component: SessionView, meta: { title: 'Sessions' } },
    { path: '/conversations', name: 'conversations', component: ConversationsView, meta: { title: 'Conversations' } },
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
    { path: '/ai-parsing-log', name: 'ai-parsing-log', component: AiParsingLogView, meta: { title: 'AI Parsing Log' } },
    { path: '/ai-parse-v2-log', name: 'ai-parse-v2-log', component: AiParseV2LogView, meta: { title: 'AI Parse V2 Logs' } },
    { path: '/contacts', name: 'contacts', component: ContactsView, meta: { title: 'Contacts' } },
    { path: '/groups', name: 'groups', component: GroupsView, meta: { title: 'Groups' } },
    { path: '/trading', name: 'trading', component: TradingView, meta: { title: 'Trading' } },
    { path: '/trading-analytics', name: 'trading-analytics', component: TradingAnalyticsView, meta: { title: 'Trading Analytics' } },
    { path: '/report-summary', name: 'report-summary', component: ReportSummaryView, meta: { title: 'Report Summary' } },
    { path: '/inventory-product-mentions', name: 'inventory-product-mentions', component: InventoryProductMentionsReportView, meta: { title: 'Inventory Product Mentions' } },
    { path: '/inquiries', name: 'inquiries', component: InquiriesView, meta: { title: 'Inquiries' } },
    { path: '/inquiry-products', name: 'inquiry-products', component: InquiryProductsView, meta: { title: 'Inquiry Products' } },
    { path: '/non-inventory-products', name: 'non-inventory-products', component: NonInventoryProductsView, meta: { title: 'Non-Inventory Products' } },
    { path: '/products', name: 'products', component: ProductsView, meta: { title: 'Products' } },
    { path: '/v2-candidate-search', name: 'v2-candidate-search', component: V2CandidateSearchView, meta: { title: 'V2 Candidate Search' } },
    { path: '/product-price-update', name: 'product-price-update', component: ProductPriceUpdateView, meta: { title: 'Product Price Update' } },
    { path: '/buying-inquiries', name: 'buying-inquiries', component: BuyingInquiriesView, meta: { title: 'Buying Inquiries' } },
    { path: '/ai-instructions', name: 'ai-instructions', component: AIInstructionsView, meta: { title: 'AI Instructions' } },
    { path: '/v2-settings', name: 'v2-settings', component: V2SettingsView, meta: { title: 'V2 Settings' } },
    { path: '/tenant-admin', name: 'tenant-admin', component: TenantAdminView, meta: { title: 'Tenant Admin' } },
  ],
})

router.beforeEach(async (to) => {
  if (to.meta.public) return true
  const auth = useAuthStore()
  if (!auth.ready) await auth.init()
  if (!auth.user) return { name: 'login' }
})

router.afterEach((to) => {
  const title = typeof to.meta.title === 'string' ? to.meta.title : ''
  document.title = title ? `${APP_TITLE} - ${title}` : APP_TITLE
})

export default router
