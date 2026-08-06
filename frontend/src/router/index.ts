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

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/login', name: 'login', component: LoginView, meta: { public: true } },
    { path: '/', name: 'sessions', component: SessionView },
    { path: '/conversations', name: 'conversations', component: ConversationsView },
    { path: '/activity', name: 'activity', component: ActivityView },
    { path: '/storage', name: 'storage', component: StorageView },
    { path: '/message-logs', name: 'message-logs', component: MessageLogsView },
    { path: '/ai-providers', name: 'ai-providers', component: AIProvidersView },
    { path: '/dropped-messages', name: 'dropped-messages', component: DroppedMessagesView },
    { path: '/worker-alerts', name: 'worker-alerts', component: WorkerAlertsView },
    { path: '/baileys-events', name: 'baileys-events', component: BaileysEventsView },
    { path: '/stuck-receipts', name: 'stuck-receipts', component: StuckReceiptsView },
    { path: '/unresolved-messages', name: 'unresolved-messages', component: UnresolvedMessagesView },
    { path: '/message-trace', name: 'message-trace', component: MessageTraceView },
    { path: '/ai-parsing-log', name: 'ai-parsing-log', component: AiParsingLogView },
    { path: '/ai-parse-v2-log', name: 'ai-parse-v2-log', component: AiParseV2LogView },
    { path: '/contacts', name: 'contacts', component: ContactsView },
    { path: '/groups', name: 'groups', component: GroupsView },
    { path: '/trading', name: 'trading', component: TradingView },
    { path: '/trading-analytics', name: 'trading-analytics', component: TradingAnalyticsView },
    { path: '/report-summary', name: 'report-summary', component: ReportSummaryView },
    { path: '/inventory-product-mentions', name: 'inventory-product-mentions', component: InventoryProductMentionsReportView },
    { path: '/inquiries', name: 'inquiries', component: InquiriesView },
    { path: '/inquiry-products', name: 'inquiry-products', component: InquiryProductsView },
    { path: '/non-inventory-products', name: 'non-inventory-products', component: NonInventoryProductsView },
    { path: '/products', name: 'products', component: ProductsView },
    { path: '/v2-candidate-search', name: 'v2-candidate-search', component: V2CandidateSearchView },
    { path: '/product-price-update', name: 'product-price-update', component: ProductPriceUpdateView },
    { path: '/buying-inquiries', name: 'buying-inquiries', component: BuyingInquiriesView },
    { path: '/ai-instructions', name: 'ai-instructions', component: AIInstructionsView },
    { path: '/v2-settings', name: 'v2-settings', component: V2SettingsView },
    { path: '/tenant-admin', name: 'tenant-admin', component: TenantAdminView },
  ],
})

router.beforeEach(async (to) => {
  if (to.meta.public) return true
  const auth = useAuthStore()
  if (!auth.ready) await auth.init()
  if (!auth.user) return { name: 'login' }
})

export default router
