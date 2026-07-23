<script setup>
import { computed, onMounted, ref } from 'vue'
import { useAccountsStore } from '@/stores/accounts'
import { useAuthStore } from '@/stores/auth.js'
import AccountCard from '@/components/AccountCard.vue'
import CreateAccountModal from '@/components/CreateAccountModal.vue'
import QRModal from '@/components/QRModal.vue'

const store = useAccountsStore()
const auth = useAuthStore()
const showCreate = ref(false)
const qrAccountId = ref(null)
const switchingCompany = ref(false)
const currentCompany = computed(() => auth.currentCompany)

onMounted(() => store.fetchAccounts())

function onQRRequested(id) {
  qrAccountId.value = id
}

function onQRClose() {
  qrAccountId.value = null
  store.fetchAccounts()
}

async function switchCompany(companyId) {
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
  <div class="h-full w-full overflow-y-auto bg-gray-50 px-6 py-6">
    <div class="max-w-5xl mx-auto">
    <div class="workspace-panel">
      <div>
        <p class="workspace-eyebrow">Active workspace</p>
        <h2 class="workspace-name">{{ currentCompany?.name || 'No company selected' }}</h2>
        <p class="workspace-copy">
          Session, trading, contacts, and reporting data are scoped to this company.
        </p>
      </div>
      <div v-if="auth.hasMultipleMemberships" class="workspace-memberships">
        <button
          v-for="membership in auth.memberships"
          :key="membership.company.id"
          type="button"
          class="workspace-pill"
          :class="{ 'workspace-pill-active': membership.company.id === currentCompany?.id }"
          :disabled="switchingCompany || membership.company.id === currentCompany?.id"
          @click="switchCompany(membership.company.id)"
        >
          <span>{{ membership.company.name }}</span>
          <span class="workspace-pill-role">{{ membership.role.replaceAll('_', ' ') }}</span>
        </button>
      </div>
    </div>

    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-2xl font-bold text-gray-900">Session Manager</h1>
        <p class="text-sm text-gray-500 mt-1">Manage WhatsApp linked device sessions</p>
      </div>
      <button
        @click="showCreate = true"
        class="bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
      >
        + Add Account
      </button>
    </div>

    <div v-if="store.loading" class="text-center text-gray-400 py-16">Loading...</div>

    <div v-else-if="store.error" class="text-center text-red-500 py-16">{{ store.error }}</div>

    <div v-else-if="store.accounts.length === 0" class="text-center text-gray-400 py-16">
      <p class="text-lg font-medium">No accounts yet</p>
      <p class="text-sm mt-1">Click "Add Account" to get started.</p>
    </div>

    <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      <AccountCard
        v-for="account in store.accounts"
        :key="account.id"
        :account="account"
        @show-qr="onQRRequested"
        @refresh="store.fetchAccounts"
      />
    </div>

    <CreateAccountModal
      v-if="showCreate"
      @close="showCreate = false"
      @created="store.fetchAccounts"
    />

    <QRModal
      v-if="qrAccountId"
      :account-id="qrAccountId"
      @close="onQRClose"
    />
    </div>
  </div>
</template>

<style scoped>
.workspace-panel {
  display: flex;
  justify-content: space-between;
  gap: 20px;
  align-items: flex-start;
  padding: 18px 20px;
  margin-bottom: 20px;
  border: 1px solid #d1d5db;
  border-radius: 14px;
  background: linear-gradient(135deg, #f8fafc 0%, #eefbf2 100%);
}
.workspace-eyebrow {
  margin: 0 0 6px;
  font-size: 0.72rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #6b7280;
}
.workspace-name {
  margin: 0;
  font-size: 1.25rem;
  font-weight: 700;
  color: #111827;
}
.workspace-copy {
  margin: 6px 0 0;
  font-size: 0.92rem;
  color: #4b5563;
}
.workspace-memberships {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 10px;
}
.workspace-pill {
  display: inline-flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  min-width: 180px;
  padding: 10px 12px;
  border: 1px solid #cbd5e1;
  border-radius: 12px;
  background: #ffffff;
  color: #111827;
  cursor: pointer;
  transition: border-color 0.15s, background-color 0.15s;
}
.workspace-pill:hover:enabled {
  border-color: #16a34a;
  background: #f0fdf4;
}
.workspace-pill:disabled {
  cursor: default;
}
.workspace-pill-active {
  border-color: #16a34a;
  background: #dcfce7;
}
.workspace-pill-role {
  font-size: 0.78rem;
  color: #6b7280;
  text-transform: capitalize;
}
</style>
