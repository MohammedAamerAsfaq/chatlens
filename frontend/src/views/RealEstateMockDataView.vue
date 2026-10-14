<!-- eslint-disable vue/block-lang -->
<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import { realEstateApi, taskQueueApi } from '@/api'
import UiBadge from '@/components/ui/UiBadge.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiCard from '@/components/ui/UiCard.vue'
import UiConfirmModal from '@/components/ui/UiConfirmModal.vue'
import UiDataTable from '@/components/ui/UiDataTable.vue'
import UiNotice from '@/components/ui/UiNotice.vue'
import UiPage from '@/components/ui/UiPage.vue'
import UiPageHeader from '@/components/ui/UiPageHeader.vue'
import { apiError } from '@/features/realEstate/apiErrors'

const columns = [
  { key: 'company_id', label: 'Company ID', width: '7rem' },
  { key: 'import_run_id', label: 'Import Run ID', width: '12rem' },
  { key: 'source_file_name', label: 'Source File', sortable: true, width: '16rem' },
  { key: 'source_file_checksum', label: 'File Checksum', width: '11rem' },
  { key: 'source_sheet_name', label: 'Sheet', sortable: true, width: '11rem' },
  { key: 'source_sheet_index', label: 'Sheet Index', sortable: true, width: '7rem' },
  { key: 'source_row_number', label: 'Row Number', sortable: true, width: '7rem' },
  { key: 'row_kind', label: 'Row Kind', sortable: true, width: '8rem' },
  { key: 'raw_values', label: 'Raw Values', width: '20rem', exportValue: row => JSON.stringify(row.raw_values) },
  { key: 'display_values', label: 'Display Values', width: '20rem', exportValue: row => JSON.stringify(row.display_values) },
  { key: 'row_checksum', label: 'Row Checksum', width: '11rem' },
  { key: 'processing_status', label: 'Status', sortable: true, width: '8rem' },
  { key: 'processing_notes', label: 'Processing Notes', width: '14rem' },
  { key: 'imported_at', label: 'Imported At', sortable: true, width: '11rem' },
]

const sourceFiles = ref([])
const selectedFiles = ref(new Set())
const rows = ref([])
const summary = ref({ records: 0, files: 0, sheets: 0, runs: 0 })
const search = ref('')
const page = ref(1)
const pageSize = ref(25)
const sortKey = ref('imported_at')
const sortDirection = ref('desc')
const loading = ref(false)
const importing = ref(false)
const deleting = ref(false)
const confirmDelete = ref(false)
const error = ref('')
const notice = ref('')
let pollTimer

const allSelected = computed(() => sourceFiles.value.length > 0 && selectedFiles.value.size === sourceFiles.value.length)

function shortHash(value) {
  return value ? `${String(value).slice(0, 12)}...` : '-'
}

function toggleFile(name) {
  const next = new Set(selectedFiles.value)
  if (next.has(name)) next.delete(name)
  else next.add(name)
  selectedFiles.value = next
}

function toggleAll() {
  selectedFiles.value = allSelected.value ? new Set() : new Set(sourceFiles.value.map(item => item.name))
}

async function loadFiles() {
  const { data } = await realEstateApi.mockSourceFiles()
  sourceFiles.value = data.files || []
}

async function loadSummary() {
  const { data } = await realEstateApi.mockSourceSummary()
  summary.value = data
}

async function loadRows() {
  loading.value = true
  error.value = ''
  try {
    const ordering = `${sortDirection.value === 'desc' ? '-' : ''}${sortKey.value}`
    const { data } = await realEstateApi.mockSourceRecords({
      page: page.value, page_size: pageSize.value, search: search.value, ordering,
    })
    rows.value = data.results || []
    summary.value.records = data.count || 0
  } catch (exc) {
    error.value = apiError(exc, 'Unable to load mock-source records.')
  } finally {
    loading.value = false
  }
}

async function refresh() {
  try {
    await Promise.all([loadFiles(), loadSummary(), loadRows()])
  } catch (exc) {
    error.value = apiError(exc, 'Unable to load the mock-source workspace.')
  }
}

async function startImport(importAll) {
  if (!importAll && !selectedFiles.value.size) {
    error.value = 'Select at least one workbook.'
    return
  }
  importing.value = true
  error.value = ''
  notice.value = ''
  try {
    const { data } = await realEstateApi.importMockSources(importAll
      ? { import_all: true }
      : { import_all: false, file_names: [...selectedFiles.value] })
    notice.value = `Import task #${data.task_id} queued for ${data.files_queued} workbook(s).`
    pollImport(data.task_id)
  } catch (exc) {
    importing.value = false
    error.value = apiError(exc, 'Unable to queue the workbook import.')
  }
}

async function pollImport(taskId) {
  clearTimeout(pollTimer)
  try {
    const { data } = await taskQueueApi.task(taskId)
    if (data.status === 'succeeded') {
      importing.value = false
      const result = data.result || {}
      notice.value = `Import complete: ${Number(result.records_created || 0).toLocaleString()} created, ${Number(result.duplicates_skipped || 0).toLocaleString()} duplicates skipped.`
      await refresh()
      return
    }
    if (['failed', 'cancelled'].includes(data.status)) {
      importing.value = false
      error.value = data.last_error || `Import task ${data.status}.`
      return
    }
    notice.value = `Import task #${taskId} is ${data.status}. The grid will refresh when it finishes.`
    pollTimer = setTimeout(() => pollImport(taskId), 2000)
  } catch (exc) {
    importing.value = false
    error.value = apiError(exc, 'Unable to read import task status.')
  }
}

async function deleteAll() {
  deleting.value = true
  error.value = ''
  try {
    const { data } = await realEstateApi.deleteMockSources()
    confirmDelete.value = false
    notice.value = `${Number(data.deleted || 0).toLocaleString()} mock-source record(s) deleted.`
    page.value = 1
    await refresh()
  } catch (exc) {
    error.value = apiError(exc, 'Unable to delete mock-source records.')
  } finally {
    deleting.value = false
  }
}

function updatePage(value) { page.value = value; loadRows() }
function updatePageSize(value) { pageSize.value = value; page.value = 1; loadRows() }
function updateSortKey(value) { sortKey.value = value; page.value = 1; loadRows() }
function updateSortDirection(value) { sortDirection.value = value; page.value = 1; loadRows() }
function updateSearch(value) { search.value = value; page.value = 1; loadRows() }

onMounted(refresh)
onBeforeUnmount(() => clearTimeout(pollTimer))
</script>

<template>
  <UiPage width="wide">
    <UiPageHeader eyebrow="Real Estate Testing" title="Mock Source Data" description="Import Excel source rows into a company-owned staging table for controlled pipeline testing.">
      <template #actions><UiButton variant="danger" :disabled="importing || !summary.records" @click="confirmDelete = true">Delete all records</UiButton></template>
    </UiPageHeader>

    <UiNotice tone="warning">This is test staging data only. Imports do not create properties, listings, contacts, or inquiries.</UiNotice>
    <UiNotice v-if="notice" tone="success">{{ notice }}</UiNotice>
    <UiNotice v-if="error" tone="danger">{{ error }}</UiNotice>

    <UiCard title="Source workbooks" subtitle="Select specific files or import every .xlsx workbook from static/Real Estate Data.">
      <div class="source-toolbar">
        <label class="select-all"><input type="checkbox" :checked="allSelected" @change="toggleAll"> Select all files</label>
        <div class="source-actions">
          <UiButton :disabled="importing || !selectedFiles.size" @click="startImport(false)">Import selected</UiButton>
          <UiButton variant="primary" :disabled="importing || !sourceFiles.length" @click="startImport(true)">{{ importing ? 'Import running...' : 'Import all files' }}</UiButton>
        </div>
      </div>
      <div v-if="sourceFiles.length" class="file-grid">
        <label v-for="file in sourceFiles" :key="file.name" :class="{ selected: selectedFiles.has(file.name) }">
          <input type="checkbox" :checked="selectedFiles.has(file.name)" @change="toggleFile(file.name)">
          <span>{{ file.name }}</span><small>{{ Number(file.size).toLocaleString() }} bytes</small>
        </label>
      </div>
      <p v-else class="empty-files">No .xlsx files were found in static/Real Estate Data.</p>
    </UiCard>

    <section class="record-summary" aria-label="Import summary">
      <div><span>Records</span><strong>{{ Number(summary.records).toLocaleString() }}</strong></div>
      <div><span>Files imported</span><strong>{{ summary.files }}</strong></div>
      <div><span>Sheets imported</span><strong>{{ summary.sheets }}</strong></div>
      <div><span>Import runs</span><strong>{{ summary.runs }}</strong></div>
    </section>

    <UiCard title="Persisted staging records" subtitle="Rows are paginated from the server and scoped to the active company." flush>
      <UiDataTable
        class="mock-source-table" :columns="columns" :rows="rows" row-key="id" :loading="loading"
        :total="summary.records" :page="page" :page-size="pageSize" :page-sizes="[10, 25, 50, 100]"
        :sort-key="sortKey" :sort-direction="sortDirection" :search="search"
        persist-key="real-estate-mock-source" expandable export-filename="real-estate-mock-source-records.csv"
        search-placeholder="Search file, sheet, or notes..." empty-title="No mock-source records have been imported."
        @update:page="updatePage" @update:page-size="updatePageSize" @update:sort-key="updateSortKey"
        @update:sort-direction="updateSortDirection" @update:search="updateSearch" @refresh="refresh"
      >
        <template #cell-import_run_id="{ value }"><code :title="value">{{ shortHash(value) }}</code></template>
        <template #cell-source_file_checksum="{ value }"><code :title="value">{{ shortHash(value) }}</code></template>
        <template #cell-row_checksum="{ value }"><code :title="value">{{ shortHash(value) }}</code></template>
        <template #cell-row_kind="{ value }"><UiBadge tone="neutral">{{ value }}</UiBadge></template>
        <template #cell-processing_status="{ value }"><UiBadge tone="warning">{{ value }}</UiBadge></template>
        <template #cell-raw_values="{ value }"><span class="cell-values" :title="JSON.stringify(value)">{{ value.join(' | ') }}</span></template>
        <template #cell-display_values="{ value }"><span class="cell-values" :title="value.join(' | ')">{{ value.join(' | ') }}</span></template>
        <template #cell-imported_at="{ value }">{{ value ? new Date(value).toLocaleString() : '-' }}</template>
        <template #expanded="{ row }"><div class="row-detail"><section><h3>Raw values</h3><pre>{{ JSON.stringify(row.raw_values, null, 2) }}</pre></section><section><h3>Display values</h3><pre>{{ JSON.stringify(row.display_values, null, 2) }}</pre></section></div></template>
      </UiDataTable>
    </UiCard>

    <UiConfirmModal :open="confirmDelete" title="Delete all mock-source records?" danger :busy="deleting" message="This permanently deletes every Real Estate mock-source staging row for the active company only." confirm-label="Delete all records" @confirm="deleteAll" @cancel="confirmDelete = false" />
  </UiPage>
</template>

<style scoped>
.source-toolbar{display:flex;align-items:center;justify-content:space-between;gap:16px}.select-all{font-weight:700}.source-actions{display:flex;gap:8px}.file-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;max-height:280px;overflow:auto;margin-top:16px}.file-grid label{display:grid;grid-template-columns:auto 1fr;gap:3px 8px;padding:10px;border:1px solid var(--ui-border);background:var(--ui-surface)}.file-grid label.selected{border-color:var(--ui-primary);background:var(--ui-primary-soft)}.file-grid small{grid-column:2;color:var(--ui-text-muted)}.empty-files{color:var(--ui-text-muted)}.record-summary{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}.record-summary div{display:grid;gap:3px;padding:16px;border:1px solid var(--ui-border);background:var(--ui-surface)}.record-summary span{color:var(--ui-text-muted)}.record-summary strong{font-size:1.5rem}.mock-source-table :deep(.ui-data-table__viewport table){min-width:2300px}.cell-values{display:block;max-width:20rem;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.row-detail{display:grid;grid-template-columns:1fr 1fr;gap:16px}.row-detail h3{margin:0 0 8px}.row-detail pre{max-height:280px;overflow:auto;margin:0;padding:14px;background:var(--ui-surface-muted);white-space:pre-wrap;word-break:break-word}code{font-size:.8rem}@media(max-width:900px){.file-grid{grid-template-columns:1fr 1fr}.record-summary{grid-template-columns:1fr 1fr}.row-detail{grid-template-columns:1fr}}@media(max-width:560px){.source-toolbar,.source-actions{display:grid}.file-grid,.record-summary{grid-template-columns:1fr}}
</style>
