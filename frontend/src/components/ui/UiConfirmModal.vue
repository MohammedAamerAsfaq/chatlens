<script setup>
import UiButton from './UiButton.vue'
import UiModal from './UiModal.vue'

defineProps({
  open: { type: Boolean, default: false }, title: { type: String, default: 'Confirm action' },
  message: { type: String, default: '' }, confirmLabel: { type: String, default: 'Confirm' },
  cancelLabel: { type: String, default: 'Cancel' }, danger: { type: Boolean, default: false },
  busy: { type: Boolean, default: false },
})
defineEmits(['confirm', 'cancel'])
</script>

<template>
  <UiModal :open="open" :title="title" size="small" :closeable="!busy" @close="$emit('cancel')">
    <p class="ui-confirm-copy">{{ message }}</p>
    <template #footer><UiButton :disabled="busy" @click="$emit('cancel')">{{ cancelLabel }}</UiButton><UiButton :variant="danger ? 'danger' : 'primary'" :disabled="busy" @click="$emit('confirm')">{{ busy ? 'Working...' : confirmLabel }}</UiButton></template>
  </UiModal>
</template>
