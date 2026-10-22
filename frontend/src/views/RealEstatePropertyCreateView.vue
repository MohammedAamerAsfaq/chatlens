<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { realEstateApi } from '@/api'
import UiButton from '@/components/ui/UiButton.vue'
import UiNotice from '@/components/ui/UiNotice.vue'
import UiPage from '@/components/ui/UiPage.vue'
import UiPageHeader from '@/components/ui/UiPageHeader.vue'
import PropertyForm from '@/features/realEstate/components/PropertyForm.vue'
import { apiError } from '@/features/realEstate/apiErrors'
import { loadPropertyHierarchy } from '@/features/realEstate/propertyHierarchy'
import { persistProperty } from '@/features/realEstate/propertyPersistence'

const router = useRouter()
const propertyTypeRecords = ref([])
const properties = ref([])
const busy = ref(false), error = ref('')
const propertyTypes = computed(() => propertyTypeRecords.value
  .filter(record => record.is_active)
  .map(record => ({ value: record.code, label: record.name })))

async function loadPropertyTypes() {
  try {
    propertyTypeRecords.value = (await realEstateApi.propertyTypes({
      include_inactive: true, page_size: 100,
    })).data.results
  } catch (exc) {
    error.value = apiError(exc, 'Unable to load property types.')
  }
}
async function loadProperties() {
  try { properties.value = await loadPropertyHierarchy(realEstateApi) }
  catch (exc) { error.value = apiError(exc, 'Unable to load the property hierarchy.') }
}
async function save(values) {
  busy.value = true; error.value = ''
  try {
    await persistProperty(values)
    await router.push({ name: 'real-estate-properties' })
  } catch (exc) {
    error.value = apiError(exc, 'Unable to save the property.')
  } finally { busy.value = false }
}
onMounted(() => Promise.all([loadPropertyTypes(), loadProperties()]))
</script>

<template><UiPage width="wide">
  <UiPageHeader eyebrow="Real Estate Inventory" title="Add property" description="Create a physical property record, map its trusted geography, and capture its source address.">
    <template #actions><UiButton @click="router.push({ name: 'real-estate-properties' })">Cancel</UiButton><UiButton variant="primary" type="submit" form="property-create-form" :disabled="busy">{{ busy ? 'Saving...' : 'Save property' }}</UiButton></template>
  </UiPageHeader>
  <UiNotice v-if="error" tone="danger">{{ error }}</UiNotice>
  <PropertyForm form-id="property-create-form" :property-types="propertyTypes" :property-type-records="propertyTypeRecords" :properties="properties" @submit="save" />
</UiPage></template>
