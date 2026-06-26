<script setup>
import { ref } from 'vue'
import { useAccountsStore } from '@/stores/accounts'

const emit = defineEmits(['close', 'created'])
const store = useAccountsStore()

const displayName = ref('')
const submitting = ref(false)
const error = ref('')

async function submit() {
  if (!displayName.value.trim()) {
    error.value = 'Display name is required'
    return
  }
  submitting.value = true
  error.value = ''
  try {
    await store.createAccount({ display_name: displayName.value.trim() })
    emit('created')
    emit('close')
  } catch (e) {
    error.value = e.response?.data?.display_name?.[0] || e.response?.data?.detail || 'Failed to create account'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div
    class="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
    @click.self="emit('close')"
  >
    <div class="bg-white rounded-2xl shadow-xl p-8 w-full max-w-sm">
      <h2 class="text-lg font-semibold text-gray-900 mb-6">Add WhatsApp Account</h2>

      <div class="mb-5">
        <label class="block text-sm font-medium text-gray-700 mb-1">Display Name</label>
        <input
          v-model="displayName"
          type="text"
          placeholder="e.g. Business Account"
          class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-transparent"
          @keydown.enter="submit"
          autofocus
        />
        <p v-if="error" class="text-red-500 text-xs mt-1">{{ error }}</p>
      </div>

      <div class="flex gap-3">
        <button
          @click="emit('close')"
          class="flex-1 bg-gray-100 hover:bg-gray-200 text-gray-700 py-2 rounded-lg text-sm font-medium transition-colors"
        >
          Cancel
        </button>
        <button
          @click="submit"
          :disabled="submitting"
          class="flex-1 bg-green-600 hover:bg-green-700 disabled:opacity-50 text-white py-2 rounded-lg text-sm font-medium transition-colors"
        >
          {{ submitting ? 'Creating...' : 'Create' }}
        </button>
      </div>
    </div>
  </div>
</template>
