<template>
  <div class="mentions-report">
    <div class="page-header">
      <div>
        <h1>Inventory Product Mentions</h1>
        <p>Item-wise report of how often inventory products appeared in WTB and WTS inquiries.</p>
      </div>
      <button class="primary-btn" :disabled="loading" @click="load">
        {{ loading ? 'Loading...' : 'Refresh' }}
      </button>
    </div>

    <div class="filters">
      <input v-model="filters.search" placeholder="Search product, brand, or extracted line..." @keydown.enter="load" />
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
      <button class="ghost-btn" @click="load">Apply</button>
    </div>

    <div v-if="error" class="error-box">{{ error }}</div>

    <div class="summary-grid">
      <div class="summary-card">
        <span>Total Mentions</span>
        <strong>{{ summary.total_mentions ?? 0 }}</strong>
      </div>
      <div class="summary-card">
        <span>WTB Mentions</span>
        <strong>{{ summary.total_wtb ?? 0 }}</strong>
      </div>
      <div class="summary-card">
        <span>WTS Mentions</span>
        <strong>{{ summary.total_wts ?? 0 }}</strong>
      </div>
      <div class="summary-card">
        <span>Products Mentioned</span>
        <strong>{{ summary.products ?? 0 }}</strong>
      </div>
    </div>

    <div class="report-card">
      <div v-if="loading" class="empty-state">Loading report...</div>
      <div v-else-if="!rows.length" class="empty-state">No product mentions found for this range.</div>
      <table v-else>
        <thead>
          <tr>
            <th>Product</th>
            <th>Stock</th>
            <th>WTB</th>
            <th>WTS</th>
            <th>Total</th>
            <th>Last Seen</th>
            <th>First Seen</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="row.product_id">
            <td>
              <div class="product-name">{{ productName(row) }}</div>
              <div class="product-meta">#{{ row.product_id }}<span v-if="row.sku"> · {{ row.sku }}</span></div>
            </td>
            <td>
              <div>{{ row.qty ?? 0 }} pcs</div>
              <div v-if="row.sale_price" class="product-meta">{{ row.currency || 'AED' }} {{ row.sale_price }}</div>
            </td>
            <td><span class="count-pill buy">{{ row.wtb_count }}</span></td>
            <td><span class="count-pill sell">{{ row.wts_count }}</span></td>
            <td><strong>{{ row.total_count }}</strong></td>
            <td>{{ formatTime(row.last_seen) }}</td>
            <td>{{ formatTime(row.first_seen) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { tradingApi } from '@/api'

const rows = ref([])
const summary = ref({})
const loading = ref(false)
const error = ref('')
const today = new Date().toISOString().slice(0, 10)
const filters = ref({
  search: '',
  date_from: today,
  date_to: today,
  limit: 100,
})

function params() {
  return Object.fromEntries(
    Object.entries(filters.value).filter(([, value]) => value !== '' && value !== null && value !== undefined),
  )
}

function productName(row) {
  return `${row.brand || ''} ${row.name || ''}`.trim() || `Product #${row.product_id}`
}

function formatTime(value) {
  if (!value) return '-'
  return new Date(value).toLocaleString()
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const { data } = await tradingApi.getInventoryProductMentions(params())
    rows.value = data.results || []
    summary.value = data.summary || {}
  } catch (err) {
    error.value = err.response?.data?.detail || err.message || 'Failed to load inventory product mentions'
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.mentions-report { height: 100%; overflow-y: auto; padding: 24px; background: #f8fafc; color: #111827; }
.page-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 18px; }
.page-header h1 { margin: 0; font-size: 1.5rem; font-weight: 800; }
.page-header p { margin: 6px 0 0; color: #64748b; font-size: 0.9rem; }
.filters { display: flex; align-items: flex-end; gap: 10px; flex-wrap: wrap; margin-bottom: 18px; }
.filters input, .filters select { height: 36px; border: 1px solid #cbd5e1; border-radius: 8px; padding: 0 10px; background: #fff; font-size: 0.86rem; }
.filters > input { min-width: 320px; flex: 1; }
.filters label { display: flex; flex-direction: column; gap: 4px; color: #64748b; font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.05em; }
.primary-btn, .ghost-btn { height: 36px; border-radius: 8px; padding: 0 14px; font-weight: 700; cursor: pointer; }
.primary-btn { border: 1px solid #16a34a; background: #16a34a; color: #fff; }
.ghost-btn { border: 1px solid #cbd5e1; background: #fff; color: #334155; }
.summary-grid { display: grid; grid-template-columns: repeat(4, minmax(140px, 1fr)); gap: 12px; margin-bottom: 18px; }
.summary-card { border: 1px solid #e2e8f0; border-radius: 12px; background: #fff; padding: 14px 16px; }
.summary-card span { display: block; color: #64748b; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; }
.summary-card strong { display: block; margin-top: 6px; font-size: 1.6rem; }
.report-card { border: 1px solid #e2e8f0; border-radius: 12px; background: #fff; overflow: hidden; }
table { width: 100%; border-collapse: collapse; font-size: 0.86rem; }
th { text-align: left; background: #f8fafc; color: #64748b; font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.05em; padding: 12px 14px; border-bottom: 1px solid #e2e8f0; }
td { padding: 12px 14px; border-bottom: 1px solid #f1f5f9; vertical-align: top; }
tr:last-child td { border-bottom: none; }
.product-name { font-weight: 800; color: #111827; }
.product-meta { margin-top: 3px; color: #64748b; font-size: 0.75rem; }
.count-pill { display: inline-flex; min-width: 34px; justify-content: center; padding: 3px 9px; border-radius: 999px; font-weight: 800; }
.count-pill.buy { background: #dcfce7; color: #15803d; }
.count-pill.sell { background: #fef3c7; color: #b45309; }
.empty-state { padding: 48px; text-align: center; color: #94a3b8; }
.error-box { margin-bottom: 14px; border: 1px solid #fecaca; background: #fef2f2; color: #b91c1c; border-radius: 8px; padding: 10px 12px; font-size: 0.86rem; }
@media (max-width: 900px) {
  .summary-grid { grid-template-columns: repeat(2, minmax(140px, 1fr)); }
  .filters > input { min-width: 220px; }
}
</style>
