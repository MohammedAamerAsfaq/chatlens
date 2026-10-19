<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { integrationsApi, realEstateApi } from '@/api'
import UiCheckbox from '@/components/ui/UiCheckbox.vue'
import UiFormField from '@/components/ui/UiFormField.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiRadioGroup from '@/components/ui/UiRadioGroup.vue'
import UiSelect from '@/components/ui/UiSelect.vue'
import PropertyAttributeFields from './PropertyAttributeFields.vue'
import PropertyLocationPicker from './PropertyLocationPicker.vue'
import { areaUnits, completionOptions, furnishingOptions, inventorySourceTypes, marketScopes, ownershipEligibilityOptions, propertyStatuses, tenureOptions } from '../options'
import { emptyProperty } from '../forms'

const props = defineProps({
  formId: { type: String, default: 'property-form' },
  record: { type: Object, default: null },
  propertyTypes: { type: Array, default: () => [] },
  propertyTypeRecords: { type: Array, default: () => [] },
})
const emit = defineEmits(['submit'])
const form = reactive(emptyProperty())
const geography = reactive({ countries: [], areas: [], cities: [], localities: [] })
const developments = ref([]), geographyError = ref('')
const selectedType = computed(() => props.propertyTypeRecords.find(row => row.code === form.property_type))
const fieldDefinitions = computed(() => selectedType.value?.field_definitions || [])
const selectedArea = computed(() => geography.areas.find(row => row.id === Number(form.address.administrative_area_master)))
const selectedCity = computed(() => geography.cities.find(row => row.id === Number(form.address.city_master)))
const selectedCountry = computed(() => geography.countries.find(row => row.id === Number(form.address.country_master)))
const options = rows => [{ value: null, label: 'Not mapped' }, ...rows.map(row => ({ value: row.id, label: row.name }))]
const countryOptions = computed(() => options(geography.countries))
const areaOptions = computed(() => options(geography.areas))
const cityOptions = computed(() => options(geography.cities.filter(row => !form.address.administrative_area_master || row.administrative_area_name === selectedArea.value?.name)))
const localityOptions = computed(() => options(geography.localities.filter(row => form.address.city_master ? row.city_name === selectedCity.value?.name : !form.address.administrative_area_master || row.administrative_area_name === selectedArea.value?.name)))
const developmentOptions = computed(() => options(developments.value))

async function loadHierarchy() {
  geographyError.value = ''
  try {
    const [countries, areas, cities, localities, projects] = await Promise.all([
      integrationsApi.locations({ level: 'country', page_size: 3000 }),
      integrationsApi.locations({ level: 'area', country_code: 'AE', page_size: 3000 }),
      integrationsApi.locations({ level: 'city', country_code: 'AE', page_size: 3000 }),
      integrationsApi.locations({ level: 'locality', country_code: 'AE', page_size: 3000 }),
      realEstateApi.propertyDevelopments({ include_inactive: false, page_size: 100 }),
    ])
    geography.countries = countries.data.results; geography.areas = areas.data.results
    geography.cities = cities.data.results; geography.localities = localities.data.results
    developments.value = projects.data.results
  } catch (error) {
    geographyError.value = error.response?.data?.detail || 'Canonical geography could not be loaded.'
  }
}
function submit() {
  const allowed = new Set(fieldDefinitions.value.map(item => item.code))
  const attributes = Object.fromEntries(Object.entries(form.attributes || {}).filter(([key]) => allowed.has(key)))
  emit('submit', { ...form, attributes, address: { ...form.address } })
}
watch(() => props.record?.id, () => {
  Object.assign(form, emptyProperty(), props.record || {})
  form.address = { ...emptyProperty().address, ...(props.record?.address || {}) }
  loadHierarchy()
}, { immediate: true })
watch(() => form.address.country_master, value => { const row = geography.countries.find(item => item.id === Number(value)); if (row) form.address.country = row.name })
watch(() => form.address.administrative_area_master, value => { const row = geography.areas.find(item => item.id === Number(value)); if (row) form.address.state_region = row.name })
watch(() => form.address.city_master, value => { const row = geography.cities.find(item => item.id === Number(value)); if (row) form.address.city = row.name })
watch(() => form.address.locality_master, value => { const row = geography.localities.find(item => item.id === Number(value)); if (row) form.address.community = row.name })
watch(() => form.address.development_master, value => { const row = developments.value.find(item => item.id === Number(value)); if (row) form.address.project_building = row.name })
</script>

<template><form :id="formId" class="re-form" @submit.prevent="submit">
  <section><h3>Property details</h3><div class="re-form-grid">
    <UiFormField label="Title"><UiInput v-model="form.title" required /></UiFormField><UiFormField label="Reference code"><UiInput v-model="form.reference_code" /></UiFormField>
    <UiFormField label="Property type"><UiSelect v-model="form.property_type" :options="propertyTypes" /></UiFormField><UiFormField v-if="form.source_property_type_label" label="Original source type"><UiInput v-model="form.source_property_type_label" disabled /></UiFormField>
    <UiRadioGroup v-model="form.availability_status" label="Availability" :options="propertyStatuses" /><UiRadioGroup v-model="form.market_scope" label="Market scope" :options="marketScopes" />
    <UiRadioGroup v-model="form.inventory_source_type" label="Inventory type" :options="inventorySourceTypes" /><UiRadioGroup v-model="form.ownership_eligibility" label="Ownership eligibility" :options="ownershipEligibilityOptions" />
    <UiRadioGroup v-model="form.tenure_type" label="Tenure" :options="tenureOptions" /><div class="tracking-field"><span>Inventory tracking</span><UiCheckbox v-model="form.is_tracked" label="Tracked inventory" description="Show this property in tracked inventory views." /></div>
    <UiFormField label="Bedrooms"><UiInput v-model="form.bedrooms" compact type="number" min="0" step="0.5" /></UiFormField><UiFormField label="Bathrooms"><UiInput v-model="form.bathrooms" compact type="number" min="0" step="0.5" /></UiFormField>
    <UiFormField label="Built-up area"><UiInput v-model="form.built_up_area" compact type="number" min="0" step="0.01" /></UiFormField><UiFormField label="Plot area"><UiInput v-model="form.plot_area" compact type="number" min="0" step="0.01" /></UiFormField>
    <UiRadioGroup v-model="form.area_unit" label="Area unit" :options="areaUnits" /><UiRadioGroup v-model="form.furnishing" label="Furnishing" :options="furnishingOptions" /><UiRadioGroup v-model="form.completion_status" label="Completion" :options="completionOptions" />
    <UiFormField label="Completion year"><UiInput v-model="form.completion_year" compact type="number" min="1900" max="2200" /></UiFormField><UiFormField label="Developer"><UiInput v-model="form.developer" /></UiFormField><UiFormField label="Project"><UiInput v-model="form.project_name" /></UiFormField>
    <UiFormField label="Description" class="wide"><UiInput v-model="form.description" multiline :rows="4" /></UiFormField>
  </div></section>
  <section v-if="fieldDefinitions.length"><h3>{{ selectedType?.name }} details</h3><div class="re-form-grid"><PropertyAttributeFields v-model="form.attributes" :definitions="fieldDefinitions" /></div></section>
  <section><h3>Canonical location</h3><p class="section-note">Map the property to trusted reference data. Google address values remain stored separately below.</p><p v-if="geographyError" class="field-error">{{ geographyError }}</p><div class="re-form-grid">
    <UiFormField label="Country master"><UiSelect v-model="form.address.country_master" :options="countryOptions" /></UiFormField><UiFormField label="Emirate / state master"><UiSelect v-model="form.address.administrative_area_master" :options="areaOptions" /></UiFormField>
    <UiFormField label="City master"><UiSelect v-model="form.address.city_master" :options="cityOptions" /></UiFormField><UiFormField label="Locality / community master"><UiSelect v-model="form.address.locality_master" :options="localityOptions" /></UiFormField>
    <UiFormField label="Project / building master" class="wide"><UiSelect v-model="form.address.development_master" :options="developmentOptions" /></UiFormField>
  </div></section>
  <section><h3>Address and map</h3><p class="section-note">Search, click, or drag the marker. Google updates all available source address fields and coordinates; canonical mappings remain operator-controlled.</p><PropertyLocationPicker v-model="form.address" :country-code="selectedCountry?.iso2 || 'AE'" /><div class="re-form-grid address-fields">
    <UiFormField label="Country"><UiInput v-model="form.address.country" /></UiFormField><UiFormField label="State / region"><UiInput v-model="form.address.state_region" /></UiFormField><UiFormField label="City"><UiInput v-model="form.address.city" /></UiFormField><UiFormField label="Community"><UiInput v-model="form.address.community" /></UiFormField>
    <UiFormField label="Building / project"><UiInput v-model="form.address.project_building" /></UiFormField><UiFormField label="Street"><UiInput v-model="form.address.street" /></UiFormField><UiFormField label="Unit"><UiInput v-model="form.address.unit_number" /></UiFormField><UiFormField label="Postal code"><UiInput v-model="form.address.postal_code" /></UiFormField>
    <UiFormField label="Latitude"><UiInput v-model="form.address.latitude" compact type="number" min="-90" max="90" step="0.000001" /></UiFormField><UiFormField label="Longitude"><UiInput v-model="form.address.longitude" compact type="number" min="-180" max="180" step="0.000001" /></UiFormField><UiFormField label="Normalized location" class="wide"><UiInput v-model="form.address.normalized_location" /></UiFormField>
  </div></section>
</form></template>

<style scoped>
.re-form{display:grid;gap:24px}.re-form section{border:1px solid var(--ui-border);border-radius:12px;padding:18px;background:var(--ui-surface)}.re-form h3{margin:0 0 8px}.section-note{margin:0 0 16px;color:var(--ui-text-muted);font-size:.84rem}.field-error{color:var(--ui-danger);font-size:.84rem}.re-form-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}.address-fields{margin-top:18px}.wide{grid-column:1/-1}.tracking-field{display:flex;flex-direction:column;gap:8px;color:var(--ui-text);font-size:.76rem;font-weight:750}.tracking-field .ui-checkbox{min-height:42px;align-items:center}@media(max-width:760px){.re-form-grid{grid-template-columns:1fr}.wide{grid-column:auto}}
</style>
