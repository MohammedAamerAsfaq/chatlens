import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { authApi } from '../api/index.js'

export const useAuthStore = defineStore('auth', () => {
  const user  = ref(null)
  const ready = ref(false)
  const currentCompany = computed(() => user.value?.current_company ?? null)
  const currentRole = computed(() => currentCompany.value?.role ?? '')
  const memberships = computed(() => user.value?.memberships ?? [])
  const hasMultipleMemberships = computed(() => memberships.value.length > 1)
  const canManageTenants = computed(() => {
    const company = currentCompany.value
    if (!company) return false
    return company.company_type === 'control' && ['super_user', 'admin'].includes(currentRole.value)
  })

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
    hasMultipleMemberships,
    canManageTenants,
    init,
    login,
    selectCompany,
    updateCurrentCompanySettings,
    logout,
  }
})
