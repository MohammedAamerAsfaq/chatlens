<script setup>
import { computed } from 'vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiDatePicker from '@/components/ui/UiDatePicker.vue'
import UiFormField from '@/components/ui/UiFormField.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiRadioGroup from '@/components/ui/UiRadioGroup.vue'
import UiSelect from '@/components/ui/UiSelect.vue'
import PropertyAttributeFields from './PropertyAttributeFields.vue'
import { areaUnits, furnishingOptions, ownershipEligibilityOptions, tenureOptions } from '../options'

const props = defineProps({
  modelValue: { type: Object, required: true },
  index: { type: Number, required: true },
  propertyTypes: { type: Array, default: () => [] },
  propertyTypeRecords: { type: Array, default: () => [] },
  demand: { type: Boolean, default: true },
  removable: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue', 'remove'])
const selectedType = computed(() => props.propertyTypeRecords.find(row => row.code === props.modelValue.property_type))
const definitions = computed(() => selectedType.value?.field_definitions || [])

function update(field, value) {
  emit('update:modelValue', { ...props.modelValue, [field]: value })
}
function csv(field) {
  return (props.modelValue[field] || []).join(', ')
}
function updateCsv(field, value) {
  update(field, String(value).split(',').map(item => item.trim()).filter(Boolean))
}
</script>

<template>
  <section class="inquiry-item">
    <header>
      <div><h3>Property {{ index + 1 }}</h3><p>Add one property requirement or offer per section.</p></div>
      <UiButton v-if="removable" size="small" variant="danger" @click="emit('remove')">
        <i class="fa-solid fa-trash"></i> Remove
      </UiButton>
    </header>
    <div class="item-grid">
      <UiFormField label="Property title"><UiInput :model-value="modelValue.title" required @update:model-value="update('title', $event)" /></UiFormField>
      <UiFormField label="Property type"><UiSelect :model-value="modelValue.property_type" :options="propertyTypes" placeholder="Select property type" searchable required @update:model-value="update('property_type', $event)" /></UiFormField>
      <UiFormField label="Locations" hint="Separate acceptable locations with commas." class="wide"><UiInput :model-value="csv('locations')" required @update:model-value="updateCsv('locations', $event)" /></UiFormField>
      <UiFormField label="Property reference"><UiInput :model-value="modelValue.reference_code" @update:model-value="update('reference_code', $event)" /></UiFormField>
      <UiFormField label="Timeframe"><UiInput :model-value="modelValue.timeframe" placeholder="Immediately, within 3 months..." @update:model-value="update('timeframe', $event)" /></UiFormField>
      <div class="range-field"><span>Bedrooms</span><UiInput :model-value="modelValue.bedrooms_min" compact type="number" min="0" step="0.5" placeholder="Min" @update:model-value="update('bedrooms_min', $event)" /><UiInput :model-value="modelValue.bedrooms_max" compact type="number" min="0" step="0.5" placeholder="Max" @update:model-value="update('bedrooms_max', $event)" /></div>
      <div class="range-field"><span>Bathrooms</span><UiInput :model-value="modelValue.bathrooms_min" compact type="number" min="0" step="0.5" placeholder="Min" @update:model-value="update('bathrooms_min', $event)" /><UiInput :model-value="modelValue.bathrooms_max" compact type="number" min="0" step="0.5" placeholder="Max" @update:model-value="update('bathrooms_max', $event)" /></div>
      <div class="range-field"><span>Area</span><UiInput :model-value="modelValue.area_min" compact type="number" min="0" step="0.01" placeholder="Min" @update:model-value="update('area_min', $event)" /><UiInput :model-value="modelValue.area_max" compact type="number" min="0" step="0.01" placeholder="Max" @update:model-value="update('area_max', $event)" /></div>
      <UiRadioGroup :model-value="modelValue.area_unit" label="Area unit" :options="areaUnits" @update:model-value="update('area_unit', $event)" />
      <div class="range-field"><span>{{ demand ? 'Budget' : 'Asking price' }}</span><UiInput :model-value="modelValue.amount_min" compact type="number" min="0" step="0.01" placeholder="Min" @update:model-value="update('amount_min', $event)" /><UiInput :model-value="modelValue.amount_max" compact type="number" min="0" step="0.01" placeholder="Max" @update:model-value="update('amount_max', $event)" /></div>
      <UiFormField label="Currency"><UiInput :model-value="modelValue.currency" maxlength="3" @update:model-value="update('currency', String($event).toUpperCase())" /></UiFormField>
      <UiRadioGroup :model-value="modelValue.furnishing" label="Furnishing" :options="furnishingOptions" @update:model-value="update('furnishing', $event)" />
      <UiRadioGroup :model-value="modelValue.ownership_eligibility" label="Ownership eligibility" :options="ownershipEligibilityOptions" @update:model-value="update('ownership_eligibility', $event)" />
      <UiRadioGroup :model-value="modelValue.tenure_type" label="Tenure" :options="tenureOptions" @update:model-value="update('tenure_type', $event)" />
      <UiFormField v-if="!demand" label="Available from"><UiDatePicker :model-value="modelValue.available_from" @update:model-value="update('available_from', $event)" /></UiFormField>
      <UiFormField label="Required amenities" hint="Hard requirements, separated with commas."><UiInput :model-value="csv('required_amenities')" @update:model-value="updateCsv('required_amenities', $event)" /></UiFormField>
      <UiFormField label="Preferred amenities" hint="Nice-to-have features, separated with commas."><UiInput :model-value="csv('preferred_amenities')" @update:model-value="updateCsv('preferred_amenities', $event)" /></UiFormField>
      <UiFormField v-if="demand" label="Hard constraints" class="wide"><UiInput :model-value="modelValue.free_form_constraints" multiline :rows="2" @update:model-value="update('free_form_constraints', $event)" /></UiFormField>
      <div v-if="definitions.length" class="attribute-grid wide"><PropertyAttributeFields :model-value="modelValue.attributes" :definitions="definitions" @update:model-value="update('attributes', $event)" /></div>
      <UiFormField label="Property details" class="wide"><UiInput :model-value="modelValue.description" multiline :rows="3" @update:model-value="update('description', $event)" /></UiFormField>
    </div>
  </section>
</template>

<style scoped>
.inquiry-item{padding:18px;border:1px solid var(--ui-border);border-radius:var(--ui-radius-md);background:var(--ui-surface)}header{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;margin-bottom:16px}h3{margin:0;color:var(--ui-text-strong);font-size:1rem}header p{margin:3px 0 0;color:var(--ui-text-muted);font-size:.78rem}.item-grid,.attribute-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}.wide{grid-column:1/-1}.range-field{display:grid;grid-template-columns:84px 1fr 1fr;align-items:center;gap:8px}.range-field>span{color:var(--ui-text);font-size:.76rem;font-weight:750}@media(max-width:760px){.item-grid,.attribute-grid{grid-template-columns:1fr}.wide{grid-column:auto}.range-field{grid-template-columns:1fr 1fr}.range-field>span{grid-column:1/-1}}
</style>
