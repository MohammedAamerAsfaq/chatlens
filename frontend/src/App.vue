<script setup>
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'
import { useConversationsStore } from '@/stores/conversations'
import { useAuthStore } from '@/stores/auth.js'

const route  = useRoute()
const router = useRouter()
const store  = useConversationsStore()
const auth   = useAuthStore()

async function handleLogout() {
  await auth.logout()
  router.push({ name: 'login' })
}
</script>

<template>
  <div class="h-screen bg-gray-50 flex flex-col overflow-hidden">
    <nav v-if="auth.user" class="bg-gray-900 text-white px-6 py-3 flex items-center gap-6 shadow shrink-0">
      <span class="text-green-400 font-bold text-lg mr-4">ChatLens</span>
      <RouterLink to="/"                class="nav-link" active-class="nav-link-active">Sessions</RouterLink>
      <RouterLink to="/conversations"   class="nav-link" active-class="nav-link-active">Conversations</RouterLink>
      <RouterLink to="/activity"        class="nav-link" active-class="nav-link-active">Activity</RouterLink>
      <RouterLink to="/storage"         class="nav-link" active-class="nav-link-active">Storage</RouterLink>
      <RouterLink to="/message-logs"    class="nav-link" active-class="nav-link-active">Message Logs</RouterLink>
      <RouterLink to="/ai-providers"    class="nav-link" active-class="nav-link-active">AI Providers</RouterLink>
      <RouterLink to="/contacts"        class="nav-link" active-class="nav-link-active">Contacts</RouterLink>
      <RouterLink to="/groups"          class="nav-link" active-class="nav-link-active">Groups</RouterLink>
      <RouterLink to="/trading"         class="nav-link" active-class="nav-link-active">Trading</RouterLink>
      <RouterLink to="/products"        class="nav-link" active-class="nav-link-active">Products</RouterLink>
      <RouterLink to="/ai-instructions" class="nav-link" active-class="nav-link-active">AI Instructions</RouterLink>
      <RouterLink to="/dropped-messages" class="nav-link" active-class="nav-link-active">Dropped</RouterLink>

      <!-- Account switcher — shown on Conversations page -->
      <div
        v-if="route.name === 'conversations' && store.accounts.length"
        class="ml-auto flex items-center gap-1"
      >
        <button
          v-for="account in store.accounts"
          :key="account.id"
          @click="store.switchAccount(account.id)"
          :class="[
            'relative flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-colors',
            store.selectedAccountId === account.id
              ? 'bg-green-600 text-white'
              : 'bg-gray-700 text-gray-300 hover:bg-gray-600 hover:text-white',
          ]"
        >
          <span
            :class="['w-1.5 h-1.5 rounded-full shrink-0', account.session_status === 'connected' ? 'bg-green-300' : 'bg-gray-500']"
          />
          {{ account.display_name || account.phone_number || `Account #${account.id}` }}
          <span
            v-if="account.total_unread > 0"
            class="ml-0.5 bg-red-500 text-white text-[10px] font-bold rounded-full min-w-[16px] h-4 flex items-center justify-center px-1 leading-none"
          >
            {{ account.total_unread > 99 ? '99+' : account.total_unread }}
          </span>
        </button>
      </div>

      <!-- Logout -->
      <div :class="route.name === 'conversations' && store.accounts.length ? '' : 'ml-auto'">
        <button @click="handleLogout" class="logout-btn">
          {{ auth.user?.username }} · Sign out
        </button>
      </div>
    </nav>

    <div class="flex-1 flex flex-col overflow-hidden min-h-0">
      <RouterView class="h-full" />
    </div>
  </div>
</template>

<style>
.nav-link        { font-size: 0.875rem; color: #d1d5db; transition: color 0.15s; white-space: nowrap; }
.nav-link:hover  { color: #fff; }
.nav-link-active { color: #fff; font-weight: 500; }
.logout-btn {
  font-size: 0.78rem;
  color: #9ca3af;
  background: transparent;
  border: 1px solid #374151;
  border-radius: 6px;
  padding: 4px 10px;
  cursor: pointer;
  white-space: nowrap;
  transition: color 0.15s, border-color 0.15s;
}
.logout-btn:hover { color: #fff; border-color: #6b7280; }
</style>
