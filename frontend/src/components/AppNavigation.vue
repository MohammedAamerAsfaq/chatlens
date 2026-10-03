<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { workerAlertsApi, stuckReceiptsApi, unresolvedMessagesApi } from '@/api'
import { useAuthStore } from '@/stores/auth.js'
import { useConversationsStore } from '@/stores/conversations'
import { logsNavigation, moreNavigation, primaryNavigation, settingsNavigation } from '@/navigation/navigation'
import '@/assets/app-navigation.css'

const auth = useAuthStore()
const conversations = useConversationsStore()
const route = useRoute()
const router = useRouter()
const openMenu = ref('')
const mobileOpen = ref(false)
const switchingCompany = ref(false)
const switchingTheme = ref(false)
const alerts = ref({ worker: 0, receipts: 0, messages: 0 })
let alertPollTimer = null

const canShow = (item) => (!item.permission || auth.hasPermission(item.permission)) && (!item.tenantAdmin || auth.canManageTenants)
const visiblePrimary = computed(() => primaryNavigation.filter(canShow))
const visibleSettings = computed(() => settingsNavigation.filter(canShow))
const totalAlerts = computed(() => alerts.value.worker + alerts.value.receipts + alerts.value.messages)
const routeName = computed(() => String(route.name || ''))
const activePrimary = computed(() => visiblePrimary.value.find((item) => item.routes.includes(routeName.value)))
const activeUtility = computed(() => {
  if (settingsNavigation.some((item) => item.route === routeName.value)) return { id: 'settings', label: 'Settings', children: visibleSettings.value }
  if (logsNavigation.some((item) => item.route === routeName.value)) return { id: 'logs', label: 'Operations', children: logsNavigation }
  if (moreNavigation.some((item) => item.route === routeName.value)) return { id: 'more', label: 'Directory', children: moreNavigation }
  return null
})
const contextSection = computed(() => activePrimary.value || activeUtility.value)
const roleLabel = computed(() => auth.currentRole?.replaceAll('_', ' ') || '')

function badgeFor(item) {
  return item.badge ? alerts.value[item.badge] : 0
}

function toggleMenu(name) {
  openMenu.value = openMenu.value === name ? '' : name
}

function closeMenus() {
  openMenu.value = ''
}

async function fetchAlertCounts() {
  if (!auth.user) return
  try { alerts.value.worker = (await workerAlertsApi.unacknowledgedCount()).data.count } catch { /* non-critical */ }
  try { alerts.value.receipts = (await stuckReceiptsApi.unresolvedCount()).data.count } catch { /* non-critical */ }
  try { alerts.value.messages = (await unresolvedMessagesApi.counts()).data.pending } catch { /* non-critical */ }
}

async function switchCompany(event) {
  const companyId = Number(event.target.value)
  if (!companyId || companyId === auth.currentCompany?.id) return
  switchingCompany.value = true
  try {
    await auth.selectCompany(companyId)
    window.location.assign('/')
  } finally {
    switchingCompany.value = false
  }
}

async function logout() {
  closeMenus()
  await auth.logout()
  router.push({ name: 'login' })
}

async function switchTheme(event) {
  switchingTheme.value = true
  try {
    await auth.updateUiTheme(event.target.value)
  } finally {
    switchingTheme.value = false
  }
}

watch(() => route.fullPath, () => {
  closeMenus()
  mobileOpen.value = false
})
onMounted(() => {
  fetchAlertCounts()
  alertPollTimer = setInterval(fetchAlertCounts, 30000)
  document.addEventListener('click', closeMenus)
})
onUnmounted(() => {
  clearInterval(alertPollTimer)
  document.removeEventListener('click', closeMenus)
})
</script>

<template>
  <header class="app-navigation">
    <div class="app-navigation__bar">
      <RouterLink to="/" class="app-navigation__brand">ChatLens</RouterLink>
      <div class="company-picker">
        <span>Company</span>
        <select :value="auth.currentCompany?.id" :disabled="switchingCompany || !auth.hasMultipleMemberships" @change="switchCompany">
          <option v-for="membership in auth.memberships" :key="membership.company.id" :value="membership.company.id">
            {{ membership.company.name }}
          </option>
        </select>
      </div>

      <button class="mobile-menu-button" type="button" :aria-expanded="mobileOpen" aria-label="Toggle navigation" @click.stop="mobileOpen = !mobileOpen">
        <span></span><span></span><span></span>
      </button>

      <nav class="primary-navigation" aria-label="Primary navigation">
        <RouterLink v-for="item in visiblePrimary" :key="item.id" :to="item.to" class="primary-navigation__link" :class="{ active: item.routes.includes(routeName) }">
          {{ item.label }}
        </RouterLink>
        <div class="navigation-menu">
          <button type="button" class="primary-navigation__link" :class="{ active: activeUtility?.id === 'more' }" @click.stop="toggleMenu('more')">More <span>⌄</span></button>
          <div v-if="openMenu === 'more'" class="navigation-menu__panel compact" @click.stop>
            <RouterLink v-for="item in moreNavigation" :key="item.route" :to="item.to">{{ item.label }}</RouterLink>
          </div>
        </div>
      </nav>

      <nav class="utility-navigation" aria-label="Utilities">
        <div class="navigation-menu">
          <button type="button" class="utility-button" :class="{ active: activeUtility?.id === 'logs' }" aria-label="Operations and logs" @click.stop="toggleMenu('logs')">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 19V9m5 10V5m5 14v-7m5 7V3"/></svg><span>Operations</span>
            <b v-if="totalAlerts">{{ totalAlerts > 99 ? '99+' : totalAlerts }}</b>
          </button>
          <div v-if="openMenu === 'logs'" class="navigation-menu__panel navigation-menu__panel--right" @click.stop>
            <RouterLink v-for="item in logsNavigation" :key="item.route" :to="item.to">
              {{ item.label }}<b v-if="badgeFor(item)">{{ badgeFor(item) > 99 ? '99+' : badgeFor(item) }}</b>
            </RouterLink>
          </div>
        </div>
        <div class="navigation-menu">
          <button type="button" class="utility-button" :class="{ active: activeUtility?.id === 'settings' }" @click.stop="toggleMenu('settings')">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 15.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Z"/><path d="M19.4 15a1.7 1.7 0 0 0 .34 1.88l.06.06-2.83 2.83-.06-.06a1.7 1.7 0 0 0-1.88-.34 1.7 1.7 0 0 0-1.03 1.55V21h-4v-.08A1.7 1.7 0 0 0 8.95 19.4a1.7 1.7 0 0 0-1.88.34l-.06.06-2.83-2.83.06-.06A1.7 1.7 0 0 0 4.58 15 1.7 1.7 0 0 0 3 14H3v-4h.08A1.7 1.7 0 0 0 4.6 8.95a1.7 1.7 0 0 0-.34-1.88L4.2 7l2.83-2.83.06.06A1.7 1.7 0 0 0 9 4.58 1.7 1.7 0 0 0 10 3V3h4v.08A1.7 1.7 0 0 0 15.05 4.6a1.7 1.7 0 0 0 1.88-.34l.06-.06L19.82 7l-.06.06A1.7 1.7 0 0 0 19.42 9 1.7 1.7 0 0 0 21 10h.08v4H21a1.7 1.7 0 0 0-1.6 1Z"/></svg><span>Settings</span>
          </button>
          <div v-if="openMenu === 'settings'" class="navigation-menu__panel navigation-menu__panel--right settings-panel" @click.stop>
            <RouterLink v-for="item in visibleSettings" :key="item.route" :to="item.to">{{ item.label }}</RouterLink>
          </div>
        </div>
        <div class="navigation-menu">
          <button type="button" class="user-menu-button" @click.stop="toggleMenu('user')"><span>{{ auth.user?.username?.slice(0, 1)?.toUpperCase() }}</span>{{ auth.user?.username }} <i>⌄</i></button>
          <div v-if="openMenu === 'user'" class="navigation-menu__panel navigation-menu__panel--right user-panel" @click.stop>
            <div><strong>{{ auth.user?.username }}</strong><small>{{ roleLabel }}</small></div>
            <label class="theme-choice">
              <span>Interface theme</span>
              <select :value="auth.uiTheme" :disabled="switchingTheme" @change="switchTheme">
                <option v-for="theme in auth.availableThemes" :key="theme.key" :value="theme.key">{{ theme.name }}</option>
              </select>
            </label>
            <button type="button" @click="logout">Sign out</button>
          </div>
        </div>
      </nav>
    </div>

    <div v-if="mobileOpen" class="mobile-navigation">
      <RouterLink v-for="item in visiblePrimary" :key="item.id" :to="item.to">{{ item.label }}</RouterLink>
      <RouterLink v-for="item in moreNavigation" :key="item.route" :to="item.to">{{ item.label }}</RouterLink>
      <RouterLink to="/task-operations">Operations</RouterLink><RouterLink to="/">Settings</RouterLink>
      <button type="button" @click="logout">Sign out</button>
    </div>

    <nav v-if="contextSection || (routeName === 'conversations' && conversations.accounts.length)" class="context-navigation" :aria-label="`${contextSection?.label || 'Conversation'} navigation`">
      <strong>{{ contextSection?.label || 'Accounts' }}</strong>
      <template v-if="routeName === 'conversations'">
        <button v-for="account in conversations.accounts" :key="account.id" type="button" class="account-pill" :class="{ active: conversations.selectedAccountId === account.id }" @click="conversations.switchAccount(account.id)">
          <i :class="{ connected: account.session_status === 'connected' }"></i>{{ account.display_name || account.phone_number || `Account #${account.id}` }}
          <b v-if="account.total_unread">{{ account.total_unread > 99 ? '99+' : account.total_unread }}</b>
        </button>
      </template>
      <template v-else>
        <RouterLink v-for="item in contextSection?.children || []" :key="item.route" v-show="canShow(item)" :to="item.to" :class="{ active: item.route === routeName || (item.route === 'clientpulse' && routeName === 'clientpulse-profile') }">{{ item.label }}</RouterLink>
      </template>
    </nav>
  </header>
</template>
