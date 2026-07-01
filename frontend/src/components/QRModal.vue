<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { accountsApi } from '@/api'

const props = defineProps({ accountId: Number })
const emit = defineEmits(['close'])

const qrImage   = ref(null)
const connected = ref(false)
const message   = ref('Starting session…')
const error     = ref('')
let pollTimer   = null

function stopPolling() {
  clearInterval(pollTimer)
  pollTimer = null
}

function startPolling() {
  stopPolling()
  poll()
  pollTimer = setInterval(() => {
    if (!connected.value) {
      poll()
      pollConnection()
    }
  }, 3000)
}

async function poll() {
  try {
    const { data, status } = await accountsApi.getQR(props.accountId)

    if (status === 202 || !data.qr) {
      message.value = 'Generating QR code…'
      return
    }

    error.value   = ''
    qrImage.value = data.qr
    message.value = 'Open WhatsApp → Linked Devices → Link a Device → Scan'
  } catch (e) {
    const status = e.response?.status
    if (status === 404) {
      // Session died or never started — restart it automatically
      stopPolling()
      message.value = 'Restarting session…'
      try {
        await accountsApi.startSession(props.accountId)
        message.value = 'Generating QR code…'
        startPolling()
      } catch {
        error.value   = 'Could not start session. Check that the WhatsApp worker is running.'
        message.value = 'Failed to start'
      }
    } else if (status === 503) {
      error.value   = 'Worker is offline. Restart the WhatsApp worker and try again.'
      message.value = 'Worker offline'
      stopPolling()
    }
    // other transient errors: keep polling silently
  }
}

async function pollConnection() {
  try {
    const { data } = await accountsApi.get(props.accountId)
    if (data.session_status === 'connected') {
      connected.value = true
      message.value   = 'Connected successfully!'
      stopPolling()
    }
  } catch {}
}

onMounted(async () => {
  // Always (re)start the session when the modal opens so stale qr_generated
  // states are automatically recovered without the user having to close and
  // click Connect separately.
  try {
    await accountsApi.startSession(props.accountId)
  } catch {
    // Session may already be running — ignore and just start polling
  }
  message.value = 'Generating QR code…'
  startPolling()
})

onUnmounted(stopPolling)
</script>

<template>
  <div
    class="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
    @click.self="emit('close')"
  >
    <div class="bg-white rounded-2xl shadow-xl p-8 w-full max-w-sm text-center">
      <h2 class="text-lg font-semibold text-gray-900 mb-1">Scan QR Code</h2>
      <p class="text-sm text-gray-500 mb-6">{{ message }}</p>

      <div class="flex justify-center mb-6">
        <div v-if="connected" class="w-56 h-56 flex items-center justify-center">
          <span class="text-green-500 text-7xl">✓</span>
        </div>
        <div v-else-if="error" class="w-56 h-56 bg-red-50 border border-red-200 rounded-lg flex items-center justify-center p-4">
          <span class="text-red-600 text-sm text-center">{{ error }}</span>
        </div>
        <img
          v-else-if="qrImage"
          :src="qrImage"
          alt="WhatsApp QR Code"
          class="w-56 h-56 rounded-lg border border-gray-200"
        />
        <div
          v-else
          class="w-56 h-56 bg-gray-100 rounded-lg flex items-center justify-center animate-pulse"
        >
          <span class="text-gray-400 text-sm">Loading...</span>
        </div>
      </div>

      <button
        @click="emit('close')"
        :class="[
          'w-full py-2.5 rounded-lg text-sm font-medium transition-colors',
          connected
            ? 'bg-green-600 hover:bg-green-700 text-white'
            : 'bg-gray-100 hover:bg-gray-200 text-gray-700',
        ]"
      >
        {{ connected ? 'Done' : 'Cancel' }}
      </button>
    </div>
  </div>
</template>
