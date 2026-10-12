<script setup>
import { reactive, watch } from 'vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiFormField from '@/components/ui/UiFormField.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiModal from '@/components/ui/UiModal.vue'
import UiSelect from '@/components/ui/UiSelect.vue'
import { areaUnits, completionOptions, furnishingOptions, propertyStatuses } from '../options'
import { emptyProperty } from '../forms'

const props = defineProps({
  open: Boolean,
  record: { type: Object, default: null },
  busy: Boolean,
  propertyTypes: { type: Array, default: () => [] },
})
const emit = defineEmits(['close', 'save'])
const form = reactive(emptyProperty())

watch(() => [props.open, props.record], () => {
  if (!props.open) return
  Object.assign(form, emptyProperty(), props.record || {})
  form.address = { ...emptyProperty().address, ...(props.record?.address || {}) }
}, { immediate: true, deep: true })

function submit() {
  emit('save', { ...form, address: { ...form.address } })
}
</script>

<template>
  <UiModal :open="open" :title="record ? 'Edit property' : 'Add property'" subtitle="Maintain the physical property separately from its sale or lease listings." size="xlarge" tall @close="emit('close')">
    <form id="property-form" class="re-form" @submit.prevent="submit">
      <section><h3>Property details</h3><div class="re-form-grid">
        <UiFormField label="Title"><UiInput v-model="form.title" required /></UiFormField>
        <UiFormField label="Reference code"><UiInput v-model="form.reference_code" /></UiFormField>
        <UiFormField label="Property type"><UiSelect v-model="form.property_type" :options="props.propertyTypes" /></UiFormField>
        <UiFormField label="Availability"><UiSelect v-model="form.availability_status" :options="propertyStatuses" /></UiFormField>
        <UiFormField label="Bedrooms"><UiInput v-model="form.bedrooms" type="number" min="0" step="0.5" /></UiFormField>
        <UiFormField label="Bathrooms"><UiInput v-model="form.bathrooms" type="number" min="0" step="0.5" /></UiFormField>
        <UiFormField label="Built-up area"><UiInput v-model="form.built_up_area" type="number" min="0" step="0.01" /></UiFormField>
        <UiFormField label="Plot area"><UiInput v-model="form.plot_area" type="number" min="0" step="0.01" /></UiFormField>
        <UiFormField label="Area unit"><UiSelect v-model="form.area_unit" :options="areaUnits" /></UiFormField>
        <UiFormField label="Furnishing"><UiSelect v-model="form.furnishing" :options="furnishingOptions" /></UiFormField>
        <UiFormField label="Completion"><UiSelect v-model="form.completion_status" :options="completionOptions" /></UiFormField>
        <UiFormField label="Completion year"><UiInput v-model="form.completion_year" type="number" min="1900" max="2200" /></UiFormField>
        <UiFormField label="Developer"><UiInput v-model="form.developer" /></UiFormField>
        <UiFormField label="Project"><UiInput v-model="form.project_name" /></UiFormField>
        <UiFormField label="Description" class="wide"><UiInput v-model="form.description" multiline :rows="4" /></UiFormField>
      </div></section>
      <section><h3>Address</h3><div class="re-form-grid">
        <UiFormField label="Country"><UiInput v-model="form.address.country" /></UiFormField>
        <UiFormField label="State / region"><UiInput v-model="form.address.state_region" /></UiFormField>
        <UiFormField label="City"><UiInput v-model="form.address.city" /></UiFormField>
        <UiFormField label="Community"><UiInput v-model="form.address.community" /></UiFormField>
        <UiFormField label="Building / project"><UiInput v-model="form.address.project_building" /></UiFormField>
        <UiFormField label="Street"><UiInput v-model="form.address.street" /></UiFormField>
        <UiFormField label="Unit"><UiInput v-model="form.address.unit_number" /></UiFormField>
        <UiFormField label="Postal code"><UiInput v-model="form.address.postal_code" /></UiFormField>
        <UiFormField label="Latitude"><UiInput v-model="form.address.latitude" type="number" min="-90" max="90" step="0.000001" placeholder="25.204849" /></UiFormField>
        <UiFormField label="Longitude"><UiInput v-model="form.address.longitude" type="number" min="-180" max="180" step="0.000001" placeholder="55.270783" /></UiFormField>
        <UiFormField label="Normalized location" class="wide"><UiInput v-model="form.address.normalized_location" /></UiFormField>
      </div></section>
    </form>
    <template #footer><UiButton @click="emit('close')">Cancel</UiButton><UiButton variant="primary" type="submit" form="property-form" :disabled="busy">{{ busy ? 'Saving...' : 'Save property' }}</UiButton></template>
  </UiModal>
</template>

<style scoped>
.re-form{display:grid;gap:24px}.re-form section{border:1px solid var(--ui-border);border-radius:12px;padding:18px}.re-form h3{margin:0 0 16px}.re-form-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}.wide{grid-column:1/-1}@media(max-width:760px){.re-form-grid{grid-template-columns:1fr}.wide{grid-column:auto}}
</style>
