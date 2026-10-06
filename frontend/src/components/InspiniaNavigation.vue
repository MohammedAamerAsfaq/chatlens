<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { stuckReceiptsApi, unresolvedMessagesApi, workerAlertsApi } from '@/api'
import { useAuthStore } from '@/stores/auth.js'
import { useConversationsStore } from '@/stores/conversations'
import { logsNavigation, moreNavigation, primaryNavigation, settingsNavigation } from '@/navigation/navigation'
import { pageDescription as resolvePageDescription } from '@/navigation/pageDescriptions'
import InspiniaSidebarProfile from '@/components/navigation/InspiniaSidebarProfile.vue'
import InspiniaTopbarMenus from '@/components/navigation/InspiniaTopbarMenus.vue'
import InspiniaCustomizer from '@/components/navigation/InspiniaCustomizer.vue'
import NavigationChevron from '@/components/navigation/NavigationChevron.vue'
import NavigationIcon from '@/components/navigation/NavigationIcon.vue'
import { DEFAULT_INSPINIA_CONFIG } from '@/themes/inspinia.js'
import '@/assets/inspinia-shell.css'

const auth = useAuthStore()
const conversations = useConversationsStore()
const route = useRoute()
const router = useRouter()
const collapsed = ref(false)
const mobileOpen = ref(false)
const userOpen = ref(false)
const customizerOpen = ref(false)
const expanded = ref(new Set())
const switching = ref(false)
const alerts = ref({ worker: 0, receipts: 0, messages: 0 })
let pollTimer = null

const routeName = computed(() => String(route.name || ''))
const canShow = item => (!item.permission || auth.hasPermission(item.permission)) && (!item.tenantAdmin || auth.canManageTenants)
const primary = computed(() => primaryNavigation.filter(canShow))
const settings = computed(() => settingsNavigation.filter(canShow))
const topbarSections = computed(() => primary.value.map(item => ({ ...item, children: item.children?.filter(canShow) || [] })))
const topbarApps = computed(() => [...moreNavigation.filter(canShow), ...settings.value])
const alertTotal = computed(() => Object.values(alerts.value).reduce((sum, value) => sum + value, 0))
const pageTitle = computed(() => route.meta.title || 'Workspace')
const pageDescription = computed(() => resolvePageDescription(routeName.value))
const roleLabel = computed(() => auth.currentRole?.replaceAll('_', ' ') || '')

function isSectionOpen(item) { return item.routes?.includes(routeName.value) || expanded.value.has(item.id) }
function isUtilityOpen(id, items) { return expanded.value.has(id) || items.some(item => item.route === routeName.value) }
function toggleSection(id) {
  const next = new Set(expanded.value)
  next.has(id) ? next.delete(id) : next.add(id)
  expanded.value = next
}
function openSection(id) {
  if (collapsed.value) collapsed.value = false
  toggleSection(id)
}
function openSettings() {
  customizerOpen.value = true
}
function closeUserMenu() { userOpen.value = false }
function toggleNavigation() {
  if (window.innerWidth <= 992) mobileOpen.value = !mobileOpen.value
  else collapsed.value = !collapsed.value
}

async function fetchAlerts() {
  try { alerts.value.worker = (await workerAlertsApi.unacknowledgedCount()).data.count } catch { /* optional */ }
  try { alerts.value.receipts = (await stuckReceiptsApi.unresolvedCount()).data.count } catch { /* optional */ }
  try { alerts.value.messages = (await unresolvedMessagesApi.counts()).data.pending } catch { /* optional */ }
}
async function switchCompany(event) {
  switching.value = true
  try { await auth.selectCompany(Number(event.target.value)); window.location.assign('/') } finally { switching.value = false }
}
async function switchTheme(event) {
  switching.value = true
  try { await auth.updateUiTheme(event.target.value) } finally { switching.value = false }
}
async function saveInspiniaConfig(config) {
  switching.value = true
  try { await auth.updateInspiniaConfig(config) } finally { switching.value = false }
}
async function toggleFullscreen() {
  if (document.fullscreenElement) await document.exitFullscreen()
  else await document.documentElement.requestFullscreen()
}
async function logout() { await auth.logout(); router.push({ name: 'login' }) }

watch(() => route.fullPath, () => { mobileOpen.value = false; userOpen.value = false })
onMounted(() => {
  fetchAlerts()
  pollTimer = setInterval(fetchAlerts, 30000)
  document.addEventListener('click', closeUserMenu)
})
onUnmounted(() => {
  clearInterval(pollTimer)
  document.removeEventListener('click', closeUserMenu)
})
</script>

<template>
  <div v-if="mobileOpen" class="inspinia-backdrop" @click="mobileOpen = false"></div>
  <aside class="inspinia-sidebar" :class="{ collapsed, mobile: mobileOpen }">
    <div class="inspinia-brand"><span>CL</span><strong>ChatLens</strong></div>
    <InspiniaSidebarProfile :username="auth.user?.username" :role="roleLabel" :collapsed="collapsed" @open-settings="openSettings" />
    <nav class="inspinia-menu">
      <p>Main</p>
      <template v-for="item in primary" :key="item.id">
        <RouterLink v-if="!item.children" :to="item.to" class="inspinia-menu-link" :class="{ active: item.routes.includes(routeName) }"><NavigationIcon :name="item.id"/><span>{{ item.label }}</span></RouterLink>
        <template v-else>
          <button class="inspinia-menu-link" :class="{ active: item.routes.includes(routeName) }" @click="openSection(item.id)"><NavigationIcon :name="item.id"/><span>{{ item.label }}</span><NavigationChevron :open="isSectionOpen(item)" /></button>
          <div v-if="isSectionOpen(item) && !collapsed" class="inspinia-submenu"><RouterLink v-for="child in item.children.filter(canShow)" :key="child.route" :to="child.to" :class="{ active: child.route === routeName || (child.route === 'clientpulse' && routeName === 'clientpulse-profile') }">{{ child.label }}</RouterLink></div>
        </template>
      </template>
      <p>Workspace</p>
      <button class="inspinia-menu-link" :class="{ active: isUtilityOpen('directory', moreNavigation) }" @click="openSection('directory')"><NavigationIcon name="directory"/><span>Directory</span><NavigationChevron :open="isUtilityOpen('directory', moreNavigation)" /></button>
      <div v-if="isUtilityOpen('directory', moreNavigation) && !collapsed" class="inspinia-submenu"><RouterLink v-for="item in moreNavigation" :key="item.route" :to="item.to">{{ item.label }}</RouterLink></div>
      <button class="inspinia-menu-link" :class="{ active: isUtilityOpen('settings', settings) }" @click="openSection('settings')"><NavigationIcon name="settings"/><span>Settings</span><NavigationChevron :open="isUtilityOpen('settings', settings)" /></button>
      <div v-if="isUtilityOpen('settings', settings) && !collapsed" class="inspinia-submenu"><RouterLink v-for="item in settings" :key="item.route" :to="item.to">{{ item.label }}</RouterLink></div>
      <button class="inspinia-menu-link" :class="{ active: isUtilityOpen('operations', logsNavigation) }" @click="openSection('operations')"><NavigationIcon name="operations"/><span>Operations</span><b v-if="alertTotal">{{ alertTotal > 99 ? '99+' : alertTotal }}</b><NavigationChevron :open="isUtilityOpen('operations', logsNavigation)" /></button>
      <div v-if="isUtilityOpen('operations', logsNavigation) && !collapsed" class="inspinia-submenu"><RouterLink v-for="item in logsNavigation" :key="item.route" :to="item.to">{{ item.label }}</RouterLink></div>
    </nav>
  </aside>

  <header class="inspinia-topbar">
    <button class="inspinia-toggle" aria-label="Toggle sidebar" @click="toggleNavigation"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 7h14M5 12h14M5 17h14"/></svg></button>
    <div class="inspinia-page-title">
      <strong>{{ pageTitle }}</strong>
      <div id="inspinia-page-context" class="inspinia-page-context">
        <span v-if="routeName !== 'trading'" class="inspinia-page-description">{{ pageDescription }}</span>
      </div>
    </div>
    <select v-if="routeName === 'conversations' && conversations.accounts.length" class="inspinia-account-select" aria-label="WhatsApp account" :value="conversations.selectedAccountId" @change="conversations.switchAccount(Number($event.target.value))"><option v-for="account in conversations.accounts" :key="account.id" :value="account.id">{{ account.display_name || account.phone_number }}</option></select>
    <div class="inspinia-topbar-actions">
      <InspiniaTopbarMenus :sections="topbarSections" :apps="topbarApps" />
      <button class="inspinia-tool" title="Customize interface" aria-label="Customize interface" @click="customizerOpen = true"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="3"/><path d="M19 14.5 21 16l-2 3-2.4-1a8 8 0 0 1-2.1 1.2L14 22h-4l-.5-2.8A8 8 0 0 1 7.4 18L5 19l-2-3 2-1.5a8 8 0 0 1 0-5L3 8l2-3 2.4 1a8 8 0 0 1 2.1-1.2L10 2h4l.5 2.8A8 8 0 0 1 16.6 6L19 5l2 3-2 1.5a8 8 0 0 1 0 5Z"/></svg></button>
      <RouterLink to="/task-operations" class="inspinia-alert" title="Operations"><NavigationIcon name="operations"/><b v-if="alertTotal">{{ alertTotal > 99 ? '99+' : alertTotal }}</b></RouterLink>
      <button class="inspinia-tool" title="Toggle fullscreen" aria-label="Toggle fullscreen" @click="toggleFullscreen"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 3H3v5M16 3h5v5M8 21H3v-5M16 21h5v-5"/></svg></button>
      <select class="inspinia-company-select" :value="auth.currentCompany?.id" :disabled="switching || !auth.hasMultipleMemberships" @change="switchCompany"><option v-for="membership in auth.memberships" :key="membership.company.id" :value="membership.company.id">{{ membership.company.name }}</option></select>
      <div class="inspinia-user">
        <button @click.stop="userOpen = !userOpen"><span>{{ auth.user?.username?.slice(0, 1)?.toUpperCase() }}</span><strong>{{ auth.user?.username }}</strong><NavigationChevron :open="userOpen" /></button>
        <div v-if="userOpen" class="inspinia-user-menu" @click.stop><div><strong>{{ auth.user?.username }}</strong><small>{{ roleLabel }}</small></div><label>Interface theme<select :value="auth.uiTheme" :disabled="switching" @change="switchTheme"><option v-for="theme in auth.availableThemes" :key="theme.key" :value="theme.key">{{ theme.name }}</option></select></label><button class="signout" @click="logout">Sign out</button></div>
      </div>
    </div>
  </header>
  <InspiniaCustomizer v-if="customizerOpen" :config="auth.inspiniaConfig" :options="auth.inspiniaOptions" :busy="switching" @close="customizerOpen = false" @update="saveInspiniaConfig" @reset="saveInspiniaConfig({ ...DEFAULT_INSPINIA_CONFIG })" />
</template>
