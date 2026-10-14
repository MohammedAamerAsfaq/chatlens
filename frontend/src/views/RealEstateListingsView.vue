<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { FontAwesomeIcon } from '@fortawesome/vue-fontawesome'
import { faCircleXmark, faPenToSquare } from '@fortawesome/free-solid-svg-icons'
import { realEstateApi } from '@/api'
import UiBadge from '@/components/ui/UiBadge.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiConfirmModal from '@/components/ui/UiConfirmModal.vue'
import UiDataTable from '@/components/ui/UiDataTable.vue'
import UiNotice from '@/components/ui/UiNotice.vue'
import UiPage from '@/components/ui/UiPage.vue'
import UiPageHeader from '@/components/ui/UiPageHeader.vue'
import UiSelect from '@/components/ui/UiSelect.vue'
import ListingEditorModal from '@/features/realEstate/components/ListingEditorModal.vue'
import { apiError } from '@/features/realEstate/apiErrors'
import { cleanPayload } from '@/features/realEstate/forms'
import { listingStatuses, listingTypes, title } from '@/features/realEstate/options'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const rows = ref([]), properties = ref([]), total = ref(0), page = ref(1), pageSize = ref(25)
const loading = ref(false), error = ref(''), sortKey = ref('updated_at'), sortDirection = ref('desc')
const filters = reactive({ search: '', type: '', status: '' })
const editor = reactive({ open: false, record: null, busy: false })
const archive = reactive({ open: false, record: null, busy: false })
const canManage = computed(() => auth.hasPermission('real_estate.listings.manage'))
const typeFilters = [{ value: '', label: 'All listing types' }, ...listingTypes]
const statusFilters = [{ value: '', label: 'All statuses' }, ...listingStatuses]
const columns = [
  { key: 'property_title', label: 'Property', sortable: true, width: '20rem', cellClass: 'listing-property-cell' },
  { key: 'listing_type', label: 'Type', sortable: true, width: '8rem' },
  { key: 'asking_price', label: 'Asking price', sortable: true, width: '11rem' },
  { key: 'payment_frequency', label: 'Frequency', width: '8rem' },
  { key: 'status', label: 'Status', sortable: true, width: '7rem' },
  { key: 'is_verified', label: 'Verified', sortable: true, width: '7rem' },
  { key: 'available_from', label: 'Available', width: '8rem' },
  { key: 'actions', label: '', exportable: false, width: '5rem', cellClass: 'listing-actions-cell' },
]

async function load() {
  loading.value = true; error.value = ''
  try {
    const { data } = await realEstateApi.listings({ page: page.value, page_size: pageSize.value, ...filters, ordering: `${sortDirection.value === 'desc' ? '-' : ''}${sortKey.value}` })
    rows.value = data.results; total.value = data.count
  } catch (exc) { error.value = apiError(exc, 'Unable to load listings.') }
  finally { loading.value = false }
}
async function loadProperties() {
  try { properties.value = (await realEstateApi.properties({ page_size: 100 })).data.results } catch (exc) { error.value = apiError(exc, 'Unable to load properties.') }
}
function openEditor(record = null) { editor.record = record; editor.open = true }
async function save(values) {
  editor.busy = true; error.value = ''
  const payload = cleanPayload(values, ['asking_price', 'deposit', 'commission'])
  try {
    if (editor.record) await realEstateApi.updateListing(editor.record.id, payload)
    else await realEstateApi.createListing(payload)
    editor.open = false; await load()
  } catch (exc) { error.value = apiError(exc, 'Unable to save the listing.') }
  finally { editor.busy = false }
}
async function confirmArchive() {
  archive.busy = true
  try { await realEstateApi.archiveListing(archive.record.id); archive.open = false; await load() }
  catch (exc) { error.value = apiError(exc) }
  finally { archive.busy = false }
}
function money(row) { return `${row.currency} ${Number(row.asking_price).toLocaleString(undefined, { maximumFractionDigits: 2 })}` }
function resetAndLoad() { if (page.value !== 1) page.value = 1; else load() }
watch(() => [filters.search, filters.type, filters.status], resetAndLoad)
watch([page, pageSize, sortKey, sortDirection], load)
onMounted(async () => { await Promise.all([load(), loadProperties()]) })
</script>

<template><UiPage width="wide"><UiPageHeader eyebrow="Real Estate Inventory" title="Listings" description="Manage sale and lease offers while preserving the underlying property record."><template #actions><UiButton v-if="canManage" variant="primary" @click="openEditor()">+ Add listing</UiButton></template></UiPageHeader><UiNotice v-if="error" tone="danger">{{ error }}</UiNotice>
  <UiDataTable class="listings-table" :columns="columns" :rows="rows" :loading="loading" :total="total" :page="page" :page-size="pageSize" :sort-key="sortKey" :sort-direction="sortDirection" :search="filters.search" persist-key="real-estate-listings" search-placeholder="Search property title or reference..." empty-title="No listings match these filters." @update:page="page = $event" @update:page-size="pageSize = $event; page = 1" @update:sort-key="sortKey = $event" @update:sort-direction="sortDirection = $event" @update:search="filters.search = $event" @refresh="load">
    <template #filters><UiSelect v-model="filters.type" :options="typeFilters" /><UiSelect v-model="filters.status" :options="statusFilters" /></template>
    <template #cell-property_title="{ row }"><strong>{{ row.property_title }}</strong><small class="subline">Listing #{{ row.id }}</small></template><template #cell-listing_type="{ value }">{{ title(value) }}</template><template #cell-asking_price="{ row }"><strong>{{ money(row) }}</strong></template>
    <template #cell-payment_frequency="{ value }">{{ title(value) }}</template><template #cell-status="{ value }"><UiBadge :tone="value === 'active' ? 'success' : 'neutral'">{{ title(value) }}</UiBadge></template><template #cell-is_verified="{ value }"><UiBadge :tone="value ? 'success' : 'warning'">{{ value ? 'Verified' : 'Review' }}</UiBadge></template><template #cell-available_from="{ value }">{{ value || '-' }}</template>
    <template #cell-actions="{ row }"><div class="actions"><UiButton v-if="canManage" class="listing-action" size="small" title="Edit listing" aria-label="Edit listing" @click.stop="openEditor(row)"><FontAwesomeIcon :icon="faPenToSquare" /></UiButton><UiButton v-if="canManage" class="listing-action" size="small" variant="danger" title="Close listing" aria-label="Close listing" @click.stop="archive.record = row; archive.open = true"><FontAwesomeIcon :icon="faCircleXmark" /></UiButton></div></template>
  </UiDataTable><ListingEditorModal :open="editor.open" :record="editor.record" :properties="properties" :busy="editor.busy" @close="editor.open = false" @save="save" /><UiConfirmModal :open="archive.open" title="Close listing" :message="`Close the ${archive.record?.listing_type || ''} listing for ${archive.record?.property_title || 'this property'}?`" confirm-label="Close listing" danger :busy="archive.busy" @cancel="archive.open = false" @confirm="confirmArchive" />
</UiPage></template>

<style scoped>
.subline{display:block;color:var(--ui-text-subtle);margin-top:3px}
.actions{display:flex;align-items:center;gap:6px;white-space:nowrap}
.listing-action{width:30px;min-width:30px;padding:0}
.listings-table :deep(.ui-data-table__viewport table){min-width:1050px}
.listings-table :deep(.listing-property-cell){min-width:20rem}
.listings-table :deep(.listing-actions-cell){min-width:5rem}
</style>
