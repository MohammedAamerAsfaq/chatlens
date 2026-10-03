import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { authApi } from '../api/index.js'
import { DEFAULT_THEME, normalizeTheme } from '../themes/registry.js'
import { normalizeInspiniaConfig } from '../themes/inspinia.js'

export const useAuthStore = defineStore('auth', () => {
  const user  = ref(null)
  const ready = ref(false)
  const currentCompany = computed(() => user.value?.current_company ?? null)
  const currentRole = computed(() => currentCompany.value?.role ?? '')
  const memberships = computed(() => user.value?.memberships ?? [])
  const permissions = computed(() => user.value?.permissions ?? {})
  const uiTheme = computed(() => normalizeTheme(user.value?.preferences?.ui_theme || DEFAULT_THEME))
  const availableThemes = computed(() => user.value?.preferences?.available_themes ?? [])
  const inspiniaConfig = computed(() => normalizeInspiniaConfig(user.value?.preferences?.inspinia_config))
  const inspiniaOptions = computed(() => user.value?.preferences?.inspinia_options ?? {})
  const hasMultipleMemberships = computed(() => memberships.value.length > 1)
  const canManageTenants = computed(() => {
    const company = currentCompany.value
    if (!company) return false
    return company.company_type === 'control' && ['super_user', 'admin'].includes(currentRole.value)
  })
  const hasPermission = (code) => Boolean(permissions.value[code])
  const permissionScope = (code) => permissions.value[code] ?? null

  async function init() {
    try {
      const { data } = await authApi.me()
      user.value = data
    } catch {
      user.value = null
    }
    ready.value = true
  }

  async function login(username, password) {
    const { data } = await authApi.login({ username, password })
    user.value = data
  }

  async function selectCompany(companyId) {
    const { data } = await authApi.selectCompany(companyId)
    user.value = data
  }

  async function updateCurrentCompanySettings(payload) {
    const { data } = await authApi.updateCurrentCompanySettings(payload)
    user.value = data
  }

  async function updateUiTheme(uiTheme) {
    const { data } = await authApi.updatePreferences({ ui_theme: normalizeTheme(uiTheme) })
    user.value = data
  }

  async function updateInspiniaConfig(inspiniaConfig) {
    const { data } = await authApi.updatePreferences({ inspinia_config: inspiniaConfig })
    user.value = data
  }

  async function logout() {
    try { await authApi.logout() } catch { /* ignore */ }
    user.value = null
  }

  return {
    user,
    ready,
    currentCompany,
    currentRole,
    memberships,
    permissions,
    uiTheme,
    availableThemes,
    inspiniaConfig,
    inspiniaOptions,
    hasMultipleMemberships,
    canManageTenants,
    hasPermission,
    permissionScope,
    init,
    login,
    selectCompany,
    updateCurrentCompanySettings,
    updateUiTheme,
    updateInspiniaConfig,
    logout,
  }
})
