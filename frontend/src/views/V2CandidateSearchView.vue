<script setup>
import { ref } from 'vue'
import { tradingApi } from '@/api'

const query = ref('')
const brand = ref('Apple')
const topK = ref(10)
const attributes = ref('{\n  "Model": "17 Pro Max",\n  "Storage": "256",\n  "Color": "Silver",\n  "SIM Type": "eSIM"\n}')
const loading = ref(false)
const error = ref('')
const searched = ref(false)
const results = ref([])

function formatDistance(value) {
  if (value == null) return '-'
  return Number(value).toFixed(4)
}

function formatAttributes(attrs) {
  if (!Array.isArray(attrs)) return '-'
  return attrs.map((attr) => `${attr.key}: ${attr.value}`).join(', ')
}

async function runSearch() {
  const q = query.value.trim()
  if (!q) {
    error.value = 'Enter a search query.'
    return
  }
  loading.value = true
  error.value = ''
  searched.value = true
  try {
    const params = {
      q,
      top_k: topK.value || 10,
    }
    if (brand.value.trim()) params.brand = brand.value.trim()
    if (attributes.value.trim()) params.attributes = attributes.value.trim()
    const { data } = await tradingApi.searchV2Candidates(params)
    results.value = data.results || []
  } catch (e) {
    error.value = e.response?.data?.detail || 'V2 candidate search failed.'
    results.value = []
  } finally {
    loading.value = false
  }
}

function useInquiryExample() {
  query.value = 'iPhone 17 Pro Max 256GB Silver eSIM'
  brand.value = 'Apple'
  attributes.value = '{\n  "Model": "17 Pro Max",\n  "Storage": "256",\n  "Color": "Silver",\n  "SIM Type": "eSIM"\n}'
}
</script>

<template>
  <main class="v2-candidate-page">
    <header class="page-header">
      <div>
        <h1>V2 Candidate Search</h1>
        <p>Uses the same V2 pass-2 candidate retrieval path, including embedding retrieval and attribute reranking.</p>
      </div>
      <button class="secondary-btn" @click="useInquiryExample">Use Inquiry 16065 Example</button>
    </header>

    <section class="search-card">
      <div class="field query-field">
        <label>Search query</label>
        <input v-model="query" type="text" placeholder="e.g. iPhone 17 Pro Max 256GB Silver eSIM" @keydown.enter="runSearch" />
      </div>
      <div class="field small-field">
        <label>Brand</label>
        <input v-model="brand" type="text" placeholder="Optional" @keydown.enter="runSearch" />
      </div>
      <div class="field tiny-field">
        <label>Top K</label>
        <input v-model.number="topK" type="number" min="1" max="20" @keydown.enter="runSearch" />
      </div>
      <button class="primary-btn" :disabled="loading" @click="runSearch">
        {{ loading ? 'Searching...' : 'Search' }}
      </button>
      <div class="field attributes-field">
        <label>Attributes JSON used for V2 reranking</label>
        <textarea v-model="attributes" spellcheck="false" />
      </div>
    </section>

    <div v-if="error" class="alert error">{{ error }}</div>

    <section class="table-card">
      <div v-if="loading" class="empty">Searching...</div>
      <div v-else-if="searched && !results.length" class="empty">No candidates found.</div>
      <div v-else-if="!searched" class="empty">Run a search to inspect V2 candidate ordering.</div>
      <table v-else v-ui-data-table="'v2-candidate-search'">
        <thead>
          <tr>
            <th>Rank</th>
            <th>Product</th>
            <th>Brand</th>
            <th>Qty</th>
            <th>Stock</th>
            <th>Distance</th>
            <th>Attribute Score</th>
            <th>Ranking Score</th>
            <th>Attribute Notes</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, index) in results" :key="row.product_id">
            <td>{{ index + 1 }}</td>
            <td>
              <strong>#{{ row.product_id }} {{ row.name }}</strong>
              <div class="muted">{{ formatAttributes(row.attributes) }}</div>
            </td>
            <td>{{ row.brand || '-' }}</td>
            <td>{{ row.qty ?? '-' }}</td>
            <td>
              <span :class="['stock-pill', row.stock_status === 'in_stock' ? 'in' : 'out']">
                {{ row.stock_status || '-' }}
              </span>
            </td>
            <td>{{ formatDistance(row.distance) }}</td>
            <td>{{ row.attribute_score ?? '-' }}</td>
            <td>{{ row.ranking_score ?? '-' }}</td>
            <td>
              <div v-for="note in row.attribute_match_notes || []" :key="note" class="note">{{ note }}</div>
            </td>
          </tr>
        </tbody>
      </table>
    </section>
  </main>
</template>

<style scoped>
.v2-candidate-page { height: 100%; overflow: auto; padding: var(--ui-page-padding); color: var(--ui-text); background: var(--ui-bg); font-family: var(--ui-font-sans); }
.page-header { display: flex; justify-content: space-between; gap: 16px; align-items: flex-start; margin-bottom: 18px; }
.page-header h1 { margin: 0 0 4px; color: var(--ui-text-strong); font-family: var(--ui-font-display); font-size: 1.5rem; font-weight: 700; }
.page-header p { margin: 0; color: var(--ui-text-muted); }
.search-card { display: grid; grid-template-columns: minmax(320px, 1fr) 160px 90px auto; gap: 12px; align-items: end; background: var(--ui-surface); border: 1px solid var(--ui-border); border-radius: var(--ui-radius-lg); padding: 16px; margin-bottom: 14px; box-shadow: var(--ui-shadow-card); }
.field { display: flex; flex-direction: column; gap: 6px; }
.field label { font-size: 0.78rem; font-weight: 700; color: var(--ui-text-muted); text-transform: uppercase; letter-spacing: 0.05em; }
.field input, .field textarea { border: 1px solid var(--ui-border-strong); border-radius: var(--ui-radius-sm); padding: 8px 10px; color: var(--ui-text); font-size: 0.9rem; background: var(--ui-surface); }
.attributes-field { grid-column: 1 / -1; }
.attributes-field textarea { min-height: 110px; font-family: Consolas, monospace; }
.primary-btn, .secondary-btn { border: 0; border-radius: var(--ui-radius-sm); padding: 9px 14px; font-weight: 700; cursor: pointer; }
.primary-btn { background: var(--ui-primary); color: var(--ui-on-primary); }
.primary-btn:disabled { opacity: 0.6; cursor: not-allowed; }
.secondary-btn { background: var(--ui-info-soft); color: var(--ui-info); }
.alert { border-radius: var(--ui-radius-sm); padding: 10px 12px; margin-bottom: 12px; font-size: 0.88rem; }
.alert.error { background: var(--ui-danger-soft); color: var(--ui-danger); border: 1px solid color-mix(in srgb,var(--ui-danger) 30%,var(--ui-border)); }
.table-card { background: var(--ui-surface); border: 1px solid var(--ui-border); border-radius: var(--ui-radius-lg); overflow: hidden; box-shadow: var(--ui-shadow-card); }
.empty { padding: 42px; text-align: center; color: var(--ui-text-subtle); }
table { width: 100%; border-collapse: collapse; font-size: 0.86rem; }
th { text-align: left; background: var(--ui-surface-muted); color: var(--ui-text-muted); font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.06em; padding: 11px 12px; border-bottom: 1px solid var(--ui-border); }
td { padding: 12px; border-bottom: 1px solid var(--ui-border); vertical-align: top; }
.muted { color: var(--ui-text-muted); font-size: 0.78rem; margin-top: 4px; }
.stock-pill { display: inline-flex; border-radius: 999px; padding: 3px 8px; font-size: 0.72rem; font-weight: 700; }
.stock-pill.in { background: var(--ui-success-soft); color: var(--ui-success); }
.stock-pill.out { background: var(--ui-danger-soft); color: var(--ui-danger); }
.note { color: var(--ui-text-muted); font-size: 0.78rem; line-height: 1.35; }
@media (max-width: 900px) {
  .search-card { grid-template-columns: 1fr; }
}
</style>
