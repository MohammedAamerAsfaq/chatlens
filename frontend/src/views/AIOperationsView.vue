<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { aiOperationsApi } from '@/api'

const sections = [
  ['parsing', 'Parsing lifecycle'], ['calls', 'Provider calls'], ['routing', 'Router decisions'],
  ['reservations', 'Capacity reservations'], ['embeddings', 'Embeddings'],
  ['tasks', 'AI tasks'], ['limits', 'Rate-limit ledger'],
]
const overview = ref({ company: '', counts: {}, statuses: {}, tokens: { input: 0, output: 0 } })
const activeSection = ref('parsing'), rows = ref([]), count = ref(0), page = ref(1), pageSize = ref(25), totalPages = ref(1)
const search = ref(''), status = ref(''), loading = ref(false), error = ref(''), expanded = ref(null)
let filterTimer = null

const activeLabel = computed(() => sections.find(([key]) => key === activeSection.value)?.[1] || '')
const statusOptions = computed(() => Object.keys(overview.value.statuses?.[activeSection.value] || {}))
const sectionCount = key => overview.value.counts?.[key] || 0

async function loadOverview() {
  const { data } = await aiOperationsApi.overview()
  overview.value = data
}
async function loadRows() {
  loading.value = true; error.value = ''
  try {
    const { data } = await aiOperationsApi.records({
      section: activeSection.value, page: page.value, page_size: pageSize.value,
      search: search.value || undefined, status: status.value || undefined,
    })
    rows.value = data.results; count.value = data.count; totalPages.value = data.total_pages
    expanded.value = null
  } catch (requestError) {
    error.value = requestError.response?.data?.detail || 'Unable to load AI operations data.'
  } finally { loading.value = false }
}
async function refresh() {
  try { await Promise.all([loadOverview(), loadRows()]) } catch (requestError) {
    error.value = requestError.response?.data?.detail || 'Unable to load AI operations data.'
  }
}
function selectSection(key) { activeSection.value = key; page.value = 1; status.value = ''; loadRows() }
function changePage(next) { if (next >= 1 && next <= totalPages.value) { page.value = next; loadRows() } }
function formatDate(value) { return value ? new Date(value).toLocaleString() : '-' }
function formatMetric(value) { return value === null || value === undefined || value === '' ? '-' : value }
function label(value) { return String(value).replaceAll('_', ' ') }
function statusClass(value) { return `state state-${String(value).toLowerCase()}` }
watch([search, status], () => {
  clearTimeout(filterTimer)
  filterTimer = setTimeout(() => { page.value = 1; loadRows() }, 250)
})
onMounted(refresh)
onUnmounted(() => clearTimeout(filterTimer))
</script>

<template>
  <main class="ai-operations">
    <header class="page-head">
      <div><p class="eyebrow">Company AI observability</p><h1>AI Operations</h1><p>Tenant-scoped parsing, provider, routing, embedding, and durable-task diagnostics for {{ overview.company || 'this company' }}.</p></div>
      <button :disabled="loading" @click="refresh"><i class="fa fa-refresh" /> {{ loading ? 'Refreshing' : 'Refresh' }}</button>
    </header>
    <p v-if="error" class="error-banner">{{ error }}</p>

    <section class="metrics">
      <article><span>Provider calls</span><strong>{{ sectionCount('calls').toLocaleString() }}</strong><small>company-owned requests</small></article>
      <article><span>Input tokens</span><strong>{{ overview.tokens.input.toLocaleString() }}</strong><small>recorded provider usage</small></article>
      <article><span>Output tokens</span><strong>{{ overview.tokens.output.toLocaleString() }}</strong><small>recorded provider usage</small></article>
      <article><span>AI tasks</span><strong>{{ sectionCount('tasks').toLocaleString() }}</strong><small>durable queue executions</small></article>
    </section>

    <section class="ledger">
      <nav class="section-tabs" aria-label="AI operation ledgers">
        <button v-for="item in sections" :key="item[0]" :class="{ active: activeSection === item[0] }" @click="selectSection(item[0])">
          {{ item[1] }} <span>{{ sectionCount(item[0]) }}</span>
        </button>
      </nav>
      <div class="toolbar">
        <div><p class="eyebrow">Execution ledger</p><h2>{{ activeLabel }}</h2></div>
        <div class="filters">
          <input v-model.trim="search" placeholder="Search records...">
          <select v-model="status"><option value="">All statuses</option><option v-for="item in statusOptions" :key="item" :value="item">{{ label(item) }}</option></select>
          <select v-model.number="pageSize" @change="page = 1; loadRows()"><option :value="25">25 rows</option><option :value="50">50 rows</option><option :value="100">100 rows</option></select>
        </div>
      </div>

      <div class="table-wrap">
        <table>
          <thead><tr><th>Record</th><th>Category</th><th>Status</th><th>Occurred</th><th>Metrics</th><th>Summary</th></tr></thead>
          <tbody>
            <tr v-if="!rows.length"><td colspan="6" class="empty">{{ loading ? 'Loading records...' : 'No records match these filters.' }}</td></tr>
            <template v-for="row in rows" :key="row.id">
              <tr :class="{ selected: expanded === row.id }" @click="expanded = expanded === row.id ? null : row.id">
                <td><strong>{{ row.title }}</strong><small>#{{ row.id }}</small></td>
                <td>{{ row.category }}</td><td><span :class="statusClass(row.status)">{{ label(row.status) }}</span></td>
                <td>{{ formatDate(row.occurred_at) }}</td>
                <td><span v-for="(value, key) in row.metrics" :key="key" class="metric-line"><b>{{ label(key) }}:</b> {{ formatMetric(value) }}</span></td>
                <td class="summary">{{ row.summary || '-' }}</td>
              </tr>
              <tr v-if="expanded === row.id" class="detail"><td colspan="6"><h3>Sanitized record detail</h3><pre>{{ JSON.stringify(row.detail, null, 2) }}</pre></td></tr>
            </template>
          </tbody>
        </table>
      </div>
      <footer>
        <span>Showing {{ rows.length ? ((page - 1) * pageSize) + 1 : 0 }}-{{ Math.min(page * pageSize, count) }} of {{ count }}</span>
        <div><button :disabled="page === 1" @click="changePage(page - 1)">Previous</button><span>Page {{ page }} of {{ totalPages }}</span><button :disabled="page === totalPages" @click="changePage(page + 1)">Next</button></div>
      </footer>
    </section>
  </main>
</template>

<style scoped>
.ai-operations{height:100%;overflow:auto;box-sizing:border-box;padding:28px;background:radial-gradient(circle at 92% 0,var(--ui-primary-soft),transparent 28rem),var(--ui-bg);color:var(--ui-text)}
.page-head,.toolbar,footer{display:flex;align-items:center;justify-content:space-between;gap:20px}.page-head h1{margin:0 0 5px;font-size:2rem}.page-head p{margin:0;color:var(--ui-text-muted)}
.eyebrow{margin:0 0 5px!important;color:var(--ui-primary)!important;text-transform:uppercase;letter-spacing:.13em;font-size:.68rem;font-weight:800}
button{border:1px solid var(--ui-primary);border-radius:var(--ui-radius-sm);padding:9px 13px;background:var(--ui-primary);color:var(--ui-on-primary);font-weight:700;cursor:pointer}button:disabled{opacity:.45;cursor:not-allowed}
.error-banner{padding:11px;border:1px solid var(--ui-danger);border-radius:var(--ui-radius-sm);background:var(--ui-danger-soft);color:var(--ui-danger)}
.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:24px 0 14px}.metrics article,.ledger{background:var(--ui-surface);border:1px solid var(--ui-border);box-shadow:var(--ui-shadow-sm)}.metrics article{padding:17px;border-top:4px solid var(--ui-primary);border-radius:var(--ui-radius-md)}.metrics strong{display:block;margin:5px 0;font:700 1.8rem Georgia,serif}.metrics small{color:var(--ui-text-muted)}
.ledger{border-radius:var(--ui-radius-md);overflow:hidden}.section-tabs{display:flex;overflow:auto;border-bottom:1px solid var(--ui-border);background:var(--ui-surface-muted)}.section-tabs button{flex:1;min-width:145px;border:0;border-radius:0;border-bottom:3px solid transparent;background:transparent;color:var(--ui-text-muted);white-space:nowrap}.section-tabs button.active{border-bottom-color:var(--ui-primary);color:var(--ui-primary);background:var(--ui-surface)}.section-tabs span{margin-left:5px;padding:2px 6px;border-radius:99px;background:var(--ui-primary-soft)}
.toolbar{padding:16px 18px}.toolbar h2{margin:0;font-size:1.1rem}.filters{display:flex;gap:8px;flex-wrap:wrap}.filters input,.filters select{min-width:160px;padding:9px;border:1px solid var(--ui-border-strong);border-radius:var(--ui-radius-sm);background:var(--ui-surface);color:var(--ui-text)}.filters input:focus,.filters select:focus{outline:0;border-color:var(--ui-primary);box-shadow:var(--ui-focus-ring)}
.table-wrap{overflow:auto}table{width:100%;min-width:1080px;border-collapse:collapse;font-size:.78rem}th{text-align:left;padding:9px 12px;background:var(--ui-surface-muted);color:var(--ui-text-muted);text-transform:uppercase;font-size:.65rem}td{padding:10px 12px;border-top:1px solid var(--ui-border);vertical-align:top}tbody tr:not(.detail){cursor:pointer}tbody tr:not(.detail):hover,tbody tr.selected{background:var(--ui-primary-soft)}td strong,td small,.metric-line{display:block}td small{color:var(--ui-text-muted)}.summary{max-width:330px;overflow-wrap:anywhere}.metric-line b{font-weight:700;color:var(--ui-text-muted)}
.state{display:inline-block;border-radius:99px;padding:3px 8px;background:var(--ui-info-soft);color:var(--ui-info);font-weight:800;text-transform:uppercase;font-size:.65rem}.state-complete,.state-succeeded,.state-embedded,.state-selected,.state-recorded{background:var(--ui-success-soft);color:var(--ui-success)}.state-error,.state-failed{background:var(--ui-danger-soft);color:var(--ui-danger)}.state-pending,.state-retrying,.state-deferred,.state-reserved{background:var(--ui-warning-soft);color:var(--ui-warning)}
.detail{background:var(--ui-surface-muted)}.detail h3{margin:0 0 8px}.detail pre{max-height:360px;overflow:auto;margin:0;padding:12px;border-radius:var(--ui-radius-sm);background:var(--ui-code-bg);color:var(--ui-code-text);white-space:pre-wrap;overflow-wrap:anywhere}.empty{text-align:center;padding:42px;color:var(--ui-text-muted)}footer{padding:12px 16px;border-top:1px solid var(--ui-border);font-size:.78rem}footer div{display:flex;align-items:center;gap:10px}footer button{padding:6px 9px}
@media(max-width:900px){.ai-operations{padding:18px}.metrics{grid-template-columns:1fr 1fr}.page-head,.toolbar{align-items:flex-start;flex-direction:column}.filters{width:100%}.filters input,.filters select{flex:1}}@media(max-width:560px){.metrics{grid-template-columns:1fr}footer{align-items:flex-start;flex-direction:column}}
</style>
