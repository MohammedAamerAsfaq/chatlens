<template>
  <div class="analytics-view">
    <!-- Header -->
    <div class="analytics-header">
      <div class="header-left">
        <h2>Trading Analytics</h2>
        <span class="last-update">Updated {{ lastUpdateLabel }}</span>
      </div>
      <div class="header-right">
        <select v-model="selectedRange" @change="refresh" class="account-select">
          <option v-for="p in RANGE_PRESETS" :key="p.label" :value="p.label">{{ p.label }}</option>
        </select>
        <select v-model="selectedAccount" @change="refresh" class="account-select">
          <option value="">All accounts</option>
          <option v-for="a in accounts" :key="a.id" :value="a.id">{{ a.display_name }}</option>
        </select>
        <button class="btn-ghost sm" @click="refresh">Refresh</button>
      </div>
    </div>

    <div class="page-body">

      <!-- AI Pipeline -->
      <div class="section-card">
        <div class="section-title-row">
          <span class="section-title">AI Pipeline ({{ selectedRange }})</span>
          <div class="section-actions">
            <button class="btn-ghost sm" @click="runBackfill" title="Classify recent unclassified messages">Backfill</button>
            <button
              v-if="classifyActivity?.today?.pending > 0"
              class="btn-retry sm"
              @click="runRetry"
              title="Re-run inquiry creation for classified messages with no Inquiry record"
            >Retry ({{ classifyActivity.today.pending }})</button>
          </div>
        </div>
        <div v-if="backfillStatus" class="backfill-msg">{{ backfillStatus }}</div>
        <pre v-if="retryError" class="retry-error">{{ retryError }}</pre>
        <div v-if="classifyActivity" class="classify-row">
          <span class="classify-chip total">{{ classifyActivity.today.total }} classified</span>
          <span class="classify-chip inquiry">{{ classifyActivity.today.as_inquiry }} inquiries</span>
          <span v-if="classifyActivity.today.pending > 0" class="classify-chip warn">{{ classifyActivity.today.pending }} pending</span>
          <span v-if="classifyActivity.today.type_missing > 0" class="classify-chip error">{{ classifyActivity.today.type_missing }} no type</span>
        </div>
        <div v-if="classifyActivity?.recent?.length" class="recent-classifications">
          <div
            v-for="mc in classifyActivity.recent" :key="mc.id"
            class="mc-row"
            :class="{ 'mc-inquiry': mc.is_inquiry }"
          >
            <span class="mc-badge" :class="mc.is_inquiry ? 'badge-yes' : 'badge-no'">
              {{ mc.is_inquiry ? (mc.inquiry_type || '?') : 'skip' }}
            </span>
            <span class="mc-summary">{{ mc.summary || mc.tags?.join(', ') }}</span>
          </div>
        </div>
        <div v-else-if="classifyActivity" class="empty-msg">No classifications {{ selectedRange === 'Today' ? 'today' : 'in this range' }}</div>
      </div>

      <!-- Two-column row: Source Breakdown + Hourly Activity -->
      <div class="two-col">

        <!-- Source Breakdown -->
        <div class="section-card">
          <div class="section-title">Source Breakdown ({{ selectedRange }})</div>
          <table class="mini-table">
            <thead><tr><th>Source</th><th>WTB</th><th>WTS</th><th>Total</th></tr></thead>
            <tbody>
              <tr v-for="src in ['direct','group','community']" :key="src">
                <td class="cap">{{ src }}</td>
                <td>{{ stats.by_source?.[src]?.wtb ?? 0 }}</td>
                <td>{{ stats.by_source?.[src]?.wts ?? 0 }}</td>
                <td class="total-col">{{ (stats.by_source?.[src]?.wtb ?? 0) + (stats.by_source?.[src]?.wts ?? 0) }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Hourly Activity -->
        <div class="section-card" v-if="stats.timeline?.length">
          <div class="section-title">{{ stats.timeline_granularity === 'daily' ? 'Daily Activity' : 'Hourly Activity' }}</div>
          <div class="chart-wrap">
            <div
              v-for="slot in stats.timeline" :key="slot.hour"
              class="chart-slot"
              :title="`${slot.hour} — WTB: ${slot.wtb}, WTS: ${slot.wts}`"
            >
              <div class="bar-group">
                <div class="bar wtb-bar" :style="{ height: barHeight(slot.wtb) + 'px' }"></div>
                <div class="bar wts-bar" :style="{ height: barHeight(slot.wts) + 'px' }"></div>
              </div>
              <div class="slot-label">{{ slot.hour.split(':')[0] }}</div>
            </div>
          </div>
          <div class="chart-legend">
            <span class="legend-dot wtb"></span> WTB &nbsp;
            <span class="legend-dot wts"></span> WTS
          </div>
        </div>
      </div>

      <!-- Product Activity -->
      <div class="section-card" v-if="productStats.length">
        <div class="section-title">Product Activity ({{ selectedRange }})</div>
        <table class="mini-table wide">
          <thead>
            <tr><th>Product</th><th>WTB</th><th>WTS</th><th>Deals</th><th>Total</th></tr>
          </thead>
          <tbody>
            <tr v-for="p in productStats" :key="p.product_id">
              <td>{{ p.name }}</td>
              <td>{{ p.wtb }}</td>
              <td>{{ p.wts }}</td>
              <td>{{ p.deals }}</td>
              <td class="total-col">{{ p.wtb + p.wts + p.deals }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-else-if="!loading" class="section-card empty-msg">No product activity {{ selectedRange === 'Today' ? 'today' : 'in this range' }}.</div>

    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { accountsApi, tradingApi } from '../api/index.js'

function fmtDate(d) {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

function startOfWeek(d) {
  // Monday-start week
  const date = new Date(d)
  const dow = date.getDay()
  date.setDate(date.getDate() + ((dow === 0 ? -6 : 1) - dow))
  return date
}

const RANGE_PRESETS = [
  { label: 'Today',        range: () => { const t = new Date(); return [t, t] } },
  { label: 'Yesterday',    range: () => { const t = new Date(); t.setDate(t.getDate() - 1); return [t, t] } },
  { label: 'This Week',    range: () => [startOfWeek(new Date()), new Date()] },
  { label: 'Last Week',    range: () => {
      const s = startOfWeek(new Date()); s.setDate(s.getDate() - 7)
      const e = new Date(s); e.setDate(e.getDate() + 6)
      return [s, e]
    } },
  { label: 'This Month',   range: () => { const n = new Date(); return [new Date(n.getFullYear(), n.getMonth(), 1), n] } },
  { label: 'Last Month',   range: () => {
      const n = new Date()
      return [new Date(n.getFullYear(), n.getMonth() - 1, 1), new Date(n.getFullYear(), n.getMonth(), 0)]
    } },
  { label: 'This Quarter', range: () => {
      const n = new Date(); const q = Math.floor(n.getMonth() / 3)
      return [new Date(n.getFullYear(), q * 3, 1), n]
    } },
  { label: 'Last Quarter', range: () => {
      const n = new Date()
      let q = Math.floor(n.getMonth() / 3) - 1
      let y = n.getFullYear()
      if (q < 0) { q = 3; y -= 1 }
      return [new Date(y, q * 3, 1), new Date(y, q * 3 + 3, 0)]
    } },
  { label: 'This Year',    range: () => { const n = new Date(); return [new Date(n.getFullYear(), 0, 1), n] } },
  { label: 'Last Year',    range: () => {
      const n = new Date()
      return [new Date(n.getFullYear() - 1, 0, 1), new Date(n.getFullYear() - 1, 11, 31)]
    } },
]

function resolveDateParams() {
  const preset = RANGE_PRESETS.find(p => p.label === selectedRange.value) || RANGE_PRESETS[0]
  const [from, to] = preset.range()
  return { date_from: fmtDate(from), date_to: fmtDate(to) }
}

const accounts         = ref([])
const selectedAccount  = ref('')
const selectedRange    = ref('Today')
const stats            = ref({})
const productStats     = ref([])
const classifyActivity = ref(null)
const backfillStatus   = ref('')
const retryError       = ref('')
const lastUpdate       = ref(null)
const loading          = ref(false)
let   pollTimer        = null

const lastUpdateLabel = computed(() => {
  if (!lastUpdate.value) return '—'
  const secs = Math.floor((Date.now() - lastUpdate.value) / 1000)
  if (secs < 10) return 'just now'
  return `${secs}s ago`
})

const maxBar = computed(() => {
  const vals = (stats.value.timeline || []).flatMap(s => [s.wtb, s.wts])
  return Math.max(...vals, 1)
})

function barHeight(val) {
  return Math.round((val / maxBar.value) * 80)
}

async function refresh() {
  const accountParam = selectedAccount.value || undefined
  const params = { ...resolveDateParams(), ...(accountParam ? { account: accountParam } : {}) }
  const [statsRes, prodRes, actRes] = await Promise.all([
    tradingApi.getStats(params),
    tradingApi.getProductStats(params),
    tradingApi.getClassificationActivity(params),
  ])
  stats.value            = statsRes.data
  productStats.value     = prodRes.data
  classifyActivity.value = actRes.data
  lastUpdate.value       = Date.now()
}

async function runBackfill() {
  backfillStatus.value = 'Queuing…'
  try {
    const accountParam = selectedAccount.value || undefined
    const { data } = await tradingApi.backfillClassify(
      accountParam ? { account: accountParam, limit: 20 } : { limit: 20 }
    )
    backfillStatus.value = `Queued ${data.queued} message(s) — check logs in ~30s`
    setTimeout(() => { backfillStatus.value = '' }, 15000)
    setTimeout(refresh, 8000)
  } catch (e) {
    backfillStatus.value = 'Failed: ' + (e.response?.data?.detail || e.message)
  }
}

async function runRetry() {
  backfillStatus.value = 'Retrying inquiry creation…'
  try {
    const accountParam = selectedAccount.value || undefined
    const { data } = await tradingApi.retryInquiries(
      accountParam ? { account: accountParam } : {}
    )
    if (data.errors && data.first_error) {
      backfillStatus.value = `Created ${data.created}, ${data.errors} errors — see below`
      retryError.value = data.first_error
    } else {
      backfillStatus.value = `Created ${data.created} inquiries`
      retryError.value = ''
      setTimeout(() => { backfillStatus.value = '' }, 10000)
    }
    await refresh()
  } catch (e) {
    backfillStatus.value = 'Failed: ' + (e.response?.data?.detail || e.message)
  }
}

onMounted(async () => {
  loading.value = true
  const { data } = await accountsApi.list()
  accounts.value = data
  await refresh()
  loading.value = false
  pollTimer = setInterval(refresh, 30000)
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
})
</script>

<style scoped>
.analytics-view { display: flex; flex-direction: column; height: 100%; overflow: hidden; background: #f9fafb; }
.analytics-header { display: flex; justify-content: space-between; align-items: center; padding: 14px 20px; background: #fff; border-bottom: 1px solid #e5e7eb; shrink: 0; }
.header-left { display: flex; align-items: center; gap: 12px; }
.header-left h2 { margin: 0; font-size: 1.15rem; }
.last-update { font-size: 0.78rem; color: #9ca3af; }
.header-right { display: flex; gap: 10px; align-items: center; }
.account-select { padding: 5px 10px; border: 1px solid #d1d5db; border-radius: 6px; font-size: 0.85rem; }
.btn-ghost { padding: 6px 14px; border: 1px solid #d1d5db; border-radius: 6px; background: transparent; cursor: pointer; font-size: 0.85rem; }
.btn-ghost.sm { padding: 4px 10px; font-size: 0.8rem; }
.btn-retry { padding: 4px 10px; font-size: 0.8rem; border: 1px solid #f59e0b; border-radius: 6px; background: #fffbeb; color: #92400e; cursor: pointer; font-weight: 600; }

.page-body { flex: 1; overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 16px; }

.section-card { background: #fff; border: 1px solid #e5e7eb; border-radius: 10px; padding: 16px; }
.section-title { font-size: 0.8rem; font-weight: 600; color: #6b7280; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 12px; }
.section-title-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.section-actions { display: flex; gap: 6px; }

.two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }

.mini-table { width: 100%; border-collapse: collapse; font-size: 0.83rem; }
.mini-table.wide td, .mini-table.wide th { padding: 6px 10px; }
.mini-table th { color: #9ca3af; font-weight: 500; padding: 3px 8px; text-align: left; border-bottom: 1px solid #f3f4f6; }
.mini-table td { padding: 5px 8px; border-bottom: 1px solid #f9fafb; }
.mini-table td.cap { text-transform: capitalize; }
.total-col { font-weight: 600; color: #374151; }

.classify-row { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 12px; }
.classify-chip { padding: 3px 10px; border-radius: 999px; font-size: 0.75rem; font-weight: 600; }
.classify-chip.total   { background: #f3f4f6; color: #374151; }
.classify-chip.inquiry { background: #dcfce7; color: #15803d; }
.classify-chip.warn    { background: #fef9c3; color: #92400e; }
.classify-chip.error   { background: #fee2e2; color: #b91c1c; }

.recent-classifications { display: flex; flex-direction: column; gap: 3px; max-height: 280px; overflow-y: auto; }
.mc-row { display: flex; align-items: flex-start; gap: 8px; padding: 4px 0; border-bottom: 1px solid #f3f4f6; }
.mc-badge { flex-shrink: 0; padding: 1px 7px; border-radius: 4px; font-size: 0.7rem; font-weight: 700; text-transform: uppercase; }
.badge-yes { background: #dcfce7; color: #15803d; }
.badge-no  { background: #f3f4f6; color: #9ca3af; }
.mc-summary { font-size: 0.78rem; color: #374151; line-height: 1.4; }

.backfill-msg { font-size: 0.75rem; color: #6b7280; margin-bottom: 8px; }
.retry-error { font-size: 0.7rem; color: #b91c1c; background: #fef2f2; border: 1px solid #fecaca; border-radius: 4px; padding: 6px 8px; white-space: pre-wrap; word-break: break-all; margin-top: 6px; max-height: 160px; overflow-y: auto; }
.empty-msg { text-align: center; color: #9ca3af; font-size: 0.85rem; padding: 20px; }

.chart-wrap { display: flex; align-items: flex-end; gap: 3px; height: 100px; padding-top: 10px; }
.chart-slot { display: flex; flex-direction: column; align-items: center; flex: 1; }
.bar-group { display: flex; align-items: flex-end; gap: 1px; }
.bar { width: 8px; border-radius: 2px 2px 0 0; min-height: 2px; transition: height 0.3s; }
.wtb-bar { background: #22c55e; }
.wts-bar { background: #f97316; }
.slot-label { font-size: 0.62rem; color: #9ca3af; margin-top: 3px; }
.chart-legend { display: flex; align-items: center; gap: 4px; font-size: 0.75rem; color: #6b7280; margin-top: 10px; }
.legend-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
.legend-dot.wtb { background: #22c55e; }
.legend-dot.wts { background: #f97316; }
</style>
