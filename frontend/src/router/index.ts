import { createRouter, createWebHistory } from 'vue-router'
import SessionView from '../views/SessionView.vue'
import ConversationsView from '../views/ConversationsView.vue'
import ActivityView from '../views/ActivityView.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/', name: 'sessions', component: SessionView },
    { path: '/conversations', name: 'conversations', component: ConversationsView },
    { path: '/activity', name: 'activity', component: ActivityView },
  ],
})

export default router
