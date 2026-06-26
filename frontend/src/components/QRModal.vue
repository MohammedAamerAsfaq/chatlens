<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { accountsApi } from '@/api'

const props = defineProps({ accountId: Number })
const emit = defineEmits(['close'])

const qrImage = ref(null)
const connected = ref(false)
const message = ref('Generating QR code...')
let pollTimer = null

async function poll() {
  try {
    const { data, status } = await accountsApi.getQR(props.accountId)

    if (status === 202 || !data.qr) {
      message.value = 'Generating QR code...'
      return
    }

    qrImage.value = data.qr
    message.value = 'Open WhatsApp → Linked Devices → Link a Device → Scan'
  } catch {
    // keep polling
  }
}

async function pollConnection() {
  try {
    const { data } = await accountsApi.get(props.accountId)
    if (data.session_status === 'connected') {
      connected.value = true
      message.value = 'Connected successfully!'
      clearInterval(pollTimer)
    }
  } catch {}
}

onMounted(() => {
  poll()
  pollTimer = setInterval(() => {
    if (!connected.value) {
      poll()
      pollConnection()
    }
  }, 3000)
})

onUnmounted(() => clearInterval(pollTimer))
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
