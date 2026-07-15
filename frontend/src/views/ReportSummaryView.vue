<template>
  <div class="report-view">
    <div class="report-header">
      <div class="header-left">
        <h2>Report Summary</h2>
        <span class="last-update">Updated {{ lastUpdateLabel }}</span>
      </div>
      <div class="header-right">
        <select v-model="selectedRange" @change="refresh" class="account-select">
          <option v-for="p in RANGE_PRESETS" :key="p.label" :value="p.label">{{ p.label }}</option>
          <option value="Custom">Custom range…</option>
        </select>
        <template v-if="selectedRange === 'Custom'">
          <input type="date" v-model="customFrom" class="account-select" :max="customTo || undefined" @change="refresh" />
          <span class="range-sep">to</span>
          <input type="date" v-model="customTo" class="account-select" :min="customFrom || undefined" @change="refresh" />
        </template>
        <select v-model="selectedAccount" @change="refresh" class="account-select">
          <option value="">All accounts</option>
          <option v-for="a in accounts" :key="a.id" :value="a.id">{{ a.display_name }}</option>
        </select>
        <select v-model="compareMode" @change="refresh" class="account-select">
          <option value="none">No comparison</option>
          <option value="day">Compare: Day-on-Day</option>
          <option value="month">Compare: Month-on-Month</option>
          <option value="year">Compare: Year-on-Year</option>
        </select>
        <button class="btn-ghost sm" @click="refresh">Refresh</button>
      </div>
    </div>

    <div class="page-body">
      <div class="tile-grid">
        <div v-for="m in METRIC_TILES" :key="m.key" class="tile" :title="m.hint">
          <div class="tile-value">{{ summary[m.key] ?? '—' }}</div>
          <div class="tile-label">{{ m.label }}</div>
          <div v-if="compareSummary" class="tile-delta" :class="deltaClass(summary[m.key], compareSummary[m.key])">
            {{ deltaText(summary[m.key], compareSummary[m.key]) }}
          </div>
        </div>
      </div>

      <div v-if="summary.status_breakdown?.length" class="section-title">By Status</div>
      <div v-if="summary.status_breakdown?.length" class="tile-grid">
        <div v-for="s in summary.status_breakdown" :key="s.status" class="tile">
          <div class="tile-value">{{ s.count }}</div>
          <div class="tile-label">{{ s.label }}</div>
          <div v-if="compareSummary" class="tile-delta" :class="deltaClass(s.count, compareStatusMap[s.status] ?? 0)">
            {{ deltaText(s.count, compareStatusMap[s.status] ?? 0) }}
          </div>
        </div>
      </div>

      <div v-if="summary.range" class="range-note">
        Showing {{ summary.range.date_from }} to {{ summary.range.date_to }}
        <template v-if="compareSummary?.range"> — comparing to {{ compareSummary.range.date_from }} to {{ compareSummary.range.date_to }}</template>
      </div>
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
  if (selectedRange.value === 'Custom') {
    return { date_from: customFrom.value || fmtDate(new Date()), date_to: customTo.value || customFrom.value || fmtDate(new Date()) }
  }
  const preset = RANGE_PRESETS.find(p => p.label === selectedRange.value) || RANGE_PRESETS[0]
  const [from, to] = preset.range()
  return { date_from: fmtDate(from), date_to: fmtDate(to) }
}

function parseISODate(s) {
  const [y, m, d] = s.split('-').map(Number)
  return new Date(y, m - 1, d)
}

// Shifting a month/year needs day-of-month clamped to the target month's real length
// (e.g. Mar 31 minus 1 month must land on Feb 28/29, not overflow into March).
function shiftMonths(date, delta) {
  const day = date.getDate()
  date.setDate(1)
  date.setMonth(date.getMonth() + delta)
  const daysInTarget = new Date(date.getFullYear(), date.getMonth() + 1, 0).getDate()
  date.setDate(Math.min(day, daysInTarget))
}

// Given the currently resolved date_from/date_to, returns the equivalent prior period
// for the selected comparison unit — same range length, shifted back by exactly one
// day/month/year — so "compare" works consistently no matter which preset or custom
// range is currently selected.
function shiftRange(dateFrom, dateTo, unit) {
  const from = parseISODate(dateFrom)
  const to   = parseISODate(dateTo)
  if (unit === 'day') {
    from.setDate(from.getDate() - 1)
    to.setDate(to.getDate() - 1)
  } else if (unit === 'month') {
    shiftMonths(from, -1)
    shiftMonths(to, -1)
  } else if (unit === 'year') {
    from.setFullYear(from.getFullYear() - 1)
    to.setFullYear(to.getFullYear() - 1)
  }
  return { date_from: fmtDate(from), date_to: fmtDate(to) }
}

function deltaClass(current, previous) {
  if (current == null || previous == null) return ''
  if (current > previous) return 'delta-up'
  if (current < previous) return 'delta-down'
  return 'delta-flat'
}

function deltaText(current, previous) {
  if (current == null || previous == null) return ''
  const diff = current - previous
  if (previous === 0) return current === 0 ? 'flat' : `new (+${current})`
  const pct = Math.round((diff / previous) * 100)
  const sign = diff > 0 ? '+' : ''
  return `${sign}${diff} (${sign}${pct}%)`
}

const METRIC_TILES = [
  { key: 'total_messages_received', label: 'Messages Received' },
  { key: 'total_inquiries_created', label: 'Inquiries Created' },
  { key: 'total_wtb', label: 'WTB (Want to Buy)' },
  { key: 'total_wts', label: 'WTS (Want to Sell)' },
  { key: 'total_own_stock_matches', label: 'Related to Own Stock', hint: 'Inquiries where at least one item matched a product in our own catalog' },
  { key: 'total_near_matches', label: 'Had Near Matches', hint: "Inquiries where at least one item was only a 'near' (not exact) match" },
  { key: 'total_wtb_own_stock', label: 'WTB (Own Stock)', hint: 'WTB inquiries where at least one item matched a product in our own catalog' },
  { key: 'total_wts_own_stock', label: 'WTS (Own Stock)', hint: 'WTS inquiries where at least one item matched a product in our own catalog' },
  { key: 'total_wtb_near_match', label: 'WTB (Near Match)', hint: "WTB inquiries where at least one item was only a 'near' (not exact) match" },
  { key: 'total_wts_near_match', label: 'WTS (Near Match)', hint: "WTS inquiries where at least one item was only a 'near' (not exact) match" },
]

const accounts        = ref([])
const selectedAccount = ref('')
const selectedRange   = ref('Today')
const customFrom      = ref('')
const customTo        = ref('')
const compareMode     = ref('none') // 'none' | 'day' | 'month' | 'year'
const summary         = ref({})
const compareSummary  = ref(null)
const lastUpdate      = ref(null)
let   pollTimer       = null

const compareStatusMap = computed(() => {
  const map = {}
  for (const s of (compareSummary.value?.status_breakdown || [])) map[s.status] = s.count
  return map
})

const lastUpdateLabel = computed(() => {
  if (!lastUpdate.value) return '—'
  const secs = Math.floor((Date.now() - lastUpdate.value) / 1000)
  if (secs < 10) return 'just now'
  return `${secs}s ago`
})

async function refresh() {
  const accountParam = selectedAccount.value || undefined
  const dateParams = resolveDateParams()
  const params = { ...dateParams, ...(accountParam ? { account: accountParam } : {}) }

  const calls = [tradingApi.getReportSummary(params)]
  if (compareMode.value !== 'none') {
    const compareParams = {
      ...shiftRange(dateParams.date_from, dateParams.date_to, compareMode.value),
      ...(accountParam ? { account: accountParam } : {}),
    }
    calls.push(tradingApi.getReportSummary(compareParams))
  }

  const [current, previous] = await Promise.all(calls)
  summary.value = current.data
  compareSummary.value = previous ? previous.data : null
  lastUpdate.value = Date.now()
}

onMounted(async () => {
  const { data } = await accountsApi.list()
  accounts.value = data
  await refresh()
  pollTimer = setInterval(refresh, 30000)
})
onUnmounted(() => clearInterval(pollTimer))
</script>

<style scoped>
.report-view { display: flex; flex-direction: column; height: 100%; overflow: hidden; }
.report-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 14px 24px; border-bottom: 1px solid #e5e7eb; flex-shrink: 0;
}
.header-left { display: flex; align-items: baseline; gap: 10px; }
.header-left h2 { margin: 0; font-size: 1.15rem; }
.last-update { font-size: 0.78rem; color: #9ca3af; }
.header-right { display: flex; align-items: center; gap: 8px; }
.account-select { padding: 5px 10px; border: 1px solid #d1d5db; border-radius: 6px; font-size: 0.85rem; }
.range-sep { font-size: 0.8rem; color: #9ca3af; }
.btn-ghost { padding: 6px 14px; border: 1px solid #d1d5db; border-radius: 6px; background: transparent; cursor: pointer; font-size: 0.85rem; }
.btn-ghost.sm { padding: 4px 10px; font-size: 0.8rem; }
.page-body { flex: 1; overflow-y: auto; padding: 20px 24px; }
.tile-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 14px; }
.section-title { margin: 24px 0 12px; font-size: 0.95rem; font-weight: 600; color: #374151; }
.tile-grid + .section-title { margin-top: 24px; }
.tile {
  background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 10px;
  padding: 18px; display: flex; flex-direction: column; gap: 6px;
}
.tile-value { font-size: 1.9rem; font-weight: 700; color: #111827; }
.tile-label { font-size: 0.82rem; color: #6b7280; }
.tile-delta { font-size: 0.78rem; font-weight: 600; margin-top: 2px; }
.tile-delta.delta-up { color: #16a34a; }
.tile-delta.delta-down { color: #dc2626; }
.tile-delta.delta-flat { color: #9ca3af; }
.range-note { margin-top: 16px; font-size: 0.8rem; color: #9ca3af; }
</style>
