<script setup>
import { onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { realEstateApi } from '@/api'
import UiBadge from '@/components/ui/UiBadge.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiConfirmModal from '@/components/ui/UiConfirmModal.vue'
import UiDataTable from '@/components/ui/UiDataTable.vue'
import UiNotice from '@/components/ui/UiNotice.vue'
import UiPage from '@/components/ui/UiPage.vue'
import UiPageHeader from '@/components/ui/UiPageHeader.vue'
import PropertyAttributeEditor from '@/features/realEstate/components/PropertyAttributeEditor.vue'
import { apiError } from '@/features/realEstate/apiErrors'

const router = useRouter()
const rows = ref([]), total = ref(0), page = ref(1), pageSize = ref(25)
const search = ref(''), sortKey = ref('sort_order'), sortDirection = ref('asc')
const loading = ref(false), busy = ref(false), error = ref(''), notice = ref('')
const selected = ref(null), editorRevision = ref(0), pendingDeactivate = ref(null)
const columns = [
  { key: 'label', label: 'Attribute', sortable: true, width: '14rem' },
  { key: 'code', label: 'Code', sortable: true, width: '11rem' },
  { key: 'data_type', label: 'Data type', sortable: true, width: '8rem' },
  { key: 'matching_strategy', label: 'Matching', sortable: true, width: '10rem' },
  { key: 'options', label: 'Options', width: '6rem', exportValue: row => row.options?.length || 0 },
  { key: 'aliases', label: 'Aliases', width: '16rem', exportValue: row => (row.aliases || []).join(', ') },
  { key: 'source', label: 'Source', width: '7rem', exportValue: row => row.is_system ? 'System' : 'Custom' },
  { key: 'is_active', label: 'Status', sortable: true, width: '7rem' },
  { key: 'actions', label: '', exportable: false, width: '6rem' },
]

async function load() {
  loading.value = true; error.value = ''
  try {
    const ordering = `${sortDirection.value === 'desc' ? '-' : ''}${sortKey.value}`
    const { data } = await realEstateApi.propertyAttributes({ include_inactive: true, page: page.value, page_size: pageSize.value, search: search.value, ordering })
    rows.value = data.results; total.value = data.count
    if (selected.value) selected.value = rows.value.find(row => row.id === selected.value.id) || selected.value
  } catch (exc) { error.value = apiError(exc, 'Unable to load property attributes.') }
  finally { loading.value = false }
}
function addNew() { selected.value = null; editorRevision.value += 1; notice.value = ''; window.scrollTo({ top: 0, behavior: 'smooth' }) }
function edit(row) { selected.value = row; editorRevision.value += 1; notice.value = ''; window.scrollTo({ top: 0, behavior: 'smooth' }) }
async function save(values) {
  busy.value = true; error.value = ''; notice.value = ''
  try {
    const payload = { ...values }; delete payload.id; delete payload.created_at; delete payload.updated_at; delete payload.is_system
    const { data } = values.id ? await realEstateApi.updatePropertyAttribute(values.id, payload) : await realEstateApi.createPropertyAttribute(payload)
    selected.value = data; notice.value = `Attribute "${data.label}" was saved.`; await load()
  } catch (exc) { error.value = apiError(exc, 'Unable to save the property attribute.') }
  finally { busy.value = false }
}
async function deactivate() {
  busy.value = true; error.value = ''
  try { await realEstateApi.deactivatePropertyAttribute(pendingDeactivate.value.id); notice.value = 'Attribute deactivated.'; pendingDeactivate.value = null; selected.value = null; editorRevision.value += 1; await load() }
  catch (exc) { error.value = apiError(exc, 'Unable to deactivate the property attribute.') }
  finally { busy.value = false }
}
function resetPageAndLoad() { if (page.value !== 1) page.value = 1; else load() }
watch(search, resetPageAndLoad)
watch([page, pageSize, sortKey, sortDirection], load)
onMounted(load)
</script>

<template>
  <UiPage width="wide">
    <UiPageHeader eyebrow="Real Estate Configuration" title="Property Attribute Master" description="Maintain canonical property fields, aliases, matching strategies, and permitted values.">
      <template #actions><UiButton @click="router.push({ name: 'real-estate-properties' })">Back to properties</UiButton><UiButton variant="primary" @click="addNew">+ Add New Attribute</UiButton></template>
    </UiPageHeader>
    <UiNotice v-if="error" tone="danger">{{ error }}</UiNotice><UiNotice v-if="notice" tone="success">{{ notice }}</UiNotice>
    <PropertyAttributeEditor :key="editorRevision" class="attribute-editor-card" :record="selected" :busy="busy" @save="save" @deactivate="pendingDeactivate = $event" />
    <UiDataTable :columns="columns" :rows="rows" :loading="loading" :total="total" :page="page" :page-size="pageSize" :sort-key="sortKey" :sort-direction="sortDirection" :search="search" persist-key="real-estate-property-attributes" export-filename="property-attributes.csv" search-placeholder="Search attributes, codes, aliases, or options..." empty-title="No property attributes match these filters." @update:page="page = $event" @update:page-size="pageSize = $event; page = 1" @update:sort-key="sortKey = $event" @update:sort-direction="sortDirection = $event" @update:search="search = $event" @refresh="load">
      <template #cell-label="{ row }"><strong>{{ row.label }}</strong><small v-if="row.unit_hint" class="subline">Unit: {{ row.unit_hint }}</small></template>
      <template #cell-data_type="{ value }">{{ String(value).replaceAll('_', ' ') }}</template>
      <template #cell-matching_strategy="{ value }">{{ String(value).replaceAll('_', ' ') }}</template>
      <template #cell-options="{ row }">{{ row.options?.length || 0 }}</template>
      <template #cell-aliases="{ row }">{{ (row.aliases || []).join(', ') || '-' }}</template>
      <template #cell-source="{ row }"><UiBadge :tone="row.is_system ? 'info' : 'neutral'">{{ row.is_system ? 'System' : 'Custom' }}</UiBadge></template>
      <template #cell-is_active="{ value }"><UiBadge :tone="value ? 'success' : 'neutral'">{{ value ? 'Active' : 'Inactive' }}</UiBadge></template>
      <template #cell-actions="{ row }"><UiButton size="small" @click.stop="edit(row)">Edit</UiButton></template>
    </UiDataTable>
    <UiConfirmModal :open="Boolean(pendingDeactivate)" title="Deactivate attribute" :message="`Deactivate ${pendingDeactivate?.label || 'this attribute'}? Existing property data will be preserved.`" confirm-label="Deactivate" danger :busy="busy" @cancel="pendingDeactivate = null" @confirm="deactivate" />
  </UiPage>
</template>

<style scoped>
.attribute-editor-card{margin-bottom:18px}.subline{display:block;margin-top:3px;color:var(--ui-text-subtle);text-transform:none}
</style>
