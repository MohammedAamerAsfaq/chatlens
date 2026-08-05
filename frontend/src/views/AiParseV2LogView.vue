<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { accountsApi, tradingApi } from '@/api'

const logs = ref([])
const accounts = ref([])
const loading = ref(false)
const expandedId = ref(null)
const filterAccount = ref('all')
const filterStatus = ref('all')
const page = ref(1)
const pageSize = ref(25)
const totalCount = ref(0)
const pageSizeOptions = [10, 25, 50, 100]
const SLOW_THRESHOLD_MS = 120000

const totalPages = computed(() => Math.max(1, Math.ceil(totalCount.value / pageSize.value)))
const pageStart = computed(() => totalCount.value === 0 ? 0 : (page.value - 1) * pageSize.value + 1)
const pageEnd = computed(() => Math.min(page.value * pageSize.value, totalCount.value))
const panelTabs = ref({})

const STATUS_LABELS = {
  pass1_started: 'Pass 1 Started',
  pass1_done: 'Pass 1 Done',
  pass2_started: 'Pass 2 Started',
  complete: 'Complete',
  error: 'Error',
}

function statusLabel(status) {
  return STATUS_LABELS[status] || status
}

function statusClass(status) {
  if (status === 'complete') return 'status-complete'
  if (status === 'error') return 'status-error'
  if (status === 'pass2_started') return 'status-pass2'
  return 'status-pending'
}

function buildParams() {
  const params = { page: page.value, page_size: pageSize.value }
  if (filterAccount.value !== 'all') params.account = filterAccount.value
  if (filterStatus.value !== 'all') params.status = filterStatus.value
  return params
}

async function fetchLogs(showSpinner = false) {
  if (showSpinner) loading.value = true
  try {
    const { data } = await tradingApi.listAiParseV2Logs(buildParams())
    logs.value = data.results
    totalCount.value = data.count
  } finally {
    loading.value = false
  }
}

async function fetchAccounts() {
  const { data } = await accountsApi.list()
  accounts.value = data.results ?? data
}

watch([filterAccount, filterStatus, pageSize], () => {
  page.value = 1
  fetchLogs()
})
watch(page, () => fetchLogs())

onMounted(() => {
  fetchAccounts()
  fetchLogs(true)
})

function toggleRow(id) {
  expandedId.value = expandedId.value === id ? null : id
}

function formatTime(value) {
  if (!value) return ''
  return new Date(value).toLocaleString()
}

function relativeTime(value) {
  const diff = Math.floor((Date.now() - new Date(value)) / 1000)
  if (diff < 60) return `${diff}s ago`
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  return `${Math.floor(diff / 86400)}d ago`
}

function formatDuration(ms) {
  if (ms == null) return '-'
  if (ms < 1000) return `${ms} ms`
  return `${(ms / 1000).toFixed(ms < 10000 ? 2 : 1)} s`
}

function elapsedMs(log) {
  if (log.total_ms != null) return log.total_ms
  return Math.max(0, Date.now() - new Date(log.created_at).getTime())
}

function stuckStage(log) {
  if (log.status === 'pass1_started') return 'waiting for pass 1 AI response'
  if (log.status === 'pass1_done') return 'waiting for pass 2 candidate search to start'
  if (log.status === 'pass2_started') {
    if (!log.pass2_response) return 'waiting for pass 2 AI response'
    return 'processing pass 2 response'
  }
  if (log.status === 'error') return 'failed with error'
  if (log.status === 'complete') return 'completed, but exceeded expected duration'
  return `status: ${statusLabel(log.status)}`
}

function slowNotice(log) {
  const ms = elapsedMs(log)
  if (ms <= SLOW_THRESHOLD_MS) return ''
  return `Taking ${formatDuration(ms)} - ${stuckStage(log)}.`
}

function remainingDuration(total, ...parts) {
  if (total == null) return null
  const known = parts.filter((part) => part != null).reduce((sum, part) => sum + part, 0)
  return Math.max(0, total - known)
}

function jsonText(value) {
  if (value == null || value === '') return ''
  if (typeof value === 'string') return value
  return JSON.stringify(value, null, 2)
}

function parseJson(value) {
  if (value == null || value === '') return null
  if (typeof value === 'object') return value
  try {
    return JSON.parse(value)
  } catch {
    return value
  }
}

function panelKey(log, panel) {
  return `${log.id}:${panel}`
}

function activeTab(log, panel) {
  return panelTabs.value[panelKey(log, panel)] || 'formatted'
}

function setActiveTab(log, panel, tab) {
  panelTabs.value = { ...panelTabs.value, [panelKey(log, panel)]: tab }
}

function panels(log) {
  return [
    { key: 'pass1_request', title: 'Pass 1 Request', type: 'request', value: log.pass1_request, timings: [] },
    { key: 'pass1_response', title: 'Pass 1 Response', type: 'response', value: log.pass1_response, timings: [['AI response', log.pass1_ai_ms]] },
    { key: 'pass1_parsed', title: 'Pass 1 Parsed', type: 'response', value: log.pass1_parsed, timings: [['Parse/save', remainingDuration(log.pass1_total_ms, log.pass1_ai_ms)], ['Pass 1 total', log.pass1_total_ms]] },
    { key: 'pass2_request', title: 'Pass 2 Request', type: 'pass2_request', value: log.pass2_request, timings: [['Candidate DB/search', log.candidate_search_ms]] },
    { key: 'pass2_response', title: 'Pass 2 Response', type: 'match_response', value: log.pass2_response, timings: [['AI response', log.pass2_ai_ms]] },
    { key: 'pass2_parsed', title: 'Pass 2 Parsed', type: 'match_parsed', value: log.pass2_parsed, timings: [['Parse/save', remainingDuration(log.pass2_total_ms, log.candidate_search_ms, log.pass2_ai_ms)], ['Pass 2 total', log.pass2_total_ms]] },
  ]
}

function requestMessages(value) {
  const parsed = parseJson(value)
  return Array.isArray(parsed?.messages) ? parsed.messages : []
}

function requestTemperature(value) {
  const parsed = parseJson(value)
  return parsed && typeof parsed === 'object' ? parsed.temperature : null
}

function pass2Payload(value) {
  const userMessage = requestMessages(value).find((message) => message.role === 'user')
  return parseJson(userMessage?.content)
}

function pass2Batches(value) {
  const parsed = parseJson(value)
  return Array.isArray(parsed?.batches) ? parsed.batches : []
}

function pass2ResponseBatches(value) {
  const parsed = parseJson(value)
  return Array.isArray(parsed) ? parsed : []
}

function pass2CandidatePool(value) {
  const payload = pass2Payload(value)
  return Array.isArray(payload?.candidate_pool) ? payload.candidate_pool : []
}

function asObject(value) {
  const parsed = parseJson(value)
  return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed : null
}

function skippedPass2(log) {
  const request = asObject(log.pass2_request)
  if (request?.skipped) return request
  const parsed = asObject(log.pass2_parsed)
  if (parsed?.skipped) return parsed
  return null
}

function summaryFields(value) {
  const obj = asObject(value)
  if (!obj) return []
  return [
    ['Tags', Array.isArray(obj.tags) ? obj.tags.join(', ') : ''],
    ['Inquiry', obj.is_inquiry == null ? '' : String(obj.is_inquiry)],
    ['Type', obj.inquiry_type || ''],
    ['Summary', obj.summary || ''],
    ['Dedup Key', obj.dedup_key || ''],
    ['Contact Suggestion', obj.contact_category_suggestion || ''],
  ].filter(([, fieldValue]) => fieldValue !== '')
}

function productsFrom(value) {
  const obj = asObject(value)
  return Array.isArray(obj?.products) ? obj.products : []
}

function matchResultsFrom(value) {
  const obj = asObject(value)
  if (Array.isArray(obj?.results)) return obj.results
  if (Array.isArray(obj?.raw?.results)) return obj.raw.results
  if (obj?.match_results && typeof obj.match_results === 'object') {
    return Object.entries(obj.match_results).map(([lineIndex, result]) => ({
      line_index: lineIndex,
      ...result,
    }))
  }
  return []
}

function updatedProductsFrom(value) {
  const obj = asObject(value)
  return Array.isArray(obj?.updated_products) ? obj.updated_products : []
}

function candidateCount(product) {
  return Array.isArray(product?.candidates)
    ? product.candidates.length
    : Array.isArray(product?.candidate_products)
      ? product.candidate_products.length
      : Array.isArray(product?.candidate_ids)
        ? product.candidate_ids.length
      : 0
}

function formatAttributes(attributes) {
  if (!attributes || typeof attributes !== 'object' || Array.isArray(attributes)) return '-'
  const entries = Object.entries(attributes).filter(([, value]) => value != null && String(value).trim() !== '')
  return entries.length ? entries.map(([key, value]) => `${key}: ${value}`).join(', ') : '-'
}

function candidatesForProduct(product, panelValue) {
  if (Array.isArray(product?.candidates)) return product.candidates
  if (Array.isArray(product?.candidate_products)) return product.candidate_products
  const ids = new Set(product?.candidate_ids || [])
  if (!ids.size) return []
  return pass2CandidatePool(panelValue).filter((candidate) => ids.has(candidate.product_id))
}
</script>

<template>
  <div class="v2-log-view">
    <div class="page-head">
      <div>
        <h1>AI Parse V2 Logs</h1>
        <p>Pass 1 and batched pass 2 request/response audit trail.</p>
      </div>
      <button class="refresh-btn" @click="fetchLogs(true)">Refresh</button>
    </div>

    <div class="filters">
      <select v-model="filterAccount">
        <option value="all">All accounts</option>
        <option v-for="account in accounts" :key="account.id" :value="account.id">
          {{ account.display_name || account.phone_number || `Account #${account.id}` }}
        </option>
      </select>
      <select v-model="filterStatus">
        <option value="all">All statuses</option>
        <option value="pass1_started">Pass 1 Started</option>
        <option value="pass1_done">Pass 1 Done</option>
        <option value="pass2_started">Pass 2 Started</option>
        <option value="complete">Complete</option>
        <option value="error">Error</option>
      </select>
      <span class="count">{{ totalCount.toLocaleString() }} entries</span>
      <div class="page-size">
        <span>Rows:</span>
        <button
          v-for="size in pageSizeOptions"
          :key="size"
          :class="{ active: pageSize === size }"
          @click="pageSize = size"
        >{{ size }}</button>
      </div>
    </div>

    <div class="table-card">
      <div v-if="loading" class="empty">Loading...</div>
      <div v-else-if="!logs.length" class="empty">No V2 parse logs found.</div>
      <table v-else>
        <thead>
          <tr>
            <th>Time</th>
            <th>Account</th>
            <th>Status</th>
            <th>Message</th>
            <th>Total Time</th>
            <th>Inquiry IDs</th>
          </tr>
        </thead>
        <tbody>
          <template v-for="log in logs" :key="log.id">
            <tr class="row" :class="{ expanded: expandedId === log.id }" @click="toggleRow(log.id)">
              <td :title="formatTime(log.created_at)">{{ relativeTime(log.created_at) }}</td>
              <td>{{ log.account_name }}</td>
              <td>
                <span class="status" :class="statusClass(log.status)">{{ statusLabel(log.status) }}</span>
                <div v-if="slowNotice(log)" class="slow-inline">{{ slowNotice(log) }}</div>
              </td>
              <td class="message-cell">{{ log.message_text || '(no text)' }}</td>
              <td>{{ formatDuration(log.total_ms) }}</td>
              <td>{{ (log.inquiry_ids || []).join(', ') || '-' }}</td>
            </tr>
            <tr v-if="expandedId === log.id">
              <td colspan="6" class="detail-cell">
                <div v-if="slowNotice(log)" class="slow-banner">
                  {{ slowNotice(log) }}
                </div>
                <div class="detail-grid">
                  <section v-for="panel in panels(log)" :key="panel.key" class="panel-card">
                    <div class="panel-head">
                      <div>
                        <h2>{{ panel.title }}</h2>
                        <div v-if="panel.timings?.length" class="timing-row">
                          <span v-for="[label, ms] in panel.timings" :key="label" class="timing-chip">
                            {{ label }}: {{ formatDuration(ms) }}
                          </span>
                        </div>
                      </div>
                      <div class="tabs" @click.stop>
                        <button
                          :class="{ active: activeTab(log, panel.key) === 'formatted' }"
                          @click="setActiveTab(log, panel.key, 'formatted')"
                        >Formatted</button>
                        <button
                          :class="{ active: activeTab(log, panel.key) === 'raw' }"
                          @click="setActiveTab(log, panel.key, 'raw')"
                        >Raw JSON</button>
                      </div>
                    </div>

                    <pre v-if="activeTab(log, panel.key) === 'raw'">{{ jsonText(panel.value) || 'Not recorded' }}</pre>

                    <div v-else class="formatted-panel">
                      <div v-if="!jsonText(panel.value) && !skippedPass2(log)" class="not-recorded">Not recorded</div>

                      <template v-else-if="skippedPass2(log) && ['pass2_request', 'match_response', 'match_parsed'].includes(panel.type)">
                        <div class="skip-card">
                          <div class="field-label">Pass 2 skipped</div>
                          <strong>{{ skippedPass2(log).reason || 'No pass 2 AI request was sent.' }}</strong>
                          <p>
                            This is not an empty log. Candidate search completed, but no eligible candidate set
                            required an AI match decision for this inquiry.
                          </p>
                        </div>
                        <article
                          v-for="(product, index) in skippedPass2(log).products || []"
                          :key="index"
                          class="product-card"
                        >
                          <div class="product-title">
                            <span>Extracted Product {{ index + 1 }}</span>
                            <strong>{{ product.canonical_name || product.raw_text }}</strong>
                          </div>
                          <div class="kv-grid">
                            <div><span>Raw</span><strong>{{ product.raw_text || '-' }}</strong></div>
                            <div><span>Brand</span><strong>{{ product.brand || '-' }}</strong></div>
                            <div><span>SKU-like</span><strong>{{ product.is_sku_like ? 'Yes' : 'No' }}</strong></div>
                            <div><span>SKU Code</span><strong>{{ product.sku_code || '-' }}</strong></div>
                            <div><span>Inferred Name</span><strong>{{ product.inferred_product_name || '-' }}</strong></div>
                            <div><span>Attributes</span><strong>{{ formatAttributes(product.attributes) }}</strong></div>
                            <div><span>Qty</span><strong>{{ product.quantity ?? '-' }}</strong></div>
                          </div>
                        </article>
                        <div v-for="result in matchResultsFrom(log.pass2_parsed)" :key="result.line_index" class="product-card">
                          <div class="product-title">
                            <span>Line {{ result.line_index }}</span>
                            <strong>{{ result.match_type || 'no match' }}</strong>
                          </div>
                          <p class="reason">{{ result.reason || '-' }}</p>
                        </div>
                      </template>

                      <template v-else-if="panel.type === 'request'">
                        <div v-for="message in requestMessages(panel.value)" :key="message.role" class="prompt-block">
                          <div class="field-label">{{ message.role }}</div>
                          <div class="prompt-text">{{ message.content }}</div>
                        </div>
                        <div v-if="requestTemperature(panel.value) !== null" class="kv-row">
                          <span>Temperature</span>
                          <strong>{{ requestTemperature(panel.value) }}</strong>
                        </div>
                      </template>

                      <template v-else-if="panel.type === 'pass2_request'">
                        <div v-if="pass2Batches(panel.value).length" class="batch-list">
                          <article v-for="batch in pass2Batches(panel.value)" :key="batch.batch_number" class="batch-card">
                            <div class="product-title">
                              <span>Batch {{ batch.batch_number }}</span>
                              <strong>Lines {{ (batch.original_line_indexes || []).join(', ') }}</strong>
                            </div>
                            <div v-for="message in requestMessages(batch)" :key="`${batch.batch_number}:${message.role}`" class="prompt-block">
                              <div class="field-label">{{ message.role }}</div>
                              <div class="prompt-text">{{ message.content }}</div>
                            </div>
                          </article>
                        </div>
                        <div v-else v-for="message in requestMessages(panel.value)" :key="message.role" class="prompt-block">
                          <div class="field-label">{{ message.role }}</div>
                          <div class="prompt-text">{{ message.content }}</div>
                        </div>
                        <div v-if="pass2Payload(panel.value)" class="product-list">
                          <div class="field-label">Original Message</div>
                          <div class="message-box">{{ pass2Payload(panel.value).original_message }}</div>
                          <div v-if="pass2CandidatePool(panel.value).length" class="candidate-pool">
                            <div class="field-label">Shared Candidate Pool</div>
                            <div
                              v-for="candidate in pass2CandidatePool(panel.value)"
                              :key="candidate.product_id"
                              class="candidate-row"
                            >
                              <span>#{{ candidate.product_id }} {{ candidate.name }}</span>
                              <small>qty {{ candidate.qty }} · {{ candidate.currency }} {{ candidate.sale_price }} · distance {{ Number(candidate.distance).toFixed(4) }}</small>
                            </div>
                          </div>
                          <article
                            v-for="product in pass2Payload(panel.value).products || []"
                            :key="product.line_index"
                            class="product-card"
                          >
                            <div class="product-title">
                              <span>Line {{ product.line_index }}</span>
                              <strong>{{ product.canonical_name || product.raw_text }}</strong>
                            </div>
                            <div class="kv-grid">
                              <div><span>Raw</span><strong>{{ product.raw_text || '-' }}</strong></div>
                              <div><span>Brand</span><strong>{{ product.brand || '-' }}</strong></div>
                              <div><span>SKU-like</span><strong>{{ product.is_sku_like ? 'Yes' : 'No' }}</strong></div>
                              <div><span>SKU Code</span><strong>{{ product.sku_code || '-' }}</strong></div>
                              <div><span>Inferred Name</span><strong>{{ product.inferred_product_name || '-' }}</strong></div>
                              <div><span>Attributes</span><strong>{{ formatAttributes(product.attributes) }}</strong></div>
                              <div><span>Qty</span><strong>{{ product.quantity ?? '-' }}</strong></div>
                              <div><span>Price</span><strong>{{ product.price ?? '-' }}</strong></div>
                              <div><span>Candidates</span><strong>{{ candidateCount(product) }}</strong></div>
                            </div>
                            <div v-if="candidatesForProduct(product, panel.value).length" class="candidate-list">
                              <div v-for="candidate in candidatesForProduct(product, panel.value)" :key="candidate.product_id" class="candidate-row">
                                <span>#{{ candidate.product_id }} {{ candidate.name }}</span>
                                <small>qty {{ candidate.qty }} · {{ candidate.currency }} {{ candidate.sale_price }} · distance {{ Number(candidate.distance).toFixed(4) }}</small>
                              </div>
                            </div>
                          </article>
                        </div>
                      </template>

                      <template v-else-if="panel.type === 'match_response' || panel.type === 'match_parsed'">
                        <div v-if="panel.type === 'match_response' && pass2ResponseBatches(panel.value).length" class="batch-list">
                          <article v-for="batch in pass2ResponseBatches(panel.value)" :key="batch.batch_number" class="batch-card">
                            <div class="product-title">
                              <span>Batch {{ batch.batch_number }}</span>
                              <strong>AI time: {{ formatDuration(batch.ai_ms) }}</strong>
                            </div>
                            <pre>{{ batch.raw_response }}</pre>
                          </article>
                        </div>
                        <div v-for="result in matchResultsFrom(panel.value)" :key="result.line_index" class="product-card">
                          <div class="product-title">
                            <span>Line {{ result.line_index }}</span>
                            <strong>Product #{{ result.product_id ?? 'none' }} · {{ result.match_type || 'no match' }}</strong>
                          </div>
                          <div class="kv-grid">
                            <div><span>Confidence</span><strong>{{ result.confidence ?? '-' }}</strong></div>
                            <div><span>Rejected</span><strong>{{ (result.rejected_candidate_ids || []).join(', ') || '-' }}</strong></div>
                          </div>
                          <p class="reason">{{ result.reason || '-' }}</p>
                        </div>
                        <article
                          v-for="product in updatedProductsFrom(panel.value)"
                          :key="product.v2_line_index"
                          class="product-card"
                        >
                          <div class="product-title">
                            <span>Updated Product</span>
                            <strong>{{ product.canonical_name || product.raw_text }}</strong>
                          </div>
                          <div class="kv-grid">
                            <div><span>Product ID</span><strong>{{ product.product_id ?? '-' }}</strong></div>
                            <div><span>Match</span><strong>{{ product.match_type || '-' }}</strong></div>
                            <div><span>Confidence</span><strong>{{ product.match_confidence ?? '-' }}</strong></div>
                            <div><span>Candidates</span><strong>{{ candidateCount(product) }}</strong></div>
                          </div>
                          <p class="reason">{{ product.match_reason || '-' }}</p>
                        </article>
                      </template>

                      <template v-else>
                        <div v-for="[label, value] in summaryFields(panel.value)" :key="label" class="kv-row">
                          <span>{{ label }}</span>
                          <strong>{{ value }}</strong>
                        </div>
                        <article v-for="(product, index) in productsFrom(panel.value)" :key="index" class="product-card">
                          <div class="product-title">
                            <span>Product {{ index + 1 }}</span>
                            <strong>{{ product.canonical_name || product.raw_text }}</strong>
                          </div>
                          <div class="kv-grid">
                            <div><span>Raw</span><strong>{{ product.raw_text || '-' }}</strong></div>
                            <div><span>Brand</span><strong>{{ product.brand || '-' }}</strong></div>
                            <div><span>SKU-like</span><strong>{{ product.is_sku_like ? 'Yes' : 'No' }}</strong></div>
                            <div><span>SKU Code</span><strong>{{ product.sku_code || '-' }}</strong></div>
                            <div><span>Inferred Name</span><strong>{{ product.inferred_product_name || '-' }}</strong></div>
                            <div><span>Attributes</span><strong>{{ formatAttributes(product.attributes) }}</strong></div>
                            <div><span>Qty</span><strong>{{ product.quantity ?? '-' }}</strong></div>
                            <div><span>Price</span><strong>{{ product.price ?? '-' }}</strong></div>
                            <div><span>Currency</span><strong>{{ product.currency || '-' }}</strong></div>
                          </div>
                        </article>
                      </template>
                    </div>
                  </section>
                  <section v-if="log.error" class="error-section">
                    <h2>Error</h2>
                    <pre>{{ log.error }}</pre>
                  </section>
                </div>
              </td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>

    <div v-if="totalCount > 0" class="pagination">
      <span>Showing {{ pageStart.toLocaleString() }}-{{ pageEnd.toLocaleString() }} of {{ totalCount.toLocaleString() }}</span>
      <div>
        <button :disabled="page === 1" @click="page--">Prev</button>
        <span>Page {{ page }} of {{ totalPages }}</span>
        <button :disabled="page >= totalPages" @click="page++">Next</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.v2-log-view { height: 100%; overflow-y: auto; padding: 24px; background: #f8fafc; color: #111827; }
.page-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; margin-bottom: 20px; }
.page-head h1 { margin: 0; font-size: 1.55rem; }
.page-head p { margin: 6px 0 0; color: #64748b; }
.refresh-btn, .pagination button, .page-size button {
  border: 1px solid #dbe3ef;
  background: #fff;
  border-radius: 8px;
  padding: 7px 11px;
  cursor: pointer;
}
.filters { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; margin-bottom: 14px; }
.filters select { border: 1px solid #dbe3ef; border-radius: 8px; padding: 8px 10px; background: #fff; }
.count { color: #64748b; font-size: 0.88rem; flex: 1; }
.page-size { display: flex; align-items: center; gap: 6px; color: #64748b; font-size: 0.84rem; }
.page-size button { padding: 5px 9px; font-size: 0.78rem; }
.page-size button.active { background: #16a34a; color: #fff; border-color: #16a34a; }
.table-card { background: #fff; border: 1px solid #e2e8f0; border-radius: 14px; overflow: hidden; box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04); }
.empty { padding: 42px; text-align: center; color: #94a3b8; }
table { width: 100%; border-collapse: collapse; font-size: 0.88rem; }
th { text-align: left; background: #f8fafc; color: #64748b; font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.06em; padding: 12px 14px; border-bottom: 1px solid #e2e8f0; }
td { padding: 11px 14px; border-bottom: 1px solid #f1f5f9; vertical-align: top; }
.row { cursor: pointer; }
.row:hover, .row.expanded { background: #f8fafc; }
.message-cell { max-width: 520px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #475569; }
.status { display: inline-flex; border-radius: 999px; padding: 3px 8px; font-size: 0.74rem; font-weight: 700; }
.status-complete { background: #dcfce7; color: #166534; }
.status-error { background: #fee2e2; color: #b91c1c; }
.status-pass2 { background: #dbeafe; color: #1d4ed8; }
.status-pending { background: #fef3c7; color: #92400e; }
.slow-inline { margin-top: 5px; max-width: 260px; color: #b45309; font-size: 0.72rem; font-weight: 700; line-height: 1.25; }
.detail-cell { background: #f8fafc; }
.slow-banner { margin-bottom: 10px; border: 1px solid #fbbf24; border-radius: 10px; background: #fffbeb; color: #92400e; padding: 9px 11px; font-size: 0.82rem; font-weight: 800; }
.detail-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.detail-grid section { border: 1px solid #e2e8f0; border-radius: 10px; background: #fff; overflow: hidden; }
.panel-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; padding: 8px 10px 8px 12px; border-bottom: 1px solid #e2e8f0; background: #f8fafc; }
.detail-grid h2 { margin: 0; font-size: 0.78rem; color: #334155; }
.timing-row { display: flex; flex-wrap: wrap; gap: 5px; margin-top: 5px; }
.timing-chip { display: inline-flex; border: 1px solid #bfdbfe; border-radius: 999px; background: #eff6ff; color: #1d4ed8; padding: 2px 7px; font-size: 0.68rem; font-weight: 700; }
.tabs { display: inline-flex; border: 1px solid #dbe3ef; border-radius: 8px; overflow: hidden; background: #fff; }
.tabs button { border: 0; background: transparent; color: #64748b; font-size: 0.72rem; padding: 5px 8px; cursor: pointer; }
.tabs button.active { background: #0f172a; color: #fff; }
pre { margin: 0; padding: 12px; max-height: 340px; overflow: auto; font-size: 0.76rem; line-height: 1.45; color: #d1fae5; background: #0f172a; white-space: pre-wrap; word-break: break-word; }
.formatted-panel { max-height: 420px; overflow: auto; padding: 12px; display: flex; flex-direction: column; gap: 12px; background: #fff; }
.not-recorded { color: #94a3b8; font-size: 0.86rem; }
.skip-card { border: 1px solid #fed7aa; border-radius: 12px; padding: 11px; background: #fff7ed; color: #9a3412; }
.skip-card strong { display: block; color: #7c2d12; margin-bottom: 6px; }
.skip-card p { margin: 0; line-height: 1.45; font-size: 0.82rem; }
.prompt-block { border: 1px solid #e2e8f0; border-radius: 10px; overflow: hidden; }
.batch-list { display: flex; flex-direction: column; gap: 10px; }
.batch-card { border: 1px solid #cbd5e1; border-radius: 12px; padding: 10px; background: #f8fafc; display: flex; flex-direction: column; gap: 10px; }
.field-label { color: #64748b; font-size: 0.7rem; font-weight: 800; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 6px; }
.prompt-block .field-label { padding: 8px 10px; margin: 0; background: #f8fafc; border-bottom: 1px solid #e2e8f0; }
.prompt-text { padding: 10px; color: #334155; font-size: 0.78rem; line-height: 1.45; white-space: pre-wrap; word-break: break-word; max-height: 240px; overflow-y: auto; }
.kv-row { display: grid; grid-template-columns: 140px 1fr; gap: 10px; align-items: start; font-size: 0.82rem; }
.kv-row span, .kv-grid span { color: #64748b; font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.06em; }
.kv-row strong, .kv-grid strong { color: #0f172a; font-weight: 650; word-break: break-word; }
.message-box { border: 1px solid #e2e8f0; border-radius: 10px; padding: 10px; color: #334155; background: #f8fafc; white-space: pre-wrap; }
.product-list { display: flex; flex-direction: column; gap: 10px; }
.product-card { border: 1px solid #dbe3ef; border-radius: 12px; padding: 10px; background: #f8fafc; }
.product-title { display: flex; flex-direction: column; gap: 3px; margin-bottom: 10px; }
.product-title span { color: #64748b; font-size: 0.72rem; font-weight: 800; text-transform: uppercase; letter-spacing: 0.08em; }
.product-title strong { color: #0f172a; font-size: 0.92rem; }
.kv-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
.kv-grid div { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.candidate-list { display: flex; flex-direction: column; gap: 5px; margin-top: 10px; }
.candidate-pool { border: 1px solid #e2e8f0; border-radius: 12px; padding: 10px; background: #fff; display: flex; flex-direction: column; gap: 6px; }
.candidate-row { display: flex; flex-direction: column; gap: 2px; border-top: 1px solid #e2e8f0; padding-top: 7px; color: #0f172a; }
.candidate-row small { color: #64748b; }
.reason { margin: 8px 0 0; color: #475569; line-height: 1.45; }
.error-section { grid-column: 1 / -1; }
.pagination { display: flex; justify-content: space-between; align-items: center; gap: 12px; padding: 14px 4px; color: #64748b; font-size: 0.86rem; }
.pagination div { display: flex; align-items: center; gap: 10px; }
.pagination button:disabled { opacity: 0.45; cursor: not-allowed; }
@media (max-width: 980px) {
  .detail-grid { grid-template-columns: 1fr; }
}
</style>
