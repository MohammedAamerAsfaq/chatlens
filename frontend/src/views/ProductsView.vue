<template>
  <div class="products-view">
    <div class="view-header">
      <div class="header-left">
        <h2>Product Master</h2>
        <span class="count-badge">{{ products.length }} products</span>
      </div>
      <div style="display:flex;gap:8px">
        <button class="btn-ghost" @click="openBulk">Bulk Import</button>
        <button class="btn-ghost btn-inv" @click="openInventory">Update Inventory</button>
        <button class="btn-primary" @click="openCreate">+ Add Product</button>
      </div>
    </div>

    <div class="toolbar">
      <input v-model="search" class="search-input" placeholder="Search products…" />
      <label class="toggle-label">
        <input type="checkbox" v-model="showInactive" /> Show inactive
      </label>
    </div>

    <div class="table-wrap">
      <table class="data-table">
        <thead>
          <tr>
            <th>Name</th>
            <th>Brand</th>
            <th>Category</th>
            <th>Aliases</th>
            <th class="th-inv">Qty</th>
            <th class="th-inv">Cost</th>
            <th class="th-inv">Sale</th>
            <th>Active</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="filtered.length === 0">
            <td colspan="9" class="empty">No products found.</td>
          </tr>
          <tr v-for="p in filtered" :key="p.id" :class="{ inactive: !p.is_active }">
            <td class="col-name">{{ p.name }}</td>
            <td>{{ p.brand }}</td>
            <td>{{ p.category }}</td>
            <td class="col-aliases">
              <span v-for="a in p.aliases" :key="a" class="alias-chip">{{ a }}</span>
              <span v-if="!p.aliases.length" class="muted">—</span>
            </td>
            <td class="td-inv">{{ p.qty ?? 0 }}</td>
            <td class="td-inv">{{ p.cost_price != null ? p.cost_price : '—' }}</td>
            <td class="td-inv">{{ p.sale_price != null ? p.sale_price : '—' }}</td>
            <td>
              <span :class="['status-dot', p.is_active ? 'active' : 'inactive']">
                {{ p.is_active ? 'Active' : 'Inactive' }}
              </span>
            </td>
            <td class="col-actions">
              <button class="btn-sm" @click="openEdit(p)">Edit</button>
              <button v-if="p.is_active" class="btn-sm danger" @click="deactivate(p)">
                Deactivate
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Bulk Import modal -->
    <div v-if="bulk.open" class="modal-backdrop" @click.self="closeBulk">
      <div class="modal modal-wide">

        <!-- Fixed header -->
        <div class="modal-head">
          <h3>Bulk Import Products</h3>
          <div class="tab-bar">
            <button :class="['tab-btn', bulk.tab === 'structured' && 'active']"
              @click="bulk.tab = 'structured'">Structured text</button>
            <button :class="['tab-btn', bulk.tab === 'ai' && 'active']"
              @click="bulk.tab = 'ai'">AI extract (free-form)</button>
          </div>
        </div>

        <!-- Scrollable body -->
        <div class="modal-body">

          <!-- Structured tab -->
          <template v-if="bulk.tab === 'structured'">
            <div class="format-hint">
              <strong>Format:</strong> one product per line —
              <code>Name | Brand | Category</code><br />
              Brand and Category are optional. Lines starting with <code>#</code> are ignored.
              <div class="format-example">
                iPhone 17 Pro 256GB | Apple | Smartphones<br />
                iPhone 17 Pro Max 512GB | Apple | Smartphones<br />
                iPad Air 11" M4 128GB WiFi | Apple | Tablets<br />
                Samsung Galaxy S25 Ultra | Samsung | Smartphones
              </div>
            </div>
            <textarea v-model="bulk.text" class="bulk-textarea" rows="10"
              placeholder="iPhone 17 Pro 256GB | Apple | Smartphones&#10;Samsung Galaxy S25 Ultra | Samsung | Smartphones" />
          </template>

          <!-- AI extract tab -->
          <template v-else>
            <p class="ai-hint">
              Paste any price list — the AI strips colors, regions, and prices and returns unique products.
              <RouterLink to="/ai-instructions" class="edit-prompt-link" @click="closeBulk">Edit AI instructions →</RouterLink>
            </p>
            <textarea v-model="bulk.text" class="bulk-textarea" rows="10"
              placeholder="Paste your price list here…" />
          </template>

          <div v-if="bulk.error" class="bulk-error">{{ bulk.error }}</div>

          <!-- Preview table -->
          <template v-if="bulk.preview.length">
            <div class="preview-header">
              <span>{{ bulk.preview.length }} products found — review before importing:</span>
              <button class="btn-ghost btn-sm" @click="bulk.preview = []">Clear</button>
            </div>
            <table class="data-table preview-table">
              <thead>
                <tr><th>Name</th><th>Brand</th><th>Category</th><th></th></tr>
              </thead>
              <tbody>
                <tr v-for="(p, i) in bulk.preview" :key="i">
                  <td><input v-model="p.name" class="inline-input" /></td>
                  <td><input v-model="p.brand" class="inline-input" /></td>
                  <td><input v-model="p.category" class="inline-input" /></td>
                  <td><button class="btn-sm danger" @click="bulk.preview.splice(i,1)">✕</button></td>
                </tr>
              </tbody>
            </table>
          </template>

          <div v-if="bulk.result" class="bulk-result">
            ✓ {{ bulk.result.created.length }} created
            <span v-if="bulk.result.skipped.length">
              · {{ bulk.result.skipped.length }} skipped (already exist)
            </span>
          </div>

        </div><!-- /modal-body -->

        <!-- Fixed footer -->
        <div class="modal-foot">
          <span v-if="bulk.tab === 'ai' && bulk.text.trim()" class="token-pill">
            ~{{ Math.round(bulk.text.length / 4).toLocaleString() }} tokens
            <span v-if="agentPricing.input_price_per_1m">
              · ~${{ ((bulk.text.length / 4 / 1_000_000) * agentPricing.input_price_per_1m).toFixed(6) }}
            </span>
          </span>
          <span v-else class="foot-spacer" />

          <div class="foot-actions">
            <button class="btn-ghost" @click="closeBulk">Cancel</button>
            <button v-if="bulk.tab === 'structured'" class="btn-primary"
              :disabled="!bulk.text.trim()" @click="parseStructured">
              Parse
            </button>
            <button v-else-if="!bulk.preview.length" class="btn-primary"
              :disabled="bulk.extracting || !bulk.text.trim()" @click="extractWithAI">
              {{ bulk.extracting ? 'Extracting…' : 'Extract with AI' }}
            </button>
            <button v-else class="btn-primary" :disabled="bulk.importing" @click="importBulk">
              {{ bulk.importing ? 'Importing…' : `Import ${bulk.preview.length} products` }}
            </button>
          </div>
        </div>

      </div>
    </div>

    <!-- Update Inventory modal -->
    <div v-if="inv.open" class="modal-backdrop" @click.self="closeInventory">
      <div class="modal modal-wide">

        <div class="modal-head">
          <h3>Update Inventory</h3>
          <p class="inv-sub">
            Paste your lists — the AI matches products and extracts qty, cost, and sale price.
            <RouterLink to="/ai-instructions" class="edit-prompt-link" @click="closeInventory">Edit AI instructions →</RouterLink>
          </p>
          <div class="tab-bar">
            <button :class="['tab-btn', inv.step === 'input' && 'active']" @click="inv.step = 'input'">Input</button>
            <button :class="['tab-btn', inv.step === 'review' && 'active']" :disabled="!inv.preview.length" @click="inv.step = 'review'">
              Review{{ inv.preview.length ? ` (${inv.preview.length})` : '' }}
            </button>
          </div>
        </div>

        <div class="modal-body">

          <!-- Input step -->
          <template v-if="inv.step === 'input'">
            <div class="inv-grid">
              <div class="form-group">
                <label>Stock &amp; Cost list <span class="hint">— qty + purchase price per unit</span></label>
                <textarea v-model="inv.costText" class="bulk-textarea" rows="10"
                  placeholder="iPhone 17 Pro 256GB  50 units  cost 850 USD&#10;Samsung S25 Ultra 512GB  30 pcs  @780&#10;AirPods Pro 4  100  cost 180" />
              </div>
              <div class="form-group">
                <label>Sale price list <span class="hint">— selling price per unit (optional)</span></label>
                <textarea v-model="inv.saleText" class="bulk-textarea" rows="10"
                  placeholder="iPhone 17 Pro 256GB  950 USD&#10;Samsung S25 Ultra 512GB  890&#10;AirPods Pro 4  210" />
              </div>
            </div>
            <div v-if="inv.error" class="bulk-error">{{ inv.error }}</div>
          </template>

          <!-- Review step -->
          <template v-else>
            <div class="preview-header">
              <span>{{ inv.preview.length }} items — edit before applying:</span>
              <button class="btn-ghost btn-sm" @click="inv.step = 'input'">← Back</button>
            </div>
            <div class="inv-review-wrap">
              <table class="data-table preview-table">
                <thead>
                  <tr>
                    <th>Product</th>
                    <th>Matched</th>
                    <th style="width:70px">Qty</th>
                    <th style="width:90px">Cost</th>
                    <th style="width:90px">Sale</th>
                    <th style="width:70px">Currency</th>
                    <th style="width:32px"></th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(item, i) in inv.preview" :key="i" :class="{ 'row-unmatched': !item.product_id }">
                    <td>
                      <input v-model="item.canonical_name" class="inline-input" />
                    </td>
                    <td>
                      <span v-if="item.product_id" class="match-chip">ID {{ item.product_id }}</span>
                      <span v-else class="no-match-chip">unmatched</span>
                    </td>
                    <td><input v-model.number="item.qty" class="inline-input" type="number" min="0" /></td>
                    <td><input v-model.number="item.cost_price" class="inline-input" type="number" step="0.01" /></td>
                    <td><input v-model.number="item.sale_price" class="inline-input" type="number" step="0.01" /></td>
                    <td><input v-model="item.currency" class="inline-input" style="width:55px" /></td>
                    <td><button class="btn-sm danger" @click="inv.preview.splice(i, 1)">✕</button></td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div v-if="inv.result" class="bulk-result">
              ✓ {{ inv.result.updated.length }} updated
              <span v-if="inv.result.skipped.length">
                · {{ inv.result.skipped.length }} skipped (not found): {{ inv.result.skipped.join(', ') }}
              </span>
            </div>
          </template>

        </div><!-- /modal-body -->

        <div class="modal-foot">
          <span v-if="inv.step === 'input' && (inv.costText.trim() || inv.saleText.trim())" class="token-pill">
            ~{{ Math.round((inv.costText.length + inv.saleText.length) / 4).toLocaleString() }} tokens
            <span v-if="agentPricing.input_price_per_1m">
              · ~${{ (((inv.costText.length + inv.saleText.length) / 4 / 1_000_000) * agentPricing.input_price_per_1m).toFixed(6) }}
            </span>
          </span>
          <span v-else class="foot-spacer" />
          <div class="foot-actions">
            <button class="btn-ghost" @click="closeInventory">Cancel</button>
            <button v-if="inv.step === 'input'" class="btn-primary"
              :disabled="inv.parsing || (!inv.costText.trim() && !inv.saleText.trim())"
              @click="parseInventory">
              {{ inv.parsing ? 'Parsing…' : 'Parse with AI' }}
            </button>
            <button v-else class="btn-primary"
              :disabled="inv.applying || !inv.preview.length"
              @click="applyInventory">
              {{ inv.applying ? 'Applying…' : `Apply ${inv.preview.length} updates` }}
            </button>
          </div>
        </div>

      </div>
    </div>

    <!-- Create / Edit modal -->
    <div v-if="modal.open" class="modal-backdrop" @click.self="closeModal">
      <div class="modal">
        <h3>{{ modal.id ? 'Edit Product' : 'Add Product' }}</h3>

        <div class="form-group">
          <label>Name *</label>
          <input v-model="modal.name" placeholder="iPhone 17 Pro Max" />
        </div>
        <div class="form-row">
          <div class="form-group">
            <label>Brand</label>
            <input v-model="modal.brand" placeholder="Apple" />
          </div>
          <div class="form-group">
            <label>Category</label>
            <input v-model="modal.category" placeholder="Smartphones" />
          </div>
        </div>
        <details class="advanced-section">
          <summary>Advanced (optional)</summary>
          <div class="advanced-body">
            <div class="form-group">
              <label>SKU</label>
              <input v-model="modal.sku" placeholder="Internal SKU or model number" />
            </div>
            <div class="form-group">
              <label>
                Custom aliases
                <span class="hint">— only needed for internal codes the AI won't know (e.g. "SKU-4421")</span>
              </label>
              <textarea v-model="modal.aliasText" rows="2"
                placeholder="comma-separated" />
              <div class="alias-preview">
                <span v-for="a in previewAliases" :key="a" class="alias-chip">{{ a }}</span>
              </div>
            </div>
          </div>
        </details>

        <div class="modal-actions">
          <button class="btn-ghost" @click="closeModal">Cancel</button>
          <button class="btn-primary" :disabled="saving || !modal.name.trim()" @click="save">
            {{ saving ? 'Saving…' : 'Save' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import { tradingApi } from '../api/index.js'

const products    = ref([])
const search      = ref('')
const showInactive = ref(false)
const saving      = ref(false)

const modal = ref({
  open: false, id: null,
  name: '', brand: '', category: '', sku: '', aliasText: '',
})

const bulk = ref({
  open: false, tab: 'structured',
  text: '', extracting: false, importing: false,
  preview: [], error: '', result: null,
})

const agentPricing = ref({ input_price_per_1m: null })

const inv = ref({
  open: false, step: 'input',
  costText: '', saleText: '',
  parsing: false, applying: false,
  preview: [], error: '', result: null,
})

const previewAliases = computed(() =>
  modal.value.aliasText
    .split(',')
    .map(a => a.trim())
    .filter(Boolean)
)

const filtered = computed(() => {
  let list = products.value
  if (!showInactive.value) list = list.filter(p => p.is_active)
  if (search.value.trim()) {
    const q = search.value.toLowerCase()
    list = list.filter(p =>
      p.name.toLowerCase().includes(q) ||
      p.brand.toLowerCase().includes(q) ||
      p.aliases.some(a => a.toLowerCase().includes(q))
    )
  }
  return list
})

async function load() {
  const { data } = await tradingApi.listProducts({ active: 'all' })
  products.value = data
}

function openCreate() {
  modal.value = { open: true, id: null, name: '', brand: '', category: '', sku: '', aliasText: '' }
}

function openEdit(p) {
  modal.value = {
    open: true, id: p.id,
    name: p.name, brand: p.brand, category: p.category, sku: p.sku,
    aliasText: p.aliases.join(', '),
  }
}

function closeModal() {
  modal.value.open = false
}

async function save() {
  if (!modal.value.name.trim()) return
  saving.value = true
  try {
    const payload = {
      name:      modal.value.name.trim(),
      brand:     modal.value.brand.trim(),
      category:  modal.value.category.trim(),
      sku:       modal.value.sku.trim(),
      aliases:   previewAliases.value,
      is_active: true,
    }
    if (modal.value.id) {
      await tradingApi.updateProduct(modal.value.id, payload)
    } else {
      await tradingApi.createProduct(payload)
    }
    closeModal()
    await load()
  } finally {
    saving.value = false
  }
}

async function openBulk() {
  bulk.value = { open: true, tab: 'structured', text: '', extracting: false, importing: false, preview: [], error: '', result: null }
  tradingApi.getActiveAgent().then(r => { agentPricing.value = r.data }).catch(() => {})
}

function closeBulk() {
  bulk.value.open = false
}

function parseStructured() {
  bulk.value.error = ''
  bulk.value.preview = []
  const lines = bulk.value.text.split('\n')
  const parsed = []
  for (const raw of lines) {
    const line = raw.trim()
    if (!line || line.startsWith('#')) continue
    const [name = '', brand = '', category = ''] = line.split('|').map(s => s.trim())
    if (name) parsed.push({ name, brand, category })
  }
  if (!parsed.length) {
    bulk.value.error = 'No valid lines found. Use format: Name | Brand | Category'
    return
  }
  bulk.value.preview = parsed
}

async function extractWithAI() {
  bulk.value.error = ''
  bulk.value.preview = []
  bulk.value.extracting = true
  try {
    const { data } = await tradingApi.parseProductText(bulk.value.text)
    if (data.error) throw new Error(data.error)
    bulk.value.preview = data.products.map(p => ({
      name: p.name || '',
      brand: p.brand || '',
      category: p.category || '',
    }))
  } catch (e) {
    bulk.value.error = e.response?.data?.error || e.message || 'AI extraction failed'
  } finally {
    bulk.value.extracting = false
  }
}

async function importBulk() {
  bulk.value.importing = true
  bulk.value.result = null
  try {
    const { data } = await tradingApi.bulkCreateProducts(bulk.value.preview)
    bulk.value.result = data
    bulk.value.preview = []
    await load()
  } finally {
    bulk.value.importing = false
  }
}

function openInventory() {
  inv.value = { open: true, step: 'input', costText: '', saleText: '', parsing: false, applying: false, preview: [], error: '', result: null }
  tradingApi.getActiveAgent().then(r => { agentPricing.value = r.data }).catch(() => {})
}

function closeInventory() {
  inv.value.open = false
}

async function parseInventory() {
  inv.value.error = ''
  inv.value.parsing = true
  try {
    const { data } = await tradingApi.parseInventory(inv.value.costText, inv.value.saleText)
    if (data.error) throw new Error(data.error)
    inv.value.preview = data.items.map(item => ({
      product_id:    item.product_id   ?? null,
      canonical_name: item.canonical_name || '',
      qty:           item.qty           ?? null,
      cost_price:    item.cost_price    ?? null,
      sale_price:    item.sale_price    ?? null,
      currency:      item.currency      || 'USD',
    }))
    inv.value.step = 'review'
  } catch (e) {
    inv.value.error = e.response?.data?.error || e.message || 'AI parsing failed'
  } finally {
    inv.value.parsing = false
  }
}

async function applyInventory() {
  inv.value.applying = true
  inv.value.result = null
  try {
    const { data } = await tradingApi.bulkUpdateInventory(inv.value.preview)
    inv.value.result = data
    inv.value.preview = []
    await load()
  } finally {
    inv.value.applying = false
  }
}

async function deactivate(p) {
  if (!confirm(`Deactivate "${p.name}"? It will no longer appear in AI classification.`)) return
  await tradingApi.updateProduct(p.id, { is_active: false })
  await load()
}

onMounted(load)
</script>

<style scoped>
.products-view { display: flex; flex-direction: column; height: 100%; padding: 20px; gap: 14px; }
.view-header { display: flex; align-items: center; justify-content: space-between; }
.header-left { display: flex; align-items: center; gap: 10px; }
.header-left h2 { margin: 0; font-size: 1.2rem; }
.count-badge { background: #e5e7eb; border-radius: 999px; padding: 2px 10px; font-size: 0.8rem; }
.toolbar { display: flex; gap: 12px; align-items: center; }
.search-input { flex: 1; padding: 7px 12px; border: 1px solid #d1d5db; border-radius: 6px; font-size: 0.9rem; }
.toggle-label { font-size: 0.88rem; display: flex; gap: 6px; align-items: center; cursor: pointer; }
.table-wrap { flex: 1; overflow-y: auto; border: 1px solid #e5e7eb; border-radius: 8px; }
.data-table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
.data-table th { background: #f9fafb; padding: 10px 14px; text-align: left; font-size: 0.8rem; color: #6b7280; border-bottom: 1px solid #e5e7eb; }
.data-table td { padding: 10px 14px; border-bottom: 1px solid #f3f4f6; vertical-align: top; }
.data-table tr:last-child td { border-bottom: none; }
.data-table tr.inactive { opacity: 0.5; }
.col-name { font-weight: 500; }
.col-aliases { display: flex; flex-wrap: wrap; gap: 4px; }
.alias-chip { background: #eff6ff; color: #1d4ed8; border-radius: 4px; padding: 1px 7px; font-size: 0.78rem; }
.col-actions { display: flex; gap: 6px; white-space: nowrap; }
.status-dot { font-size: 0.8rem; font-weight: 500; }
.status-dot.active { color: #16a34a; }
.status-dot.inactive { color: #9ca3af; }
.empty { text-align: center; color: #9ca3af; padding: 40px; }
.muted { color: #9ca3af; }
.btn-primary { padding: 7px 16px; background: #2563eb; color: #fff; border: none; border-radius: 6px; cursor: pointer; font-size: 0.9rem; }
.btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-ghost { padding: 7px 16px; background: transparent; border: 1px solid #d1d5db; border-radius: 6px; cursor: pointer; font-size: 0.9rem; }
.btn-sm { padding: 4px 10px; border: 1px solid #d1d5db; border-radius: 5px; background: #fff; cursor: pointer; font-size: 0.8rem; }
.btn-sm.danger { border-color: #fca5a5; color: #dc2626; }
.modal-backdrop { position: fixed; inset: 0; background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; z-index: 100; padding: 20px; }
.modal { background: #fff; border-radius: 10px; width: 520px; max-width: 100%; max-height: 90vh; display: flex; flex-direction: column; overflow: hidden; }
.modal h3 { margin: 0; font-size: 1.1rem; }
.modal-head { padding: 20px 24px 0; display: flex; flex-direction: column; gap: 12px; flex-shrink: 0; }
.modal-body { flex: 1; overflow-y: auto; padding: 16px 24px; display: flex; flex-direction: column; gap: 12px; }
.modal-foot { padding: 14px 24px; border-top: 1px solid #e5e7eb; display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-shrink: 0; background: #fff; }
.foot-spacer { flex: 1; }
.foot-actions { display: flex; gap: 8px; }
.form-group { display: flex; flex-direction: column; gap: 4px; }
.form-group label { font-size: 0.83rem; color: #374151; font-weight: 500; }
.form-group input, .form-group textarea { padding: 7px 10px; border: 1px solid #d1d5db; border-radius: 6px; font-size: 0.9rem; }
.form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.hint { font-weight: 400; color: #6b7280; }
.alias-preview { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 4px; min-height: 20px; }
.modal-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 4px; }
.preview-table { width: 100%; border-collapse: collapse; border: 1px solid #e5e7eb; border-radius: 6px; overflow: hidden; }
.modal-wide { width: 700px; }
.tab-bar { display: flex; gap: 0; border: 1px solid #e5e7eb; border-radius: 6px; overflow: hidden; }
.tab-btn { flex: 1; padding: 7px; background: #f9fafb; border: none; cursor: pointer; font-size: 0.85rem; color: #6b7280; }
.tab-btn.active { background: #2563eb; color: #fff; font-weight: 500; }
.format-hint { font-size: 0.83rem; color: #374151; background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 6px; padding: 10px 14px; line-height: 1.6; }
.format-example { margin-top: 8px; background: #fff; border: 1px solid #e5e7eb; border-radius: 4px; padding: 8px 10px; font-family: monospace; font-size: 0.8rem; color: #374151; white-space: pre; }
.ai-hint { font-size: 0.85rem; color: #6b7280; margin: 0; display: flex; gap: 12px; align-items: baseline; flex-wrap: wrap; }
.edit-prompt-link { color: #2563eb; text-decoration: none; white-space: nowrap; }
.edit-prompt-link:hover { text-decoration: underline; }
.extract-footer { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.token-pill { font-size: 0.8rem; font-family: monospace; background: #f3f4f6; color: #374151; padding: 4px 12px; border-radius: 20px; }
.bulk-textarea { width: 100%; padding: 8px 10px; border: 1px solid #d1d5db; border-radius: 6px; font-size: 0.85rem; font-family: monospace; resize: vertical; box-sizing: border-box; }
.bulk-error { color: #dc2626; font-size: 0.85rem; }
.bulk-result { color: #16a34a; font-size: 0.85rem; }
.preview-header { display: flex; justify-content: space-between; align-items: center; font-size: 0.85rem; color: #374151; }
.preview-table-wrap { max-height: 240px; overflow-y: auto; border: 1px solid #e5e7eb; border-radius: 6px; }
.inline-input { width: 100%; border: none; background: transparent; font-size: 0.85rem; padding: 2px 4px; outline: none; }
.inline-input:focus { background: #eff6ff; border-radius: 3px; }
.prompt-details { border: 1px solid #e5e7eb; border-radius: 6px; font-size: 0.83rem; }
.prompt-details summary { padding: 7px 12px; cursor: pointer; color: #6b7280; user-select: none; }
.prompt-details summary:hover { color: #374151; }
.prompt-pre { margin: 0; padding: 10px 14px; background: #f9fafb; border-top: 1px solid #e5e7eb; font-family: monospace; font-size: 0.8rem; white-space: pre-wrap; color: #374151; border-radius: 0 0 6px 6px; }
.prompt-editable { width: 100%; resize: vertical; border: none; outline: none; box-sizing: border-box; line-height: 1.5; }
.advanced-section { border: 1px solid #e5e7eb; border-radius: 6px; padding: 0; }
.advanced-section summary { padding: 8px 12px; font-size: 0.83rem; color: #6b7280; cursor: pointer; user-select: none; }
.advanced-section summary:hover { color: #374151; }
.advanced-body { display: flex; flex-direction: column; gap: 12px; padding: 12px; border-top: 1px solid #e5e7eb; }
/* Inventory */
.btn-inv { border-color: #6366f1; color: #4f46e5; }
.btn-inv:hover { background: #eef2ff; }
.th-inv, .td-inv { text-align: right; font-variant-numeric: tabular-nums; color: #374151; }
.th-inv { font-size: 0.78rem; }
.inv-sub { margin: 0; font-size: 0.84rem; color: #6b7280; display: flex; gap: 12px; align-items: baseline; }
.inv-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.inv-review-wrap { overflow-x: auto; }
.match-chip { background: #dcfce7; color: #15803d; padding: 1px 7px; border-radius: 4px; font-size: 0.75rem; font-weight: 600; }
.no-match-chip { background: #fef9c3; color: #92400e; padding: 1px 7px; border-radius: 4px; font-size: 0.75rem; }
.row-unmatched td:first-child { color: #92400e; }

</style>
