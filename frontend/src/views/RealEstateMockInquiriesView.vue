<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import { realEstateApi } from '@/api'
import UiBadge from '@/components/ui/UiBadge.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiCard from '@/components/ui/UiCard.vue'
import UiConfirmModal from '@/components/ui/UiConfirmModal.vue'
import UiDataTable from '@/components/ui/UiDataTable.vue'
import UiMetric from '@/components/ui/UiMetric.vue'
import UiNotice from '@/components/ui/UiNotice.vue'
import UiPage from '@/components/ui/UiPage.vue'
import UiPageHeader from '@/components/ui/UiPageHeader.vue'
import UiSelect from '@/components/ui/UiSelect.vue'
import { apiError } from '@/features/realEstate/apiErrors'

const columns = [
  { key: 'id', label: 'ID', width: '5rem' },
  { key: 'activity_type', label: 'Expected', width: '8rem' },
  { key: 'classified_activity', label: 'AI Result', width: '8rem' },
  { key: 'contact_name', label: 'Contact', width: '13rem' },
  { key: 'source_row_number', label: 'Source Row', width: '7rem' },
  { key: 'generated_message', label: 'Inbound Message', width: '30rem' },
  { key: 'live_task_status', label: 'Ingestion', width: '8rem' },
  { key: 'embedding_status', label: 'Embedding', width: '8rem' },
  { key: 'parse_status', label: 'Parsing', width: '9rem' },
  { key: 'created_at', label: 'Created', width: '11rem' },
]
const counts = [1, 10, 100].map(value => ({ value, label: `${value} record${value === 1 ? '' : 's'}` }))
const datasets = ref([]), runs = ref([]), rows = ref([])
const summary = ref({ runs: 0, queued: 0, ingested: 0, failed: 0, ai_parsing_enabled: true })
const selectedFile = ref(''), recordCount = ref(10), page = ref(1), pageSize = ref(25)
const loading = ref(false), starting = ref(false), clearing = ref(false), confirmClear = ref(false)
const error = ref(''), notice = ref('')
let timer

const suitable = computed(() => datasets.value.filter(row => row.suitable && row.eligible_pending > 0))
const latestRun = computed(() => runs.value[0] || null)
const datasetOptions = computed(() => suitable.value.map(row => ({
  value: row.source_file_name,
  label: `${row.source_file_name} - ${label(row.activity_type)} - ${row.eligible_pending.toLocaleString()} pending`,
})))
const selected = computed(() => datasets.value.find(row => row.source_file_name === selectedFile.value))
const active = computed(() => runs.value.some(row => ['pending', 'running'].includes(row.status)))
function label(value) { return String(value || '-').replaceAll('_', ' ').replace(/\b\w/g, char => char.toUpperCase()) }
function tone(value) { return value === 'failed' ? 'danger' : ['complete', 'ingested', 'succeeded'].includes(value) ? 'success' : 'warning' }

async function refresh() {
  loading.value = true
  try {
    const [datasetResult, runResult, summaryResult, itemResult] = await Promise.all([
      realEstateApi.mockInquiryDatasets(), realEstateApi.mockInquiryRuns(),
      realEstateApi.mockInquirySummary(), realEstateApi.mockInquiries({ page: page.value, page_size: pageSize.value }),
    ])
    datasets.value = datasetResult.data.datasets || []
    runs.value = runResult.data.results || []
    summary.value = summaryResult.data
    rows.value = itemResult.data.results || []
    summary.value.total = itemResult.data.count || 0
    if (!selectedFile.value && suitable.value.length) selectedFile.value = suitable.value[0].source_file_name
    schedule()
  } catch (exc) { error.value = apiError(exc, 'Unable to load mock inquiry testing.') }
  finally { loading.value = false }
}
function schedule() { clearTimeout(timer); if (active.value) timer = setTimeout(refresh, 2500) }
async function start() {
  starting.value = true; error.value = ''; notice.value = ''
  try {
    const { data } = await realEstateApi.startMockInquiryRun({ source_file_name: selectedFile.value, record_count: recordCount.value })
    notice.value = `Mock run ${data.id} queued on task #${data.task_id}.`
    await refresh()
  } catch (exc) { error.value = apiError(exc, 'Unable to start mock inquiries.') }
  finally { starting.value = false }
}
async function clearAll() {
  clearing.value = true; error.value = ''
  try {
    const { data } = await realEstateApi.clearMockInquiries()
    notice.value = `${data.messages_deleted} related record(s) deleted and ${data.source_rows_reset} source row(s) reset.`
    confirmClear.value = false; page.value = 1; await refresh()
  } catch (exc) { error.value = apiError(exc, 'Unable to clear mock inquiries.') }
  finally { clearing.value = false }
}
function changePage(value) { page.value = value; refresh() }
function changePageSize(value) { pageSize.value = value; page.value = 1; refresh() }
onMounted(refresh)
onBeforeUnmount(() => clearTimeout(timer))
</script>

<template>
  <UiPage width="wide">
    <UiPageHeader eyebrow="Real Estate Testing" title="Mock Inquiries" description="Generate controlled inbound WhatsApp messages, then observe the normal ingestion, embedding, and AI parsing queues.">
      <template #actions><UiButton variant="danger" :disabled="active || !summary.total" @click="confirmClear = true">Clear mock inquiries</UiButton></template>
    </UiPageHeader>
    <UiNotice v-if="!summary.ai_parsing_enabled" tone="warning">Company AI parsing is off. Messages will ingest and embed, but Real Estate classification will be skipped.</UiNotice>
    <UiNotice v-if="notice" tone="success">{{ notice }}</UiNotice><UiNotice v-if="error" tone="danger">{{ error }}</UiNotice>
    <UiCard title="Start a mock run" subtitle="The activity is inferred from the curated dataset. Only valid, unprocessed data rows are selected.">
      <div class="run-form"><UiSelect v-model="selectedFile" :options="datasetOptions" placeholder="Select a suitable dataset" searchable/><UiSelect v-model="recordCount" :options="counts"/><UiButton variant="primary" :disabled="starting || active || !selected" @click="start">{{ starting ? 'Queueing...' : 'Start mock inquiries' }}</UiButton></div>
      <div v-if="selected" class="dataset-note"><UiBadge tone="info">{{ label(selected.activity_type) }}</UiBadge><span>{{ selected.description }}</span><strong>{{ selected.eligible_pending.toLocaleString() }} pending rows</strong><small>{{ selected.processed.toLocaleString() }} processed</small></div>
      <div v-if="latestRun" class="run-status"><UiBadge :tone="tone(latestRun.status)">{{ label(latestRun.status) }}</UiBadge><strong>{{ latestRun.generated_count }} / {{ latestRun.requested_count }} generated</strong><span>Task #{{ latestRun.task_id }} {{ label(latestRun.task_status) }}</span><small v-if="latestRun.error">{{ latestRun.error }}</small></div>
    </UiCard>
    <section class="metrics"><UiMetric label="Runs" :value="summary.runs"/><UiMetric label="Queued" :value="summary.queued" tone="warning"/><UiMetric label="Ingested" :value="summary.ingested" tone="success"/><UiMetric label="Failed" :value="summary.failed" tone="danger"/></section>
    <UiCard title="Production-pipeline feedback" subtitle="Expected activity comes from the dataset profile; AI Result is populated only after the normal Real Estate extraction completes." flush>
      <UiDataTable :columns="columns" :rows="rows" row-key="id" :loading="loading" :total="summary.total || 0" :page="page" :page-size="pageSize" :page-sizes="[10,25,50,100]" persist-key="real-estate-mock-inquiries" expandable empty-title="No mock inquiries have been generated." @update:page="changePage" @update:page-size="changePageSize" @refresh="refresh">
        <template #cell-activity_type="{ value }"><UiBadge tone="info">{{ label(value) }}</UiBadge></template><template #cell-classified_activity="{ value }"><UiBadge :tone="value ? 'success' : 'neutral'">{{ label(value) }}</UiBadge></template>
        <template #cell-live_task_status="{ value }"><UiBadge :tone="tone(value)">{{ label(value) }}</UiBadge></template><template #cell-embedding_status="{ value }"><UiBadge :tone="tone(value)">{{ label(value) }}</UiBadge></template><template #cell-parse_status="{ value }"><UiBadge :tone="tone(value)">{{ label(value) }}</UiBadge></template>
        <template #cell-generated_message="{ value }"><span class="message" :title="value">{{ value }}</span></template><template #cell-created_at="{ value }">{{ new Date(value).toLocaleString() }}</template>
        <template #expanded="{ row }"><div class="detail"><p><strong>Contact:</strong> {{ row.contact_name }} - {{ row.contact_number }}</p><p><strong>Source:</strong> {{ row.source_sheet_name }} row {{ row.source_row_number }}</p><p>{{ row.generated_message }}</p><p v-if="row.error" class="error">{{ row.error }}</p></div></template>
      </UiDataTable>
    </UiCard>
    <UiConfirmModal :open="confirmClear" title="Clear all mock inquiries?" danger :busy="clearing" message="This removes only the dedicated mock account messages and their related tasks and AI records, then resets the audited source rows for reuse." confirm-label="Clear mock data" @confirm="clearAll" @cancel="confirmClear = false"/>
  </UiPage>
</template>

<style scoped>
.run-form{display:grid;grid-template-columns:minmax(320px,1fr) 180px auto;gap:12px;align-items:start}.dataset-note,.run-status{display:flex;align-items:center;gap:12px;margin-top:14px;color:var(--ui-text-muted)}.dataset-note strong{margin-left:auto;color:var(--ui-text)}.run-status{padding-top:12px;border-top:1px solid var(--ui-border)}.run-status small{color:var(--ui-warning)}.metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}.message{display:block;max-width:30rem;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.detail{padding:8px 12px}.detail p{margin:5px 0}.error{color:var(--ui-danger)}@media(max-width:800px){.run-form,.metrics{grid-template-columns:1fr}.dataset-note,.run-status{align-items:flex-start;flex-wrap:wrap}.dataset-note strong{margin-left:0}}
</style>
