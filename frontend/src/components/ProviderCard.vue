<script setup>
defineProps({
  provider:   { type: Object,  required: true },
  testResult: { default: null },
  deleting:   { type: Boolean, default: false },
})
defineEmits(['edit', 'toggle-active', 'test', 'delete'])
</script>

<template>
  <div class="border rounded-lg bg-white p-4 flex items-start gap-4">
    <!-- Active toggle dot -->
    <div class="pt-0.5">
      <button
        @click="$emit('toggle-active')"
        :title="provider.is_active ? 'Click to deactivate' : 'Click to activate'"
        :class="[
          'w-4 h-4 rounded-full border-2 transition-colors',
          provider.is_active
            ? 'bg-green-500 border-green-500'
            : 'bg-white border-gray-300 hover:border-green-400',
        ]"
      />
    </div>

    <!-- Info -->
    <div class="flex-1 min-w-0">
      <div class="flex items-center gap-2 flex-wrap">
        <span class="font-medium text-gray-900 text-sm">{{ provider.display_name }}</span>
        <span :class="['text-xs px-2 py-0.5 rounded-full font-medium', provider.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500']">
          {{ provider.is_active ? 'active' : 'inactive' }}
        </span>
      </div>
      <div class="text-xs text-gray-500 mt-1 space-x-3">
        <span>{{ provider.provider_label }}</span>
        <span>·</span>
        <span class="font-mono">{{ provider.model }}</span>
        <span>·</span>
        <span class="font-mono">{{ provider.api_key_masked }}</span>
      </div>
      <!-- Test result -->
      <div v-if="testResult && testResult !== 'running'" class="mt-2 text-xs">
        <span v-if="testResult.ok" class="text-green-600">
          ✓ Connected
          <template v-if="testResult.dimensions"> · {{ testResult.dimensions }} dims</template>
          <template v-if="testResult.response"> · "{{ testResult.response }}"</template>
        </span>
        <span v-else class="text-red-600">✗ {{ testResult.error }}</span>
      </div>
    </div>

    <!-- Actions -->
    <div class="flex items-center gap-2 shrink-0">
      <button
        @click="$emit('test')"
        :disabled="testResult === 'running'"
        class="text-xs px-3 py-1.5 border border-gray-200 rounded hover:bg-gray-50 text-gray-600 transition-colors disabled:opacity-40"
      >
        {{ testResult === 'running' ? 'Testing…' : 'Test' }}
      </button>
      <button
        @click="$emit('edit')"
        class="text-xs px-3 py-1.5 border border-gray-200 rounded hover:bg-gray-50 text-gray-600 transition-colors"
      >
        Edit
      </button>
      <button
        @click="$emit('delete')"
        :disabled="deleting"
        class="text-xs px-3 py-1.5 border border-red-200 rounded hover:bg-red-50 text-red-600 transition-colors disabled:opacity-40"
      >
        {{ deleting ? '…' : 'Delete' }}
      </button>
    </div>
  </div>
</template>
