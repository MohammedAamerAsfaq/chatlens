<script setup>
import { onMounted, ref } from 'vue'
import { useAccountsStore } from '@/stores/accounts'
import AccountCard from '@/components/AccountCard.vue'
import CreateAccountModal from '@/components/CreateAccountModal.vue'
import QRModal from '@/components/QRModal.vue'

const store = useAccountsStore()
const showCreate = ref(false)
const qrAccountId = ref(null)

onMounted(() => store.fetchAccounts())

function onQRRequested(id) {
  qrAccountId.value = id
}

function onQRClose() {
  qrAccountId.value = null
  store.fetchAccounts()
}
</script>

<template>
  <div>
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
</template>
