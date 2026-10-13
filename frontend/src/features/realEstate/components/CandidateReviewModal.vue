<script setup>
import { computed, reactive, ref, watch } from 'vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiFormField from '@/components/ui/UiFormField.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiModal from '@/components/ui/UiModal.vue'
import UiSelect from '@/components/ui/UiSelect.vue'
import UiTabs from '@/components/ui/UiTabs.vue'
import PropertyAttributeFields from './PropertyAttributeFields.vue'
import {
  areaUnits, furnishingOptions, inventorySourceTypes, ownershipEligibilityOptions,
  paymentFrequencies, tenureOptions,
} from '../options'

const props = defineProps({
  open: Boolean,
  candidate: { type: Object, default: null },
  listings: { type: Array, default: () => [] },
  propertyTypes: { type: Array, default: () => [] },
  propertyTypeRecords: { type: Array, default: () => [] },
  busy: Boolean,
})
const emit = defineEmits(['close', 'promote', 'merge', 'reject'])
const mode = ref('promote')
const listingId = ref('')
const form = reactive({})
const tabs = [{ value: 'promote', label: 'Create property' }, { value: 'merge', label: 'Merge into listing' }]
const listingOptions = computed(() => props.listings.map(item => ({ value: item.id, label: `#${item.id} ${item.property_title} - ${item.listing_type} ${item.asking_price} ${item.currency}` })))
const isLease = computed(() => props.candidate?.activity_type === 'leasing_offer')
const selectedType = computed(() => props.propertyTypeRecords.find(record => record.code === form.property_type))
const fieldDefinitions = computed(() => selectedType.value?.field_definitions || [])

watch(() => [props.open, props.candidate], () => {
  if (!props.open || !props.candidate) return
  mode.value = 'promote'; listingId.value = ''
  Object.assign(form, {
    title: props.candidate.title || '', property_type: props.candidate.property_type || 'other',
    description: props.candidate.description || '', bedrooms: props.candidate.bedrooms ?? '',
    bathrooms: props.candidate.bathrooms ?? '', built_up_area: props.candidate.area ?? '',
    area_unit: props.candidate.area_unit || 'sqft', furnishing: props.candidate.furnishing || 'unknown',
    normalized_location: props.candidate.location_raw || '', asking_price: props.candidate.asking_price ?? '',
    currency: props.candidate.currency || 'AED', payment_frequency: isLease.value ? 'yearly' : 'not_applicable',
    inventory_source_type: props.candidate.inventory_source_type || 'floating',
    is_tracked: Boolean(props.candidate.is_tracked),
    ownership_eligibility: props.candidate.ownership_eligibility || 'all',
    tenure_type: props.candidate.tenure_type || '', attributes: { ...(props.candidate.attributes || {}) },
  })
}, { immediate: true, deep: true })

function promote() {
  const allowed = new Set(fieldDefinitions.value.map(item => item.code))
  const attributes = Object.fromEntries(Object.entries(form.attributes || {}).filter(([key]) => allowed.has(key)))
  emit('promote', {
    property: {
      title: form.title, property_type: form.property_type, description: form.description,
      bedrooms: form.bedrooms || null, bathrooms: form.bathrooms || null,
      built_up_area: form.built_up_area || null, area_unit: form.area_unit,
      furnishing: form.furnishing, address: { normalized_location: form.normalized_location },
      inventory_source_type: form.inventory_source_type, is_tracked: form.is_tracked,
      ownership_eligibility: form.ownership_eligibility, tenure_type: form.tenure_type,
      attributes,
    },
    listing: {
      asking_price: form.asking_price, currency: form.currency,
      payment_frequency: form.payment_frequency, status: 'draft',
    },
  })
}
</script>

<template>
  <UiModal :open="open" title="Review property candidate" :subtitle="candidate?.title || 'AI-extracted supply candidate'" size="xlarge" tall @close="emit('close')">
    <UiTabs v-model="mode" :tabs="tabs" />
    <form v-if="mode === 'promote'" id="candidate-form" class="candidate-form" @submit.prevent="promote">
      <UiFormField label="Property title" class="wide"><UiInput v-model="form.title" required /></UiFormField>
      <UiFormField label="Property type"><UiSelect v-model="form.property_type" :options="props.propertyTypes" /></UiFormField>
      <UiFormField label="Location"><UiInput v-model="form.normalized_location" /></UiFormField>
      <UiFormField label="Inventory type"><UiSelect v-model="form.inventory_source_type" :options="inventorySourceTypes" /></UiFormField>
      <UiFormField label="Ownership eligibility"><UiSelect v-model="form.ownership_eligibility" :options="ownershipEligibilityOptions" /></UiFormField>
      <UiFormField label="Tenure"><UiSelect v-model="form.tenure_type" :options="tenureOptions" /></UiFormField>
      <UiFormField label="Tracked inventory"><label class="check-row"><input v-model="form.is_tracked" type="checkbox" /> Track after promotion</label></UiFormField>
      <UiFormField label="Bedrooms"><UiInput v-model="form.bedrooms" type="number" min="0" step="0.5" /></UiFormField>
      <UiFormField label="Bathrooms"><UiInput v-model="form.bathrooms" type="number" min="0" step="0.5" /></UiFormField>
      <UiFormField label="Area"><UiInput v-model="form.built_up_area" type="number" min="0" step="0.01" /></UiFormField>
      <UiFormField label="Area unit"><UiSelect v-model="form.area_unit" :options="areaUnits" /></UiFormField>
      <UiFormField label="Furnishing"><UiSelect v-model="form.furnishing" :options="furnishingOptions" /></UiFormField>
      <UiFormField label="Asking price"><UiInput v-model="form.asking_price" type="number" min="0" step="0.01" required /></UiFormField>
      <UiFormField label="Currency"><UiInput v-model="form.currency" maxlength="3" /></UiFormField>
      <UiFormField v-if="isLease" label="Payment frequency"><UiSelect v-model="form.payment_frequency" :options="paymentFrequencies" /></UiFormField>
      <template v-if="fieldDefinitions.length">
        <div class="section-title wide">{{ selectedType?.name }} details</div>
        <PropertyAttributeFields v-model="form.attributes" :definitions="fieldDefinitions" />
      </template>
      <UiFormField label="Description" class="wide"><UiInput v-model="form.description" multiline :rows="4" /></UiFormField>
    </form>
    <div v-else class="merge-form"><UiFormField label="Existing listing"><UiSelect v-model="listingId" :options="listingOptions" searchable placeholder="Select a verified listing" /></UiFormField><p>The candidate will remain auditable and point to the selected existing listing.</p></div>
    <template #footer><UiButton variant="danger" :disabled="busy" @click="emit('reject')">Reject candidate</UiButton><span class="spacer"></span><UiButton @click="emit('close')">Cancel</UiButton><UiButton v-if="mode === 'promote'" variant="primary" type="submit" form="candidate-form" :disabled="busy">Create verified draft</UiButton><UiButton v-else variant="primary" :disabled="busy || !listingId" @click="emit('merge', listingId)">Merge candidate</UiButton></template>
  </UiModal>
</template>

<style scoped>
.candidate-form{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px;margin-top:18px}.wide{grid-column:1/-1}.section-title{font-weight:700;border-top:1px solid var(--ui-border);padding-top:16px}.check-row{display:flex;align-items:center;gap:8px;min-height:42px}.merge-form{display:grid;gap:12px;margin-top:24px}.merge-form p{color:var(--ui-text-subtle)}.spacer{flex:1}@media(max-width:700px){.candidate-form{grid-template-columns:1fr}.wide{grid-column:auto}}
</style>
