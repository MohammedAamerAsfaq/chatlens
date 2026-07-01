<template>
  <div class="ai-instructions">
    <div class="page-header">
      <div>
        <h2>AI Instructions</h2>
        <p class="subtitle">Prompts sent verbatim to the AI. Edit and save to change behaviour globally.</p>
      </div>
      <div class="page-tabs">
        <button :class="['page-tab', tab === 'prompts' && 'active']" @click="tab = 'prompts'">Prompts</button>
        <button :class="['page-tab', tab === 'logs'    && 'active']" @click="switchToLogs">Logs</button>
      </div>
    </div>

    <!-- ── PROMPTS TAB ─────────────────────────────────────────────────── -->
    <template v-if="tab === 'prompts'">

      <!-- Active agent card -->
      <div class="agent-card">
        <div class="agent-header">
          <div class="agent-title">
            <span class="agent-dot" />
            <span class="agent-name">{{ agent.display_name || '—' }}</span>
            <span class="agent-model">{{ agent.model }}</span>
            <span class="agent-provider">{{ agent.provider }}</span>
          </div>
          <span class="agent-label">Active agent</span>
        </div>
        <div class="pricing-row">
          <div class="price-field">
            <label>Input price (USD / 1M tokens)</label>
            <input v-model.number="agent.input_price_per_1m" type="number" step="0.01" min="0"
              placeholder="e.g. 0.15" @change="savePricing" />
          </div>
          <div class="price-field">
            <label>Output price (USD / 1M tokens)</label>
            <input v-model.number="agent.output_price_per_1m" type="number" step="0.01" min="0"
              placeholder="e.g. 0.60" @change="savePricing" />
          </div>
          <div class="price-field">
            <label>Token approximation</label>
            <div class="price-info">chars ÷ 4 &nbsp;·&nbsp; ±10% accuracy</div>
          </div>
          <div v-if="pricingSaved" class="pricing-ok">Saved.</div>
        </div>
      </div>

      <div v-if="promptsLoading" class="loading">Loading…</div>
      <div v-else class="prompt-list">
        <div v-for="p in prompts" :key="p.key" class="prompt-card">
          <div class="card-header">
            <div class="card-title-row">
              <span class="card-label">{{ p.label }}</span>
              <span class="key-badge">{{ p.key }}</span>
              <span v-if="p.is_default" class="default-badge">default</span>
              <span v-else class="saved-badge">saved {{ formatDate(p.updated_at) }}</span>
            </div>
            <div class="card-actions">
              <button class="btn-ghost btn-sm" :disabled="p.is_default" @click="reset(p)">Reset to default</button>
              <button class="btn-primary btn-sm" :disabled="saving[p.key]" @click="save(p)">
                {{ saving[p.key] ? 'Saving…' : 'Save' }}
              </button>
            </div>
          </div>
          <div class="meta-row">
            <span class="meta-note" v-if="p.key === 'inquiry_classification'">
              Used for every live inbound message · supports <code>{product_block}</code> placeholder
            </span>
            <span class="meta-note" v-if="p.key === 'product_extraction'">
              Used in Bulk Import → AI Extract · must return a raw JSON array
            </span>
            <span class="meta-note" v-if="p.key === 'inventory_update'">
              Used in Products → Update Inventory · supports <code>{product_block}</code> placeholder · must return a raw JSON array
            </span>
            <span class="token-estimate">
              ~{{ tokenCount(p.body).toLocaleString() }} tokens
              <span v-if="inputCost(p.body) !== null" class="cost-estimate">· ~${{ inputCost(p.body) }} input</span>
              <span v-else class="cost-na">· set price above to see cost</span>
            </span>
          </div>
          <textarea v-model="p.body" class="prompt-editor"
            :rows="p.key === 'inquiry_classification' ? 28 : 18" spellcheck="false" />
          <div v-if="errors[p.key]" class="card-error">{{ errors[p.key] }}</div>
          <div v-if="saved[p.key]"  class="card-ok">Saved.</div>
        </div>
      </div>

    </template>

    <!-- ── LOGS TAB ────────────────────────────────────────────────────── -->
    <template v-else>
      <div class="log-toolbar">
        <div class="filter-group">
          <select v-model="logFilter.purpose" @change="loadLogs">
            <option value="">All purposes</option>
            <option value="classification">Inquiry Classification</option>
            <option value="product_extraction">Product Extraction</option>
            <option value="inventory_update">Inventory Update</option>
          </select>
          <select v-model="logFilter.success" @change="loadLogs">
            <option value="">All statuses</option>
            <option value="true">Success</option>
            <option value="false">Failed</option>
          </select>
        </div>
        <button class="btn-ghost btn-sm" @click="loadLogs">↺ Refresh</button>
      </div>

      <div v-if="logsLoading" class="loading">Loading…</div>

      <div v-else-if="!logs.length" class="empty-logs">No agent calls logged yet.</div>

      <div v-else class="log-list">
        <div v-for="log in logs" :key="log.id"
          class="log-row" :class="{ failed: !log.success }"
          @click="toggle(log.id)">

          <!-- Summary row -->
          <div class="log-summary">
            <span class="log-time">{{ formatDate(log.created_at) }}</span>
            <span :class="['purpose-badge', log.purpose]">{{ purposeLabel(log.purpose) }}</span>
            <span class="log-model">{{ log.model }}</span>
            <div class="log-stats">
              <span class="stat">↑ {{ log.input_tokens.toLocaleString() }} tok</span>
              <span class="stat">↓ {{ log.output_tokens.toLocaleString() }} tok</span>
              <span v-if="log.input_cost !== null" class="stat cost">
                ${{ (log.input_cost + (log.output_cost || 0)).toFixed(6) }}
              </span>
              <span class="stat dur">{{ log.duration_ms }}ms</span>
            </div>
            <span v-if="!log.success" class="err-badge">ERROR</span>
            <span class="chevron">{{ expanded.has(log.id) ? '▲' : '▼' }}</span>
          </div>

          <!-- Expanded detail -->
          <div v-if="expanded.has(log.id)" class="log-detail" @click.stop>
            <div v-if="log.error" class="detail-error">{{ log.error }}</div>

            <div class="detail-section">
              <div class="detail-label">Messages sent</div>
              <div v-for="(m, i) in log.messages" :key="i" class="message-block">
                <span class="role-badge" :class="m.role">{{ m.role }}</span>
                <pre class="message-content">{{ m.content }}</pre>
              </div>
            </div>

            <div class="detail-section" v-if="log.response">
              <div class="detail-label">Response received</div>
              <pre class="message-content response">{{ log.response }}</pre>
            </div>

            <div class="detail-meta">
              Provider: {{ log.provider }} · Model: {{ log.model }}
              <span v-if="log.wa_message_id"> · WA message #{{ log.wa_message_id }}</span>
            </div>
          </div>

        </div>
      </div>
    </template>

  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { tradingApi } from '../api/index.js'

const tab = ref('prompts')

// ── Prompts ────────────────────────────────────────────────────────────────
const prompts      = ref([])
const promptsLoading = ref(true)
const saving       = ref({})
const saved        = ref({})
const errors       = ref({})
const pricingSaved = ref(false)

const agent = ref({ display_name: '', provider: '', model: '', input_price_per_1m: null, output_price_per_1m: null })

function tokenCount(text) { return Math.round((text || '').length / 4) }

function inputCost(text) {
  const price = agent.value.input_price_per_1m
  if (price === null || price === undefined || price === '') return null
  return ((tokenCount(text) / 1_000_000) * price).toFixed(6)
}

async function loadPrompts() {
  promptsLoading.value = true
  try {
    const [pr, ar] = await Promise.all([
      tradingApi.listPrompts(),
      tradingApi.getActiveAgent().catch(() => ({ data: {} })),
    ])
    prompts.value = pr.data
    Object.assign(agent.value, ar.data)
  } finally {
    promptsLoading.value = false
  }
}

async function save(p) {
  saving.value[p.key] = true
  saved.value[p.key]  = false
  errors.value[p.key] = ''
  try {
    const { data } = await tradingApi.savePrompt(p.key, p.body)
    const idx = prompts.value.findIndex(x => x.key === p.key)
    if (idx !== -1) prompts.value[idx] = data
    saved.value[p.key] = true
    setTimeout(() => { saved.value[p.key] = false }, 2500)
  } catch (e) {
    errors.value[p.key] = e.response?.data?.error || 'Save failed'
  } finally {
    saving.value[p.key] = false
  }
}

async function reset(p) {
  if (!confirm(`Reset "${p.label}" to the built-in default?`)) return
  await tradingApi.resetPrompt(p.key)
  await loadPrompts()
}

async function savePricing() {
  pricingSaved.value = false
  await tradingApi.saveAgentPricing({
    input_price_per_1m:  agent.value.input_price_per_1m,
    output_price_per_1m: agent.value.output_price_per_1m,
  })
  pricingSaved.value = true
  setTimeout(() => { pricingSaved.value = false }, 2000)
}

// ── Logs ───────────────────────────────────────────────────────────────────
const logs       = ref([])
const logsLoading = ref(false)
const expanded   = ref(new Set())
const logFilter  = ref({ purpose: '', success: '' })

async function loadLogs() {
  logsLoading.value = true
  expanded.value = new Set()
  try {
    const params = {}
    if (logFilter.value.purpose) params.purpose = logFilter.value.purpose
    if (logFilter.value.success) params.success = logFilter.value.success
    const { data } = await tradingApi.listAgentLogs(params)
    logs.value = data
  } finally {
    logsLoading.value = false
  }
}

function switchToLogs() {
  tab.value = 'logs'
  if (!logs.value.length) loadLogs()
}

function toggle(id) {
  if (expanded.value.has(id)) expanded.value.delete(id)
  else expanded.value.add(id)
  expanded.value = new Set(expanded.value)
}

function purposeLabel(p) {
  if (p === 'classification')   return 'Classification'
  if (p === 'inventory_update') return 'Inventory Update'
  return 'Product Extract'
}

// ── Shared ─────────────────────────────────────────────────────────────────
function formatDate(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

onMounted(loadPrompts)
</script>

<style scoped>
.ai-instructions { display: flex; flex-direction: column; height: 100%; padding: 24px; gap: 20px; overflow-y: auto; }
.page-header { display: flex; align-items: flex-start; justify-content: space-between; }
.page-header h2 { margin: 0 0 4px; font-size: 1.2rem; }
.subtitle { margin: 0; font-size: 0.85rem; color: #6b7280; }
.page-tabs { display: flex; border: 1px solid #e5e7eb; border-radius: 8px; overflow: hidden; }
.page-tab { padding: 6px 20px; background: #f9fafb; border: none; cursor: pointer; font-size: 0.88rem; color: #6b7280; }
.page-tab.active { background: #1d4ed8; color: #fff; font-weight: 500; }
.loading { color: #9ca3af; font-size: 0.9rem; }

/* Agent card */
.agent-card { border: 1px solid #d1fae5; background: #f0fdf4; border-radius: 10px; padding: 16px 20px; display: flex; flex-direction: column; gap: 12px; }
.agent-header { display: flex; align-items: center; justify-content: space-between; }
.agent-title { display: flex; align-items: center; gap: 8px; }
.agent-dot { width: 8px; height: 8px; border-radius: 50%; background: #16a34a; flex-shrink: 0; }
.agent-name { font-weight: 600; font-size: 0.95rem; }
.agent-model { font-family: monospace; font-size: 0.8rem; background: #dcfce7; color: #166534; padding: 2px 8px; border-radius: 4px; }
.agent-provider { font-size: 0.78rem; color: #6b7280; }
.agent-label { font-size: 0.75rem; color: #6b7280; text-transform: uppercase; letter-spacing: 0.05em; }
.pricing-row { display: flex; gap: 16px; align-items: flex-end; flex-wrap: wrap; }
.price-field { display: flex; flex-direction: column; gap: 4px; }
.price-field label { font-size: 0.78rem; color: #374151; font-weight: 500; }
.price-field input { padding: 5px 9px; border: 1px solid #d1d5db; border-radius: 6px; font-size: 0.85rem; width: 180px; background: #fff; }
.price-info { padding: 5px 9px; font-size: 0.82rem; color: #6b7280; border: 1px solid #e5e7eb; border-radius: 6px; background: #fff; }
.pricing-ok { font-size: 0.82rem; color: #16a34a; align-self: flex-end; padding-bottom: 6px; }

/* Prompt cards */
.prompt-list { display: flex; flex-direction: column; gap: 24px; }
.prompt-card { border: 1px solid #e5e7eb; border-radius: 10px; padding: 20px; display: flex; flex-direction: column; gap: 10px; background: #fff; }
.card-header { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.card-title-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.card-label { font-weight: 600; font-size: 1rem; }
.key-badge { background: #f3f4f6; color: #374151; font-family: monospace; font-size: 0.75rem; padding: 2px 8px; border-radius: 4px; }
.default-badge { background: #fef9c3; color: #854d0e; font-size: 0.75rem; padding: 2px 8px; border-radius: 4px; }
.saved-badge { background: #dcfce7; color: #166534; font-size: 0.75rem; padding: 2px 8px; border-radius: 4px; }
.card-actions { display: flex; gap: 8px; }
.meta-row { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px; }
.meta-note { font-size: 0.8rem; color: #6b7280; }
.meta-note code { background: #f3f4f6; padding: 1px 5px; border-radius: 3px; font-size: 0.78rem; }
.token-estimate { font-size: 0.8rem; font-family: monospace; background: #f3f4f6; color: #374151; padding: 2px 10px; border-radius: 20px; white-space: nowrap; }
.cost-estimate { color: #2563eb; font-weight: 500; }
.cost-na { color: #9ca3af; }
.prompt-editor { width: 100%; padding: 12px 14px; border: 1px solid #d1d5db; border-radius: 6px; font-family: 'Cascadia Code', 'Fira Code', 'Consolas', monospace; font-size: 0.82rem; line-height: 1.6; resize: vertical; box-sizing: border-box; color: #1f2937; background: #fafafa; }
.prompt-editor:focus { outline: none; border-color: #2563eb; background: #fff; }
.card-error { color: #dc2626; font-size: 0.85rem; }
.card-ok { color: #16a34a; font-size: 0.85rem; }

/* Logs */
.log-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.filter-group { display: flex; gap: 8px; }
.filter-group select { padding: 6px 10px; border: 1px solid #d1d5db; border-radius: 6px; font-size: 0.85rem; background: #fff; }
.empty-logs { color: #9ca3af; font-size: 0.9rem; padding: 40px; text-align: center; }
.log-list { display: flex; flex-direction: column; gap: 6px; }
.log-row { border: 1px solid #e5e7eb; border-radius: 8px; background: #fff; overflow: hidden; cursor: pointer; }
.log-row:hover { border-color: #d1d5db; }
.log-row.failed { border-color: #fecaca; background: #fff5f5; }
.log-summary { display: flex; align-items: center; gap: 10px; padding: 10px 14px; flex-wrap: wrap; }
.log-time { font-size: 0.78rem; color: #6b7280; white-space: nowrap; min-width: 130px; }
.purpose-badge { font-size: 0.75rem; font-weight: 500; padding: 2px 8px; border-radius: 4px; white-space: nowrap; }
.purpose-badge.classification { background: #ede9fe; color: #5b21b6; }
.purpose-badge.product_extraction { background: #dbeafe; color: #1d4ed8; }
.purpose-badge.inventory_update { background: #fef3c7; color: #92400e; }
.log-model { font-family: monospace; font-size: 0.78rem; color: #374151; }
.log-stats { display: flex; gap: 8px; margin-left: auto; flex-wrap: wrap; }
.stat { font-size: 0.78rem; color: #6b7280; font-family: monospace; }
.stat.cost { color: #2563eb; font-weight: 500; }
.stat.dur { color: #9ca3af; }
.err-badge { background: #fecaca; color: #991b1b; font-size: 0.72rem; font-weight: 600; padding: 2px 6px; border-radius: 4px; }
.chevron { font-size: 0.7rem; color: #9ca3af; margin-left: 4px; }

/* Log detail */
.log-detail { border-top: 1px solid #e5e7eb; padding: 16px; display: flex; flex-direction: column; gap: 14px; cursor: default; background: #fafafa; }
.detail-error { background: #fee2e2; color: #991b1b; padding: 8px 12px; border-radius: 6px; font-size: 0.85rem; font-family: monospace; }
.detail-section { display: flex; flex-direction: column; gap: 8px; }
.detail-label { font-size: 0.75rem; font-weight: 600; color: #6b7280; text-transform: uppercase; letter-spacing: 0.05em; }
.message-block { display: flex; flex-direction: column; gap: 4px; }
.role-badge { font-size: 0.72rem; font-weight: 600; padding: 1px 7px; border-radius: 4px; align-self: flex-start; text-transform: uppercase; }
.role-badge.system { background: #f3f4f6; color: #374151; }
.role-badge.user { background: #dbeafe; color: #1d4ed8; }
.role-badge.assistant { background: #dcfce7; color: #166534; }
.message-content { margin: 0; padding: 10px 12px; background: #fff; border: 1px solid #e5e7eb; border-radius: 6px; font-family: 'Cascadia Code', 'Consolas', monospace; font-size: 0.78rem; line-height: 1.6; white-space: pre-wrap; overflow-x: auto; max-height: 400px; overflow-y: auto; }
.message-content.response { background: #f0fdf4; border-color: #bbf7d0; }
.detail-meta { font-size: 0.78rem; color: #9ca3af; }

/* Shared buttons */
.btn-primary { padding: 6px 14px; background: #2563eb; color: #fff; border: none; border-radius: 6px; cursor: pointer; font-size: 0.85rem; }
.btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-ghost { padding: 6px 14px; background: transparent; border: 1px solid #d1d5db; border-radius: 6px; cursor: pointer; font-size: 0.85rem; color: #374151; }
.btn-ghost:disabled { opacity: 0.4; cursor: not-allowed; }
.btn-sm { padding: 5px 12px; font-size: 0.8rem; }
</style>
