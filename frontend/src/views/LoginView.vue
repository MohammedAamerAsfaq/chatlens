<template>
  <div class="login-page">
    <div class="login-card">
      <div class="login-logo">
        <span class="logo-mark">CL</span>
        <span class="logo-name">ChatLens</span>
      </div>
      <h1 class="login-title">Sign in</h1>
      <form @submit.prevent="submit" class="login-form">
        <div class="field">
          <label class="field-label">Username</label>
          <input
            v-model="username"
            type="text"
            class="field-input"
            autocomplete="username"
            autofocus
            :disabled="loading"
          />
        </div>
        <div class="field">
          <label class="field-label">Password</label>
          <input
            v-model="password"
            type="password"
            class="field-input"
            autocomplete="current-password"
            :disabled="loading"
          />
        </div>
        <div v-if="error" class="login-error">{{ error }}</div>
        <button type="submit" class="login-btn" :disabled="loading">
          {{ loading ? 'Signing in…' : 'Sign in' }}
        </button>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth.js'

const router   = useRouter()
const auth     = useAuthStore()
const username = ref('')
const password = ref('')
const error    = ref('')
const loading  = ref(false)

async function submit() {
  if (!username.value.trim() || !password.value) return
  error.value   = ''
  loading.value = true
  try {
    await auth.login(username.value.trim(), password.value)
    router.push({ name: 'sessions' })
  } catch (e) {
    error.value = e.response?.data?.detail || 'Invalid credentials'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f3f4f6;
}
.login-card {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 40px 36px;
  width: 100%;
  max-width: 380px;
  box-shadow: 0 4px 24px rgba(0,0,0,0.07);
}
.login-logo {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 28px;
}
.logo-mark {
  background: #111827;
  color: #4ade80;
  font-weight: 800;
  font-size: 0.9rem;
  letter-spacing: 0.03em;
  padding: 4px 8px;
  border-radius: 6px;
}
.logo-name {
  font-size: 1.1rem;
  font-weight: 700;
  color: #111827;
}
.login-title {
  font-size: 1.4rem;
  font-weight: 700;
  color: #111827;
  margin: 0 0 24px;
}
.login-form { display: flex; flex-direction: column; gap: 16px; }
.field { display: flex; flex-direction: column; gap: 5px; }
.field-label { font-size: 0.83rem; font-weight: 600; color: #374151; }
.field-input {
  padding: 9px 12px;
  border: 1px solid #d1d5db;
  border-radius: 7px;
  font-size: 0.92rem;
  outline: none;
  transition: border-color 0.15s;
}
.field-input:focus { border-color: #6366f1; }
.field-input:disabled { background: #f9fafb; color: #9ca3af; }
.login-error {
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 7px;
  padding: 9px 12px;
  font-size: 0.83rem;
  color: #b91c1c;
}
.login-btn {
  padding: 10px;
  background: #111827;
  color: #fff;
  border: none;
  border-radius: 7px;
  font-size: 0.92rem;
  font-weight: 600;
  cursor: pointer;
  margin-top: 4px;
  transition: background 0.15s;
}
.login-btn:hover:not(:disabled) { background: #1f2937; }
.login-btn:disabled { opacity: 0.6; cursor: not-allowed; }
</style>
