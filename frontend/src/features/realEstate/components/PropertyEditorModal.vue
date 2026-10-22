<script setup>
import UiButton from '@/components/ui/UiButton.vue'
import UiModal from '@/components/ui/UiModal.vue'
import PropertyForm from './PropertyForm.vue'

defineProps({
  open: Boolean,
  record: { type: Object, default: null },
  busy: Boolean,
  propertyTypes: { type: Array, default: () => [] },
  propertyTypeRecords: { type: Array, default: () => [] },
  properties: { type: Array, default: () => [] },
})
const emit = defineEmits(['close', 'save'])
</script>

<template><UiModal :open="open" :title="record ? 'Edit property' : 'Add property'" subtitle="Maintain the physical property separately from its sale or lease listings." size="xlarge" tall @close="emit('close')">
  <PropertyForm v-if="open" form-id="property-modal-form" :record="record" :property-types="propertyTypes" :property-type-records="propertyTypeRecords" :properties="properties" @submit="emit('save', $event)" />
  <template #footer><UiButton @click="emit('close')">Cancel</UiButton><UiButton variant="primary" type="submit" form="property-modal-form" :disabled="busy">{{ busy ? 'Saving...' : 'Save property' }}</UiButton></template>
</UiModal></template>
