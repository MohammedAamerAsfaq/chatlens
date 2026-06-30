import { createRouter, createWebHistory } from 'vue-router'
import SessionView          from '../views/SessionView.vue'
import ConversationsView    from '../views/ConversationsView.vue'
import ActivityView         from '../views/ActivityView.vue'
import StorageView          from '../views/StorageView.vue'
import MessageLogsView      from '../views/MessageLogsView.vue'
import AIProvidersView      from '../views/AIProvidersView.vue'
import DroppedMessagesView  from '../views/DroppedMessagesView.vue'

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
  ],
})

export default router
