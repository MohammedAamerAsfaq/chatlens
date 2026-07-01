import { ref } from 'vue'
import { defineStore } from 'pinia'
import { authApi } from '../api/index.js'

export const useAuthStore = defineStore('auth', () => {
  const user  = ref(null)
  const ready = ref(false)

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

  async function logout() {
    try { await authApi.logout() } catch { /* ignore */ }
    user.value = null
  }

  return { user, ready, init, login, logout }
})
