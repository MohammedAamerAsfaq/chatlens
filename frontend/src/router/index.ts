import { createRouter, createWebHistory } from 'vue-router'
import SessionView          from '../views/SessionView.vue'
import ConversationsView    from '../views/ConversationsView.vue'
import ActivityView         from '../views/ActivityView.vue'
import StorageView          from '../views/StorageView.vue'
import MessageLogsView      from '../views/MessageLogsView.vue'
import AIProvidersView      from '../views/AIProvidersView.vue'
import DroppedMessagesView  from '../views/DroppedMessagesView.vue'
import ContactsView         from '../views/ContactsView.vue'
import GroupsView           from '../views/GroupsView.vue'
import TradingView          from '../views/TradingView.vue'
import InquiriesView        from '../views/InquiriesView.vue'
import ProductsView         from '../views/ProductsView.vue'
import AIInstructionsView   from '../views/AIInstructionsView.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/', name: 'sessions', component: SessionView },
    { path: '/conversations', name: 'conversations', component: ConversationsView },
    { path: '/activity', name: 'activity', component: ActivityView },
    { path: '/storage', name: 'storage', component: StorageView },
    { path: '/message-logs', name: 'message-logs', component: MessageLogsView },
    { path: '/ai-providers', name: 'ai-providers', component: AIProvidersView },
    { path: '/dropped-messages', name: 'dropped-messages', component: DroppedMessagesView },
    { path: '/contacts', name: 'contacts', component: ContactsView },
    { path: '/groups', name: 'groups', component: GroupsView },
    { path: '/trading', name: 'trading', component: TradingView },
    { path: '/inquiries', name: 'inquiries', component: InquiriesView },
    { path: '/products', name: 'products', component: ProductsView },
    { path: '/ai-instructions', name: 'ai-instructions', component: AIInstructionsView },
  ],
})

export default router
