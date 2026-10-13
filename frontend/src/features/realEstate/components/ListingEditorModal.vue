<script setup>
import { computed, reactive, watch } from 'vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiCheckbox from '@/components/ui/UiCheckbox.vue'
import UiDatePicker from '@/components/ui/UiDatePicker.vue'
import UiFormField from '@/components/ui/UiFormField.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiModal from '@/components/ui/UiModal.vue'
import UiRadioGroup from '@/components/ui/UiRadioGroup.vue'
import UiSelect from '@/components/ui/UiSelect.vue'
import { listingStatuses, listingTypes, paymentFrequencies } from '../options'
import { emptyListing } from '../forms'

const props = defineProps({ open: Boolean, record: { type: Object, default: null }, properties: { type: Array, default: () => [] }, busy: Boolean })
const emit = defineEmits(['close', 'save'])
const form = reactive(emptyListing())
const propertyOptions = computed(() => props.properties.map(item => ({ value: item.id, label: `${item.reference_code ? `${item.reference_code} - ` : ''}${item.title}` })))

watch(() => [props.open, props.record], () => {
  if (!props.open) return
  Object.assign(form, emptyListing(), props.record || {})
}, { immediate: true, deep: true })
watch(() => form.listing_type, type => {
  if (type === 'sale') form.payment_frequency = 'not_applicable'
  else if (form.payment_frequency === 'not_applicable') form.payment_frequency = 'yearly'
})
</script>

<template>
  <UiModal :open="open" :title="record ? 'Edit listing' : 'Add listing'" subtitle="A property can carry separate sale and lease listing histories." size="large" tall @close="emit('close')">
    <form id="listing-form" class="re-form-grid" @submit.prevent="emit('save', { ...form })">
      <UiFormField label="Property" class="wide"><UiSelect v-model="form.property" :options="propertyOptions" searchable placeholder="Select a property" :disabled="Boolean(record)" /></UiFormField>
      <UiRadioGroup v-model="form.listing_type" label="Listing type" :options="listingTypes" />
      <UiRadioGroup v-model="form.status" label="Status" :options="listingStatuses" />
      <UiFormField label="Asking price"><UiInput v-model="form.asking_price" compact type="number" min="0" step="0.01" required /></UiFormField>
      <UiFormField label="Currency"><UiInput v-model="form.currency" maxlength="3" required /></UiFormField>
      <UiRadioGroup v-model="form.payment_frequency" label="Payment frequency" :options="paymentFrequencies" :disabled="form.listing_type === 'sale'" />
      <UiFormField label="Available from"><UiDatePicker v-model="form.available_from" /></UiFormField>
      <UiFormField label="Deposit"><UiInput v-model="form.deposit" compact type="number" min="0" step="0.01" /></UiFormField>
      <UiFormField label="Commission"><UiInput v-model="form.commission" compact type="number" min="0" step="0.01" /></UiFormField>
      <UiFormField label="Payment terms" class="wide"><UiInput v-model="form.payment_terms" multiline :rows="4" /></UiFormField>
      <UiCheckbox v-model="form.is_verified" label="Verified listing" description="Only verified listings can be activated." class="wide" />
    </form>
    <template #footer><UiButton @click="emit('close')">Cancel</UiButton><UiButton variant="primary" type="submit" form="listing-form" :disabled="busy">{{ busy ? 'Saving...' : 'Save listing' }}</UiButton></template>
  </UiModal>
</template>

<style scoped>
.re-form-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}.wide{grid-column:1/-1}@media(max-width:700px){.re-form-grid{grid-template-columns:1fr}.wide{grid-column:auto}}
</style>
