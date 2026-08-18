<template>
  <div class="offers-report">
    <div class="page-header">
      <div>
        <h1>Selling Offers Report</h1>
        <p>Counts created selling inquiries, offered products, targeted customers, and WA notifications.</p>
      </div>
      <div class="header-actions no-print">
        <button class="ghost-btn" :disabled="loading" @click="printReport">Print Report</button>
        <button class="primary-btn" :disabled="loading" @click="load">
          {{ loading ? 'Loading...' : 'Refresh' }}
        </button>
      </div>
    </div>

    <div class="print-report-head print-only">
      <h1>ChatLens - Selling Offers Report</h1>
      <p>{{ reportFilterLabel }} · Printed {{ printTimestamp }}</p>
    </div>

    <div class="filters no-print">
      <input v-model="filters.search" placeholder="Search offer, product, customer..." @keydown.enter="load" />
      <label>
        From
        <input v-model="filters.date_from" type="date" />
      </label>
      <label>
        To
        <input v-model="filters.date_to" type="date" />
      </label>
      <select v-model.number="filters.limit">
        <option :value="50">Top 50</option>
        <option :value="100">Top 100</option>
        <option :value="250">Top 250</option>
        <option :value="500">Top 500</option>
      </select>
      <button class="ghost-btn" @click="setToday">Today</button>
      <button class="ghost-btn" @click="setThisMonth">This Month</button>
      <button class="ghost-btn" @click="load">Apply</button>
    </div>

    <div v-if="error" class="error-box">{{ error }}</div>

    <div class="summary-grid">
      <div class="summary-card">
        <span>Inquiries Created</span>
        <strong>{{ number(summary.offers_created) }}</strong>
      </div>
      <div class="summary-card">
        <span>Open / Closed</span>
        <strong>{{ number(summary.open_offers) }} / {{ number(summary.closed_offers) }}</strong>
      </div>
      <div class="summary-card">
        <span>Product Rows</span>
        <strong>{{ number(summary.product_rows) }}</strong>
      </div>
      <div class="summary-card">
        <span>Distinct Products</span>
        <strong>{{ number(summary.distinct_products) }}</strong>
      </div>
      <div class="summary-card">
        <span>Customers Targeted</span>
        <strong>{{ number(summary.customers_targeted) }}</strong>
      </div>
      <div class="summary-card">
        <span>Customers Notified</span>
        <strong>{{ number(summary.customers_notified) }}</strong>
      </div>
      <div class="summary-card">
        <span>WA Button Presses</span>
        <strong>{{ number(summary.wa_presses) }}</strong>
      </div>
    </div>

    <section class="report-card">
      <div class="card-title">
        <div>
          <h2>Selling Inquiries</h2>
          <p>{{ rangeLabel }}</p>
        </div>
      </div>
      <div v-if="loading" class="empty-state">Loading report...</div>
      <div v-else-if="!rows.length" class="empty-state">No selling offers found for this range.</div>
      <table v-else>
        <thead>
          <tr>
            <th>#</th>
            <th>Inquiry</th>
            <th>Status</th>
            <th>Products</th>
            <th>Customers</th>
            <th>Notified</th>
            <th>WA Presses</th>
            <th>Created</th>
            <th>Closed</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, index) in rows" :key="row.id">
            <td>{{ index + 1 }}</td>
            <td>
              <div class="primary-text">{{ row.name }}</div>
              <div class="muted">#{{ row.id }}</div>
            </td>
            <td><span class="status-pill" :class="row.status">{{ row.status }}</span></td>
            <td>{{ number(row.product_count) }}</td>
            <td>{{ number(row.customer_count) }}</td>
            <td><span class="count-pill notified">{{ number(row.notified_count) }}</span></td>
            <td><span class="count-pill wa">{{ number(row.wa_press_count) }}</span></td>
            <td>{{ formatTime(row.created_at) }}</td>
            <td>{{ formatTime(row.closed_at) }}</td>
          </tr>
        </tbody>
      </table>
    </section>

    <section class="report-card">
      <div class="card-title">
        <div>
          <h2>Product Breakdown</h2>
          <p>Products selected inside the selling inquiries in this date range.</p>
        </div>
      </div>
      <div v-if="loading" class="empty-state">Loading product breakdown...</div>
      <div v-else-if="!products.length" class="empty-state">No product rows found for this range.</div>
      <table v-else>
        <thead>
          <tr>
            <th>#</th>
            <th>Product</th>
            <th>Offer Count</th>
            <th>Customers Sent To</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, index) in products" :key="row.product_id">
            <td>{{ index + 1 }}</td>
            <td>
              <div class="primary-text">{{ productName(row) }}</div>
              <div class="muted">#{{ row.product_id }}<span v-if="row.sku"> · {{ row.sku }}</span></div>
            </td>
            <td>{{ number(row.offer_count) }}</td>
            <td>{{ number(row.customers_sent_to) }}</td>
          </tr>
        </tbody>
      </table>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { tradingApi } from '@/api'

function fmtDate(date) {
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

const today = fmtDate(new Date())
const rows = ref([])
const products = ref([])
const summary = ref({})
const loading = ref(false)
const error = ref('')
const filters = ref({
  search: '',
  date_from: today,
  date_to: today,
  limit: 250,
})

const printTimestamp = computed(() => new Date().toLocaleString())
const rangeLabel = computed(() => `${filters.value.date_from || 'Any start'} to ${filters.value.date_to || 'Any end'}`)
const reportFilterLabel = computed(() => {
  const search = filters.value.search ? `Search: ${filters.value.search}` : 'All selling offers'
  return `${rangeLabel.value} · ${search} · Limit ${filters.value.limit}`
})

function params() {
  return Object.fromEntries(
    Object.entries(filters.value).filter(([, value]) => value !== '' && value !== null && value !== undefined),
  )
}

function number(value) {
  return Number(value || 0).toLocaleString()
}

function productName(row) {
  return `${row.brand || ''} ${row.name || ''}`.trim() || `Product #${row.product_id}`
}

function formatTime(value) {
  if (!value) return '-'
  return new Date(value).toLocaleString()
}

function printReport() {
  window.print()
}

function setToday() {
  filters.value.date_from = today
  filters.value.date_to = today
  load()
}

function setThisMonth() {
  const now = new Date()
  filters.value.date_from = fmtDate(new Date(now.getFullYear(), now.getMonth(), 1))
  filters.value.date_to = fmtDate(now)
  load()
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const { data } = await tradingApi.getSellingOffersReport(params())
    rows.value = data.results || []
    products.value = data.products || []
    summary.value = data.summary || {}
  } catch (err) {
    error.value = err.response?.data?.detail || err.message || 'Failed to load selling offers report'
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.offers-report { height: 100%; overflow-y: auto; padding: 24px; background: #f8fafc; color: #111827; }
.page-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 18px; }
.page-header h1 { margin: 0; font-size: 1.5rem; font-weight: 800; }
.page-header p { margin: 6px 0 0; color: #64748b; font-size: 0.9rem; }
.header-actions { display: flex; align-items: center; gap: 8px; }
.filters { display: flex; align-items: flex-end; gap: 10px; flex-wrap: wrap; margin-bottom: 18px; }
.filters input, .filters select { height: 36px; border: 1px solid #cbd5e1; border-radius: 8px; padding: 0 10px; background: #fff; font-size: 0.86rem; }
.filters > input { min-width: 320px; flex: 1; }
.filters label { display: flex; flex-direction: column; gap: 4px; color: #64748b; font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.05em; }
.primary-btn, .ghost-btn { height: 36px; border-radius: 8px; padding: 0 14px; font-weight: 700; cursor: pointer; }
.primary-btn { border: 1px solid #16a34a; background: #16a34a; color: #fff; }
.ghost-btn { border: 1px solid #cbd5e1; background: #fff; color: #334155; }
.primary-btn:disabled, .ghost-btn:disabled { opacity: 0.55; cursor: not-allowed; }
.summary-grid { display: grid; grid-template-columns: repeat(7, minmax(120px, 1fr)); gap: 12px; margin-bottom: 18px; }
.summary-card { border: 1px solid #e2e8f0; border-radius: 12px; background: #fff; padding: 14px 16px; }
.summary-card span { display: block; color: #64748b; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; }
.summary-card strong { display: block; margin-top: 6px; font-size: 1.45rem; }
.report-card { border: 1px solid #e2e8f0; border-radius: 12px; background: #fff; overflow: hidden; margin-bottom: 18px; }
.card-title { display: flex; justify-content: space-between; gap: 12px; padding: 14px 16px; border-bottom: 1px solid #e2e8f0; }
.card-title h2 { margin: 0; font-size: 1rem; font-weight: 800; }
.card-title p { margin: 4px 0 0; color: #64748b; font-size: 0.82rem; }
table { width: 100%; border-collapse: collapse; font-size: 0.86rem; }
th { text-align: left; background: #f8fafc; color: #64748b; font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.05em; padding: 12px 14px; border-bottom: 1px solid #e2e8f0; }
td { padding: 12px 14px; border-bottom: 1px solid #f1f5f9; vertical-align: top; }
tr:last-child td { border-bottom: none; }
.primary-text { font-weight: 800; color: #111827; }
.muted { margin-top: 3px; color: #64748b; font-size: 0.75rem; }
.status-pill { display: inline-flex; align-items: center; border-radius: 999px; padding: 3px 10px; font-weight: 800; text-transform: capitalize; }
.status-pill.open { background: #dcfce7; color: #15803d; }
.status-pill.closed { background: #e2e8f0; color: #334155; }
.count-pill { display: inline-flex; min-width: 34px; justify-content: center; padding: 3px 9px; border-radius: 999px; font-weight: 800; }
.count-pill.notified { background: #dbeafe; color: #1d4ed8; }
.count-pill.wa { background: #dcfce7; color: #15803d; }
.empty-state { padding: 42px; text-align: center; color: #94a3b8; }
.error-box { margin-bottom: 14px; border: 1px solid #fecaca; background: #fef2f2; color: #b91c1c; border-radius: 8px; padding: 10px 12px; font-size: 0.86rem; }
.print-only { display: none; }
@media (max-width: 1200px) {
  .summary-grid { grid-template-columns: repeat(3, minmax(140px, 1fr)); }
}
@media (max-width: 760px) {
  .summary-grid { grid-template-columns: repeat(2, minmax(140px, 1fr)); }
  .filters > input { min-width: 220px; }
}
@media print {
  :global(nav),
  :global(header:not(.print-report-head)) {
    display: none !important;
  }
  .offers-report {
    height: auto;
    overflow: visible;
    padding: 0;
    background: #fff;
  }
  .no-print { display: none !important; }
  .print-only { display: block !important; }
  .page-header { display: none; }
  .print-report-head {
    margin-bottom: 14px;
    border-bottom: 2px solid #111827;
    padding-bottom: 10px;
  }
  .print-report-head h1 { margin: 0 0 4px; font-size: 18pt; }
  .print-report-head p { margin: 0; color: #475569; font-size: 9pt; }
  .summary-grid {
    grid-template-columns: repeat(4, 1fr);
    gap: 8px;
    margin-bottom: 12px;
    break-inside: avoid;
    page-break-inside: avoid;
  }
  .summary-card {
    border: 1px solid #cbd5e1;
    border-radius: 0;
    padding: 8px 10px;
  }
  .summary-card span { font-size: 7.5pt; }
  .summary-card strong { font-size: 15pt; }
  .report-card {
    border: none;
    border-radius: 0;
    overflow: visible;
  }
  table { font-size: 8.5pt; }
  th { color: #111827; background: #f1f5f9; }
  th, td { padding: 5px 6px; }
  tr {
    break-inside: avoid;
    page-break-inside: avoid;
  }
  .count-pill, .status-pill {
    border-radius: 0;
    border: 1px solid currentColor;
    background: #fff !important;
    print-color-adjust: exact;
    -webkit-print-color-adjust: exact;
  }
}
</style>
