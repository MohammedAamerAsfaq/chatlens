<script setup>
import { computed, reactive, watch } from 'vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiFormField from '@/components/ui/UiFormField.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiModal from '@/components/ui/UiModal.vue'
import UiSelect from '@/components/ui/UiSelect.vue'
import PropertyAttributeFields from './PropertyAttributeFields.vue'
import {
  areaUnits, completionOptions, furnishingOptions, inventorySourceTypes,
  marketScopes, ownershipEligibilityOptions, propertyStatuses, tenureOptions,
} from '../options'
import { emptyProperty } from '../forms'

const props = defineProps({
  open: Boolean,
  record: { type: Object, default: null },
  busy: Boolean,
  propertyTypes: { type: Array, default: () => [] },
  propertyTypeRecords: { type: Array, default: () => [] },
})
const emit = defineEmits(['close', 'save'])
const form = reactive(emptyProperty())
const selectedType = computed(() => props.propertyTypeRecords.find(record => record.code === form.property_type))
const fieldDefinitions = computed(() => selectedType.value?.field_definitions || [])

watch(() => [props.open, props.record], () => {
  if (!props.open) return
  Object.assign(form, emptyProperty(), props.record || {})
  form.address = { ...emptyProperty().address, ...(props.record?.address || {}) }
}, { immediate: true, deep: true })

function submit() {
  const allowed = new Set(fieldDefinitions.value.map(item => item.code))
  const attributes = Object.fromEntries(Object.entries(form.attributes || {}).filter(([key]) => allowed.has(key)))
  emit('save', { ...form, attributes, address: { ...form.address } })
}
</script>

<template>
  <UiModal :open="open" :title="record ? 'Edit property' : 'Add property'" subtitle="Maintain the physical property separately from its sale or lease listings." size="xlarge" tall @close="emit('close')">
    <form id="property-form" class="re-form" @submit.prevent="submit">
      <section><h3>Property details</h3><div class="re-form-grid">
        <UiFormField label="Title"><UiInput v-model="form.title" required /></UiFormField>
        <UiFormField label="Reference code"><UiInput v-model="form.reference_code" /></UiFormField>
        <UiFormField label="Property type"><UiSelect v-model="form.property_type" :options="props.propertyTypes" /></UiFormField>
        <UiFormField v-if="form.source_property_type_label" label="Original source type"><UiInput v-model="form.source_property_type_label" disabled /></UiFormField>
        <UiFormField label="Availability"><UiSelect v-model="form.availability_status" :options="propertyStatuses" /></UiFormField>
        <UiFormField label="Market scope"><UiSelect v-model="form.market_scope" :options="marketScopes" /></UiFormField>
        <UiFormField label="Inventory type"><UiSelect v-model="form.inventory_source_type" :options="inventorySourceTypes" /></UiFormField>
        <UiFormField label="Ownership eligibility"><UiSelect v-model="form.ownership_eligibility" :options="ownershipEligibilityOptions" /></UiFormField>
        <UiFormField label="Tenure"><UiSelect v-model="form.tenure_type" :options="tenureOptions" /></UiFormField>
        <UiFormField label="Tracked inventory"><label class="check-row"><input v-model="form.is_tracked" type="checkbox" /> Track this property across inventory views</label></UiFormField>
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
      <section v-if="fieldDefinitions.length"><h3>{{ selectedType?.name }} details</h3><div class="re-form-grid">
        <PropertyAttributeFields v-model="form.attributes" :definitions="fieldDefinitions" />
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
.re-form{display:grid;gap:24px}.re-form section{border:1px solid var(--ui-border);border-radius:12px;padding:18px}.re-form h3{margin:0 0 16px}.re-form-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}.wide{grid-column:1/-1}.check-row{display:flex;align-items:center;gap:8px;min-height:42px}@media(max-width:760px){.re-form-grid{grid-template-columns:1fr}.wide{grid-column:auto}}
</style>
