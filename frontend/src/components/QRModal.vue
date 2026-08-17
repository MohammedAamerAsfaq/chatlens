<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { accountsApi } from '@/api'

const props = defineProps({ accountId: Number })
const emit = defineEmits(['close'])

const qrImage = ref(null)
const connected = ref(false)
const message = ref('Starting session...')
const error = ref('')
let pollTimer = null

const PHASE_MESSAGES = {
  starting: 'Starting worker session...',
  loading_auth: 'Loading WhatsApp credentials...',
  fetching_version: 'Checking WhatsApp Web version...',
  connecting_to_whatsapp: 'Connecting to WhatsApp...',
  pending_qr: 'Waiting for QR code...',
  qr_generated: 'Open WhatsApp -> Linked Devices -> Link a Device -> Scan',
  connected: 'Connected successfully!',
  error: 'Failed to connect',
}

function messageForPhase(data) {
  return PHASE_MESSAGES[data?.startupPhase] || PHASE_MESSAGES[data?.status] || 'Generating QR code...'
}

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

    if (data.status === 'connected') {
      connected.value = true
      error.value = ''
      message.value = 'Connected successfully!'
      stopPolling()
      return
    }

    if (status === 202 || !data.qr) {
      message.value = messageForPhase(data)
      return
    }

    error.value = ''
    qrImage.value = data.qr
    message.value = messageForPhase(data)
  } catch (e) {
    const status = e.response?.status
    if (status === 404) {
      stopPolling()
      message.value = 'Restarting session...'
      try {
        await accountsApi.startSession(props.accountId)
        message.value = 'Starting worker session...'
        startPolling()
      } catch {
        error.value = 'Could not start session. Check that the WhatsApp worker is running.'
        message.value = 'Failed to start'
      }
    } else if (status === 503) {
      error.value = 'Worker is offline. Restart the WhatsApp worker and try again.'
      message.value = 'Worker offline'
      stopPolling()
    } else if (status === 500) {
      error.value = e.response?.data?.error || 'Connection failed - please try again.'
      message.value = messageForPhase(e.response?.data)
      stopPolling()
    } else {
      error.value = 'Lost contact with the server while generating the QR code.'
      message.value = 'Connection error'
      stopPolling()
    }
  }
}

async function pollConnection() {
  try {
    const { data } = await accountsApi.get(props.accountId)
    if (data.session_status === 'connected') {
      connected.value = true
      message.value = 'Connected successfully!'
      stopPolling()
    }
  } catch {}
}

onMounted(async () => {
  try {
    await accountsApi.startSession(props.accountId)
  } catch {
    // Session may already be running. Polling below will surface real errors.
  }
  message.value = 'Starting worker session...'
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
          <span class="text-green-500 text-7xl">OK</span>
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
          class="w-56 h-56 bg-gray-100 rounded-lg flex flex-col gap-3 items-center justify-center"
        >
          <span class="h-7 w-7 rounded-full border-4 border-gray-300 border-t-green-600 animate-spin" />
          <span class="text-gray-400 text-sm">Working...</span>
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
