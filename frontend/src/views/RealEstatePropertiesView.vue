<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { FontAwesomeIcon } from '@fortawesome/vue-fontawesome'
import { faBoxArchive, faChartLine, faCrosshairs, faEyeSlash, faImages, faPenToSquare } from '@fortawesome/free-solid-svg-icons'
import { realEstateApi } from '@/api'
import UiBadge from '@/components/ui/UiBadge.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiConfirmModal from '@/components/ui/UiConfirmModal.vue'
import UiDataTable from '@/components/ui/UiDataTable.vue'
import UiNotice from '@/components/ui/UiNotice.vue'
import UiPage from '@/components/ui/UiPage.vue'
import UiPageHeader from '@/components/ui/UiPageHeader.vue'
import UiSelect from '@/components/ui/UiSelect.vue'
import PropertyEditorModal from '@/features/realEstate/components/PropertyEditorModal.vue'
import PropertyDevelopmentManagerModal from '@/features/realEstate/components/PropertyDevelopmentManagerModal.vue'
import PropertyImportModal from '@/features/realEstate/components/PropertyImportModal.vue'
import PropertyMediaModal from '@/features/realEstate/components/PropertyMediaModal.vue'
import PropertyMarketActivityModal from '@/features/realEstate/components/PropertyMarketActivityModal.vue'
import PropertyTypeManagerModal from '@/features/realEstate/components/PropertyTypeManagerModal.vue'
import { apiError, downloadBlob } from '@/features/realEstate/apiErrors'
import { persistProperty } from '@/features/realEstate/propertyPersistence'
import {
  inventoryFilters, ownershipEligibilityOptions, propertyStatuses, tenureOptions, title,
} from '@/features/realEstate/options'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const rows = ref([]), total = ref(0), page = ref(1), pageSize = ref(25), loading = ref(false)
const sortKey = ref('updated_at'), sortDirection = ref('desc'), error = ref('')
const filters = reactive({
  search: '', property_type: '', status: '', inventory_type: '',
  ownership_eligibility: '', tenure_type: '',
})
const editor = reactive({ open: false, record: null, busy: false })
const media = reactive({ open: false, property: null, busy: false })
const market = reactive({ open: false, property: null, activity: null, loading: false })
const importer = reactive({ open: false, rows: [], busy: false, error: '' })
const archive = reactive({ open: false, record: null, busy: false })
const embeddings = reactive({ total: 0, embedded: 0, pending: 0, error: 0, missing: 0, busy: false })
const propertyTypeRecords = ref([])
const typeManager = reactive({ open: false, busy: false })
const developmentManager = reactive({ open: false })
const canManage = computed(() => auth.hasPermission('real_estate.properties.manage'))
const propertyTypeOptions = computed(() => propertyTypeRecords.value
  .filter(record => record.is_active)
  .map(record => ({ value: record.code, label: record.name })))
const filterTypes = computed(() => [{ value: '', label: 'All property types' }, ...propertyTypeOptions.value])
const filterStatuses = [{ value: '', label: 'All statuses' }, ...propertyStatuses]
const filterEligibility = [{ value: '', label: 'All eligibility' }, ...ownershipEligibilityOptions]
const filterTenure = [{ value: '', label: 'All tenure' }, ...tenureOptions.filter(item => item.value)]
const columns = [
  { key: 'title', label: 'Property', sortable: true, width: '19rem', cellClass: 'property-title-cell' },
  { key: 'property_type', label: 'Type', sortable: true, width: '8rem' },
  { key: 'location', label: 'Location', width: '14rem', cellClass: 'property-location-cell' },
  { key: 'bedrooms', label: 'Beds', sortable: true, width: '5rem' },
  { key: 'built_up_area', label: 'Area', sortable: true, width: '7rem' },
  { key: 'inventory_source_type', label: 'Inventory', sortable: true, width: '8rem' },
  { key: 'tenure_type', label: 'Tenure', width: '8rem' },
  { key: 'availability_status', label: 'Status', sortable: true, width: '7rem' },
  { key: 'media', label: 'Media', exportable: false, width: '5rem' },
  { key: 'actions', label: '', exportable: false, width: '11rem', cellClass: 'property-actions-cell' },
]

async function load() {
  loading.value = true; error.value = ''
  try {
    const { data } = await realEstateApi.properties({ page: page.value, page_size: pageSize.value, ...filters, ordering: `${sortDirection.value === 'desc' ? '-' : ''}${sortKey.value}` })
    rows.value = data.results; total.value = data.count
  } catch (exc) { error.value = apiError(exc, 'Unable to load properties.') }
  finally { loading.value = false }
}
async function loadEmbeddingStatus() {
  try { Object.assign(embeddings, (await realEstateApi.realEstateEmbeddingStatus()).data) }
  catch (exc) { error.value = apiError(exc, 'Unable to load Real Estate embedding status.') }
}
async function loadPropertyTypes() {
  try {
    propertyTypeRecords.value = (await realEstateApi.propertyTypes({ include_inactive: true, page_size: 100 })).data.results
  } catch (exc) { error.value = apiError(exc, 'Unable to load property types.') }
}
async function savePropertyType(values) {
  typeManager.busy = true; error.value = ''
  try {
    const payload = { ...values }; delete payload.id; delete payload.created_at; delete payload.updated_at
    if (values.id) await realEstateApi.updatePropertyType(values.id, payload)
    else await realEstateApi.createPropertyType(payload)
    await loadPropertyTypes()
  } catch (exc) { error.value = apiError(exc, 'Unable to save the property type.') }
  finally { typeManager.busy = false }
}
async function deactivatePropertyType(record) {
  typeManager.busy = true; error.value = ''
  try { await realEstateApi.deactivatePropertyType(record.id); await loadPropertyTypes() }
  catch (exc) { error.value = apiError(exc, 'Unable to deactivate the property type.') }
  finally { typeManager.busy = false }
}
function developmentError(exc) { error.value = apiError(exc, 'Unable to maintain projects and buildings.') }
async function repairEmbeddings() {
  embeddings.busy = true; error.value = ''
  try { await realEstateApi.backfillRealEstateEmbeddings(); await loadEmbeddingStatus() }
  catch (exc) { error.value = apiError(exc, 'Unable to queue Real Estate embeddings.') }
  finally { embeddings.busy = false }
}
function openEditor(record = null) { editor.record = record; editor.open = true }
async function saveProperty(values) {
  editor.busy = true; error.value = ''
  try {
    await persistProperty(values, editor.record)
    editor.open = false; await load()
  } catch (exc) { error.value = apiError(exc, 'Unable to save the property.') }
  finally { editor.busy = false }
}
function openMedia(record) { media.property = record; media.open = true }
async function openMarketActivity(record) {
  market.open = true; market.property = record; market.activity = null; market.loading = true
  try { market.activity = (await realEstateApi.propertyMarketActivity(record.id)).data }
  catch (exc) { error.value = apiError(exc, 'Unable to load property market activity.') }
  finally { market.loading = false }
}
async function uploadMedia(values) {
  media.busy = true
  const data = new FormData(); data.append('property', media.property.id); data.append('media_type', values.media_type); data.append('caption', values.caption); data.append('is_primary', values.is_primary)
  if (values.file) { data.append('file', values.file); data.append('file_name', values.file.name); data.append('mime_type', values.file.type) } else data.append('external_url', values.external_url)
  try { await realEstateApi.createMedia(data); await refreshMedia() } catch (exc) { error.value = apiError(exc, 'Unable to add media.') } finally { media.busy = false }
}
async function removeMedia(item) { media.busy = true; try { await realEstateApi.deleteMedia(item.id); await refreshMedia() } catch (exc) { error.value = apiError(exc) } finally { media.busy = false } }
async function refreshMedia() { await load(); media.property = rows.value.find(row => row.id === media.property.id) || media.property }
async function previewImport(file) { importer.busy = true; importer.error = ''; try { importer.rows = (await realEstateApi.previewPropertyImport(file)).data.rows } catch (exc) { importer.error = apiError(exc) } finally { importer.busy = false } }
async function reviewImportRows(rows) { importer.busy = true; importer.error = ''; try { importer.rows = (await realEstateApi.reviewPropertyImportRows(rows)).data.rows } catch (exc) { importer.error = apiError(exc) } finally { importer.busy = false } }
async function importRows(importRows) { importer.busy = true; try { await realEstateApi.importProperties(importRows); importer.open = false; importer.rows = []; await load() } catch (exc) { importer.error = apiError(exc) } finally { importer.busy = false } }
async function exportAll() { try { const { data } = await realEstateApi.exportProperties(filters); downloadBlob(data, 'real-estate-properties.csv') } catch (exc) { error.value = apiError(exc, 'Unable to export properties.') } }
async function confirmArchive() { archive.busy = true; try { await realEstateApi.archiveProperty(archive.record.id); archive.open = false; await load() } catch (exc) { error.value = apiError(exc) } finally { archive.busy = false } }
async function toggleTracked(record) {
  try { await realEstateApi.updateProperty(record.id, { is_tracked: !record.is_tracked }); await load() }
  catch (exc) { error.value = apiError(exc, 'Unable to update tracking.') }
}
function resetAndLoad() { if (page.value !== 1) page.value = 1; else load() }
watch(() => [
  filters.search, filters.property_type, filters.status, filters.inventory_type,
  filters.ownership_eligibility, filters.tenure_type,
], resetAndLoad)
watch([page, pageSize, sortKey, sortDirection], load)
onMounted(() => Promise.all([load(), loadEmbeddingStatus(), loadPropertyTypes()]))
</script>

<template><UiPage width="wide"><UiPageHeader eyebrow="Real Estate Inventory" title="Properties" description="Maintain verified physical property records independently from sale and lease listings."><template #actions><UiBadge :tone="embeddings.error ? 'danger' : (embeddings.pending || embeddings.missing) ? 'warning' : 'success'">Embeddings {{ embeddings.embedded }}/{{ embeddings.total }}</UiBadge><UiButton v-if="canManage" @click="typeManager.open = true">Property types</UiButton><UiButton v-if="canManage" @click="developmentManager.open = true">Projects / buildings</UiButton><UiButton v-if="canManage" :loading="embeddings.busy" @click="repairEmbeddings">Repair embeddings</UiButton><UiButton @click="exportAll">Export CSV</UiButton><UiButton v-if="canManage" @click="importer.open = true">Import CSV</UiButton><UiButton v-if="canManage" variant="primary" @click="router.push({ name: 'real-estate-property-create' })">+ Add property</UiButton></template></UiPageHeader><UiNotice v-if="error" tone="danger">{{ error }}</UiNotice>
  <UiDataTable class="properties-table" :columns="columns" :rows="rows" :loading="loading" :total="total" :page="page" :page-size="pageSize" :sort-key="sortKey" :sort-direction="sortDirection" :search="filters.search" persist-key="real-estate-properties" search-placeholder="Search title, reference, or project..." empty-title="No properties match these filters." @update:page="page = $event" @update:page-size="pageSize = $event; page = 1" @update:sort-key="sortKey = $event" @update:sort-direction="sortDirection = $event" @update:search="filters.search = $event" @refresh="load">
    <template #filters><UiSelect v-model="filters.inventory_type" :options="inventoryFilters" /><UiSelect v-model="filters.property_type" :options="filterTypes" /><UiSelect v-model="filters.status" :options="filterStatuses" /><UiSelect v-model="filters.ownership_eligibility" :options="filterEligibility" /><UiSelect v-model="filters.tenure_type" :options="filterTenure" /></template>
    <template #cell-title="{ row }"><strong>{{ row.title }}</strong><small class="subline">{{ row.reference_code || `#${row.id}` }}</small></template>
    <template #cell-property_type="{ value }">{{ title(value) }}</template><template #cell-location="{ row }">{{ row.address?.normalized_location || [row.address?.community, row.address?.city].filter(Boolean).join(', ') || '-' }}</template>
    <template #cell-built_up_area="{ row }">{{ row.built_up_area ? `${row.built_up_area} ${row.area_unit}` : '-' }}</template><template #cell-inventory_source_type="{ row }"><UiBadge :tone="row.is_tracked ? 'success' : 'neutral'">{{ row.is_tracked ? 'Tracked' : title(row.inventory_source_type) }}</UiBadge><small v-if="row.is_tracked" class="subline">{{ title(row.inventory_source_type) }}</small></template><template #cell-tenure_type="{ value }">{{ value ? title(value) : '-' }}</template><template #cell-availability_status="{ value }"><UiBadge :tone="value === 'available' ? 'success' : 'neutral'">{{ title(value) }}</UiBadge></template>
    <template #cell-media="{ row }">{{ row.media.length }}</template><template #cell-actions="{ row }"><div class="actions"><UiButton class="property-action" size="small" title="Market activity" aria-label="Market activity" @click.stop="openMarketActivity(row)"><FontAwesomeIcon :icon="faChartLine" /></UiButton><UiButton class="property-action" size="small" title="Manage media" aria-label="Manage media" @click.stop="openMedia(row)"><FontAwesomeIcon :icon="faImages" /></UiButton><UiButton v-if="canManage" class="property-action" size="small" :title="row.is_tracked ? 'Stop tracking' : 'Track property'" :aria-label="row.is_tracked ? 'Stop tracking' : 'Track property'" @click.stop="toggleTracked(row)"><FontAwesomeIcon :icon="row.is_tracked ? faEyeSlash : faCrosshairs" /></UiButton><UiButton v-if="canManage" class="property-action" size="small" title="Edit property" aria-label="Edit property" @click.stop="openEditor(row)"><FontAwesomeIcon :icon="faPenToSquare" /></UiButton><UiButton v-if="canManage" class="property-action" size="small" variant="danger" title="Archive property" aria-label="Archive property" @click.stop="archive.record = row; archive.open = true"><FontAwesomeIcon :icon="faBoxArchive" /></UiButton></div></template>
  </UiDataTable>
  <PropertyEditorModal :open="editor.open" :record="editor.record" :busy="editor.busy" :property-types="propertyTypeOptions" :property-type-records="propertyTypeRecords" @close="editor.open = false" @save="saveProperty" /><PropertyMediaModal :open="media.open" :property="media.property" :busy="media.busy" @close="media.open = false" @upload="uploadMedia" @remove="removeMedia" /><PropertyMarketActivityModal :open="market.open" :property="market.property" :activity="market.activity" :loading="market.loading" @close="market.open = false" /><PropertyImportModal :open="importer.open" :rows="importer.rows" :busy="importer.busy" :error="importer.error" :property-types="propertyTypeOptions" :property-type-records="propertyTypeRecords" @close="importer.open = false" @preview="previewImport" @review="reviewImportRows" @import="importRows" /><PropertyTypeManagerModal :open="typeManager.open" :records="propertyTypeRecords" :busy="typeManager.busy" @close="typeManager.open = false" @save="savePropertyType" @deactivate="deactivatePropertyType" /><PropertyDevelopmentManagerModal :open="developmentManager.open" @close="developmentManager.open = false" @changed="load" @error="developmentError" /><UiConfirmModal :open="archive.open" title="Archive property" :message="`Archive ${archive.record?.title || 'this property'} and close its listings?`" confirm-label="Archive" danger :busy="archive.busy" @cancel="archive.open = false" @confirm="confirmArchive" />
</UiPage></template>

<style scoped>
.subline{display:block;color:var(--ui-text-subtle);margin-top:3px}
.actions{display:flex;align-items:center;gap:6px;white-space:nowrap}
.property-action{width:30px;min-width:30px;padding:0}
.properties-table :deep(.ui-data-table__toolbar){display:grid;grid-template-columns:minmax(0,1fr);align-items:center}
.properties-table :deep(.ui-data-table__filters){display:grid;grid-template-columns:repeat(5,minmax(140px,1fr));width:100%;min-width:0}
.properties-table :deep(.ui-data-table__filters>.choices){width:100%;min-width:0;margin:0}
.properties-table :deep(.ui-data-table__tools){width:100%;min-width:0;justify-content:flex-end}
.properties-table :deep(.ui-data-table__search){width:min(360px,100%);margin-right:auto}
.properties-table :deep(.ui-data-table__viewport table){min-width:1280px}
.properties-table :deep(.property-title-cell){min-width:19rem}
.properties-table :deep(.property-location-cell){min-width:14rem;white-space:normal;overflow-wrap:break-word}
.properties-table :deep(.property-actions-cell){min-width:11rem}
@media(max-width:1100px){
  .properties-table :deep(.ui-data-table__filters){grid-template-columns:repeat(3,minmax(150px,1fr))}
}
@media(max-width:760px){
  .properties-table :deep(.ui-data-table__filters){grid-template-columns:1fr}
  .properties-table :deep(.ui-data-table__tools){align-items:stretch;display:grid;grid-template-columns:1fr 1fr}
  .properties-table :deep(.ui-data-table__search){grid-column:1/-1;width:100%;margin:0}
}
</style>
