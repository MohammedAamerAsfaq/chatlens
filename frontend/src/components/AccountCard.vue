<script setup>
import { useAccountsStore } from '@/stores/accounts'

const props = defineProps({ account: Object })
const emit = defineEmits(['show-qr', 'refresh'])
const store = useAccountsStore()

const statusConfig = {
  pending_qr:   { label: 'Pending QR',   cls: 'bg-yellow-100 text-yellow-800' },
  qr_generated: { label: 'QR Generated', cls: 'bg-blue-100 text-blue-800' },
  connected:    { label: 'Connected',    cls: 'bg-green-100 text-green-800' },
  disconnected: { label: 'Disconnected', cls: 'bg-gray-100 text-gray-600' },
  logged_out:   { label: 'Logged Out',   cls: 'bg-red-100 text-red-700' },
  error:        { label: 'Error',        cls: 'bg-red-100 text-red-700' },
}

function statusFor(s) {
  return statusConfig[s] || { label: s, cls: 'bg-gray-100 text-gray-600' }
}

function formatDate(dt) {
  if (!dt) return '—'
  return new Date(dt).toLocaleString()
}

async function connect() {
  await store.startSession(props.account.id)
  emit('show-qr', props.account.id)
}

async function disconnect() {
  await store.disconnect(props.account.id)
  emit('refresh')
}
</script>

<template>
  <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-5 flex flex-col gap-3">
    <div class="flex items-start justify-between gap-2">
      <div class="min-w-0">
        <p class="font-semibold text-gray-900 truncate">
          {{ account.display_name || 'Unnamed Account' }}
        </p>
        <p class="text-sm text-gray-500">{{ account.phone_number || 'No phone yet' }}</p>
      </div>
      <span :class="['shrink-0 text-xs font-medium px-2 py-1 rounded-full', statusFor(account.session_status).cls]">
        {{ statusFor(account.session_status).label }}
      </span>
    </div>

    <p class="text-xs text-gray-400">Last connected: {{ formatDate(account.last_connected_at) }}</p>

    <div class="flex gap-2">
      <button
        v-if="['disconnected', 'pending_qr', 'logged_out', 'error'].includes(account.session_status)"
        @click="connect"
        class="flex-1 bg-green-600 hover:bg-green-700 text-white text-sm py-1.5 rounded-lg transition-colors"
      >
        Connect
      </button>

      <button
        v-if="account.session_status === 'qr_generated'"
        @click="emit('show-qr', account.id)"
        class="flex-1 bg-blue-600 hover:bg-blue-700 text-white text-sm py-1.5 rounded-lg transition-colors"
      >
        Show QR
      </button>

      <button
        v-if="account.session_status === 'connected'"
        @click="disconnect"
        class="flex-1 bg-red-500 hover:bg-red-600 text-white text-sm py-1.5 rounded-lg transition-colors"
      >
        Disconnect
      </button>
    </div>
  </div>
</template>
