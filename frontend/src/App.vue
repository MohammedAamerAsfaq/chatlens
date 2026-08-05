<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'
import { useConversationsStore } from '@/stores/conversations'
import { useAuthStore } from '@/stores/auth.js'
import { workerAlertsApi, stuckReceiptsApi, unresolvedMessagesApi } from '@/api'

const route  = useRoute()
const router = useRouter()
const store  = useConversationsStore()
const auth   = useAuthStore()
const currentCompany = computed(() => auth.currentCompany)
const currentRole = computed(() => {
  if (!auth.currentRole) return ''
  return auth.currentRole.replaceAll('_', ' ')
})
const switchingCompany = ref(false)

const LOG_ROUTES = ['activity', 'message-logs', 'dropped-messages', 'worker-alerts', 'baileys-events', 'message-trace', 'stuck-receipts', 'unresolved-messages', 'ai-parsing-log', 'ai-parse-v2-log']
const isLogsActive = computed(() => LOG_ROUTES.includes(route.name))

// Nav-level visibility for worker alerts ("admin should be notified") — a badge that's
// visible from anywhere in the app, not just when someone happens to open the Logs
// dropdown and click through to the page.
const unacknowledgedAlerts = ref(0)
const unresolvedStuckReceipts = ref(0)
const pendingUnresolvedMessages = ref(0)
let alertPollTimer = null

async function fetchUnacknowledgedCount() {
  if (!auth.user) return
  try {
    const { data } = await workerAlertsApi.unacknowledgedCount()
    unacknowledgedAlerts.value = data.count
  } catch { /* non-critical — badge just won't update this cycle */ }
  try {
    const { data } = await stuckReceiptsApi.unresolvedCount()
    unresolvedStuckReceipts.value = data.count
  } catch { /* non-critical — badge just won't update this cycle */ }
  try {
    const { data } = await unresolvedMessagesApi.counts()
    pendingUnresolvedMessages.value = data.pending
  } catch { /* non-critical — badge just won't update this cycle */ }
}

onMounted(() => {
  fetchUnacknowledgedCount()
  alertPollTimer = setInterval(fetchUnacknowledgedCount, 30000)
})
onUnmounted(() => clearInterval(alertPollTimer))

const REPORT_ROUTES = ['trading-analytics', 'report-summary', 'inventory-product-mentions']
const isReportsActive = computed(() => REPORT_ROUTES.includes(route.name))

const LIST_ROUTES = ['contacts', 'groups', 'products', 'inquiry-products', 'product-price-update']
const isListsActive = computed(() => LIST_ROUTES.includes(route.name))

const SETTINGS_ROUTES = ['sessions', 'storage', 'ai-providers', 'ai-instructions', 'v2-settings', 'tenant-admin']
const isSettingsActive = computed(() => SETTINGS_ROUTES.includes(route.name))

async function handleLogout() {
  await auth.logout()
  router.push({ name: 'login' })
}

async function handleCompanySwitch(event) {
  const companyId = Number(event.target.value)
  if (!companyId || companyId === currentCompany.value?.id) return
  switchingCompany.value = true
  try {
    await auth.selectCompany(companyId)
    window.location.assign('/')
  } finally {
    switchingCompany.value = false
  }
}
</script>

<template>
  <div class="h-screen bg-gray-50 flex flex-col overflow-hidden">
    <nav v-if="auth.user" class="bg-gray-900 text-white px-6 py-3 flex items-center gap-6 shadow shrink-0">
      <div class="mr-4 flex items-center gap-3">
        <span class="text-green-400 font-bold text-lg">ChatLens</span>
        <div v-if="currentCompany" class="tenant-chip" :title="currentCompany.slug">
          <span class="tenant-chip-label">Company</span>
          <span class="tenant-chip-name">{{ currentCompany.name }}</span>
          <span v-if="currentRole" class="tenant-chip-role">{{ currentRole }}</span>
        </div>
      </div>
      <RouterLink to="/conversations"   class="nav-link" active-class="nav-link-active">Conversations</RouterLink>
      <RouterLink to="/trading"            class="nav-link" active-class="nav-link-active">Trading</RouterLink>
      <RouterLink to="/buying-inquiries"  class="nav-link" active-class="nav-link-active">Buying Inquiries</RouterLink>

      <!-- Reports — grouped dropdown, opens on hover -->
      <div class="relative group">
        <button type="button" class="nav-link flex items-center gap-1" :class="{ 'nav-link-active': isReportsActive }">
          Reports
          <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/>
          </svg>
        </button>
        <div class="absolute left-0 top-full hidden group-hover:block bg-gray-800 border border-gray-700 rounded-lg shadow-lg py-1 min-w-[170px] z-50">
          <RouterLink to="/trading-analytics" class="dropdown-item" active-class="dropdown-item-active">Analytics</RouterLink>
          <RouterLink to="/report-summary" class="dropdown-item" active-class="dropdown-item-active">Summary</RouterLink>
          <RouterLink to="/inventory-product-mentions" class="dropdown-item" active-class="dropdown-item-active">Inventory Product Mentions</RouterLink>
        </div>
      </div>

      <!-- Lists — grouped dropdown, opens on hover -->
      <div class="relative group">
        <button type="button" class="nav-link flex items-center gap-1" :class="{ 'nav-link-active': isListsActive }">
          Lists
          <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/>
          </svg>
        </button>
        <div class="absolute left-0 top-full hidden group-hover:block bg-gray-800 border border-gray-700 rounded-lg shadow-lg py-1 min-w-[170px] z-50">
          <RouterLink to="/contacts" class="dropdown-item" active-class="dropdown-item-active">Contacts</RouterLink>
          <RouterLink to="/groups"   class="dropdown-item" active-class="dropdown-item-active">Groups</RouterLink>
          <RouterLink to="/products" class="dropdown-item" active-class="dropdown-item-active">Products</RouterLink>
          <RouterLink to="/inquiry-products" class="dropdown-item" active-class="dropdown-item-active">Inquiry Products</RouterLink>
          <RouterLink to="/product-price-update" class="dropdown-item" active-class="dropdown-item-active">Product Price Update</RouterLink>
        </div>
      </div>

      <!-- Settings — grouped dropdown, opens on hover -->
      <div class="relative group">
        <button type="button" class="nav-link flex items-center gap-1" :class="{ 'nav-link-active': isSettingsActive }">
          Settings
          <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/>
          </svg>
        </button>
        <div class="absolute left-0 top-full hidden group-hover:block bg-gray-800 border border-gray-700 rounded-lg shadow-lg py-1 min-w-[170px] z-50">
          <RouterLink to="/"                class="dropdown-item" active-class="dropdown-item-active">Sessions</RouterLink>
          <RouterLink to="/storage"         class="dropdown-item" active-class="dropdown-item-active">Storage</RouterLink>
          <RouterLink to="/ai-providers"    class="dropdown-item" active-class="dropdown-item-active">AI Providers</RouterLink>
          <RouterLink to="/ai-instructions" class="dropdown-item" active-class="dropdown-item-active">AI Instructions</RouterLink>
          <RouterLink to="/v2-settings"     class="dropdown-item" active-class="dropdown-item-active">V2 Settings</RouterLink>
          <RouterLink v-if="auth.canManageTenants" to="/tenant-admin" class="dropdown-item" active-class="dropdown-item-active">Tenant Admin</RouterLink>
        </div>
      </div>

      <!-- Logs — grouped dropdown, opens on hover -->
      <div class="relative group">
        <button type="button" class="nav-link flex items-center gap-1" :class="{ 'nav-link-active': isLogsActive }">
          Logs
          <span
            v-if="unacknowledgedAlerts + unresolvedStuckReceipts + pendingUnresolvedMessages > 0"
            class="bg-red-500 text-white text-[10px] font-bold rounded-full px-1.5 py-0.5 leading-none"
            :title="`${unacknowledgedAlerts} unacknowledged worker alert${unacknowledgedAlerts !== 1 ? 's' : ''}, ${unresolvedStuckReceipts} unresolved stuck receipt${unresolvedStuckReceipts !== 1 ? 's' : ''}, ${pendingUnresolvedMessages} pending unresolved message${pendingUnresolvedMessages !== 1 ? 's' : ''}`"
          >{{ (unacknowledgedAlerts + unresolvedStuckReceipts + pendingUnresolvedMessages) > 99 ? '99+' : (unacknowledgedAlerts + unresolvedStuckReceipts + pendingUnresolvedMessages) }}</span>
          <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/>
          </svg>
        </button>
        <div class="absolute left-0 top-full hidden group-hover:block bg-gray-800 border border-gray-700 rounded-lg shadow-lg py-1 min-w-[170px] z-50">
          <RouterLink to="/activity"          class="dropdown-item" active-class="dropdown-item-active">Activity</RouterLink>
          <RouterLink to="/message-logs"      class="dropdown-item" active-class="dropdown-item-active">Message Logs</RouterLink>
          <RouterLink to="/dropped-messages"  class="dropdown-item" active-class="dropdown-item-active">Dropped</RouterLink>
          <RouterLink to="/baileys-events"    class="dropdown-item" active-class="dropdown-item-active">Baileys Events</RouterLink>
          <RouterLink to="/message-trace"     class="dropdown-item" active-class="dropdown-item-active">Message Trace</RouterLink>
          <RouterLink to="/worker-alerts" class="dropdown-item flex items-center justify-between" active-class="dropdown-item-active">
            Worker Alerts
            <span v-if="unacknowledgedAlerts > 0" class="bg-red-500 text-white text-[10px] font-bold rounded-full px-1.5 py-0.5 leading-none ml-2">
              {{ unacknowledgedAlerts > 99 ? '99+' : unacknowledgedAlerts }}
            </span>
          </RouterLink>
          <RouterLink to="/stuck-receipts" class="dropdown-item flex items-center justify-between" active-class="dropdown-item-active">
            Stuck Receipts
            <span v-if="unresolvedStuckReceipts > 0" class="bg-red-500 text-white text-[10px] font-bold rounded-full px-1.5 py-0.5 leading-none ml-2">
              {{ unresolvedStuckReceipts > 99 ? '99+' : unresolvedStuckReceipts }}
            </span>
          </RouterLink>
          <RouterLink to="/unresolved-messages" class="dropdown-item flex items-center justify-between" active-class="dropdown-item-active">
            Unresolved Messages
            <span v-if="pendingUnresolvedMessages > 0" class="bg-red-500 text-white text-[10px] font-bold rounded-full px-1.5 py-0.5 leading-none ml-2">
              {{ pendingUnresolvedMessages > 99 ? '99+' : pendingUnresolvedMessages }}
            </span>
          </RouterLink>
          <RouterLink to="/ai-parsing-log"    class="dropdown-item" active-class="dropdown-item-active">AI Parsing Log</RouterLink>
          <RouterLink to="/ai-parse-v2-log"   class="dropdown-item" active-class="dropdown-item-active">AI Parse V2 Logs</RouterLink>
        </div>
      </div>

      <div v-if="auth.hasMultipleMemberships" class="workspace-switcher">
        <label class="workspace-switcher-label" for="workspace-switcher">Workspace</label>
        <select
          id="workspace-switcher"
          class="workspace-switcher-select"
          :value="currentCompany?.id"
          :disabled="switchingCompany"
          @change="handleCompanySwitch"
        >
          <option
            v-for="membership in auth.memberships"
            :key="membership.company.id"
            :value="membership.company.id"
          >
            {{ membership.company.name }}
          </option>
        </select>
      </div>

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
.nav-link        { font-size: 0.875rem; color: #d1d5db; transition: color 0.15s; white-space: nowrap; background: none; border: none; cursor: pointer; padding: 0; font-family: inherit; }
.nav-link:hover  { color: #fff; }
.nav-link-active { color: #fff; font-weight: 500; }
.dropdown-item {
  display: block;
  padding: 8px 14px;
  font-size: 0.85rem;
  color: #d1d5db;
  white-space: nowrap;
  transition: background-color 0.15s, color 0.15s;
}
.dropdown-item:hover  { background: #374151; color: #fff; }
.dropdown-item-active { color: #fff; font-weight: 500; background: #374151; }
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
.tenant-chip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  border: 1px solid #374151;
  border-radius: 9999px;
  background: rgba(17, 24, 39, 0.55);
  color: #e5e7eb;
  line-height: 1;
}
.tenant-chip-label {
  font-size: 0.68rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #9ca3af;
}
.tenant-chip-name {
  font-size: 0.8rem;
  font-weight: 600;
  color: #ffffff;
}
.tenant-chip-role {
  font-size: 0.72rem;
  color: #86efac;
  text-transform: capitalize;
}
.workspace-switcher {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  margin-left: auto;
}
.workspace-switcher-label {
  font-size: 0.72rem;
  color: #9ca3af;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}
.workspace-switcher-select {
  min-width: 180px;
  background: #111827;
  color: #f9fafb;
  border: 1px solid #374151;
  border-radius: 8px;
  padding: 6px 10px;
  font-size: 0.82rem;
}
.workspace-switcher-select:disabled {
  opacity: 0.65;
  cursor: wait;
}
</style>
