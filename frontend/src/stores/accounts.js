import { defineStore } from 'pinia'
import { ref } from 'vue'
import { accountsApi } from '@/api'

export const useAccountsStore = defineStore('accounts', () => {
  const accounts = ref([])
  const loading = ref(false)
  const error = ref(null)

  async function fetchAccounts() {
    loading.value = true
    error.value = null
    try {
      const { data } = await accountsApi.list()
      accounts.value = data
    } catch (e) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  async function createAccount(payload) {
    const { data } = await accountsApi.create(payload)
    accounts.value.unshift(data)
    return data
  }

  async function startSession(id) {
    await accountsApi.startSession(id)
  }

  async function disconnect(id) {
    await accountsApi.disconnect(id)
    await fetchAccounts()
  }

  function updateAccount(updated) {
    const idx = accounts.value.findIndex(a => a.id === updated.id)
    if (idx !== -1) accounts.value[idx] = { ...accounts.value[idx], ...updated }
  }

  return { accounts, loading, error, fetchAccounts, createAccount, startSession, disconnect, updateAccount }
})
