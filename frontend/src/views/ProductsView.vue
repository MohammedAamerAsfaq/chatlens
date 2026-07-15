<template>
  <div class="products-view">
    <div class="view-header">
      <div class="header-left">
        <h2>Product Master</h2>
        <span class="count-badge">{{ products.length }} products</span>
        <span class="pnl-badge" :class="totalPnl < 0 ? 'negative' : 'positive'">
          Total PNL: {{ formatMoney(totalPnl) }}
        </span>
        <span
          v-if="embeddingStatus"
          class="embed-badge"
          :class="{ warn: embeddingMissing > 0 }"
          :title="`Products: ${embeddingStatus.products.embedded}/${embeddingStatus.products.total} · Aliases: ${embeddingStatus.aliases.embedded}/${embeddingStatus.aliases.total}`"
        >
          Embeddings: {{ embeddingStatus.products.embedded + embeddingStatus.aliases.embedded }}/{{ embeddingStatus.products.total + embeddingStatus.aliases.total }}
        </span>
        <button
          v-if="embeddingMissing > 0"
          class="backfill-btn"
          :disabled="backfilling"
          @click="runBackfillEmbeddings"
        >{{ backfilling ? 'Backfilling…' : `Backfill (${embeddingMissing})` }}</button>
      </div>
      <div style="display:flex;gap:8px">
        <button class="btn-ghost" @click="openBulk">Bulk Import</button>
        <button class="btn-ghost btn-inv" @click="openInventory">Update Inventory</button>
        <button class="btn-ghost" @click="openPriceList">Price List</button>
        <button class="btn-primary" @click="openCreate">+ Add Product</button>
      </div>
    </div>

    <div class="toolbar">
      <input v-model="search" class="search-input" placeholder="Search products…" />
      <label class="toggle-label">
        <input type="checkbox" v-model="showInactive" /> Show inactive
      </label>
    </div>

    <!-- Smart Search — embedding-based, separate from the plain filter above. Handles
         out-of-order/rephrased queries ("Orange 256GB 17 Pro") that a substring match
         can't, by comparing against every product's own name AND alias embeddings. -->
    <div class="smart-search-box">
      <div class="smart-search-row">
        <span class="smart-search-icon">✦</span>
        <input
          v-model="smartQuery"
          class="search-input"
          placeholder="Smart Search — any word order or phrasing (e.g. &quot;Orange 256GB 17 Pro&quot;)…"
          @keydown.enter="runSmartSearch"
        />
        <button class="btn-primary sm" :disabled="smartSearching || !smartQuery.trim()" @click="runSmartSearch">
          {{ smartSearching ? 'Searching…' : 'Smart Search' }}
        </button>
        <button v-if="smartSearched" class="btn-ghost sm" @click="clearSmartSearch">Clear</button>
      </div>

      <div v-if="smartError" class="bulk-error">{{ smartError }}</div>

      <div v-if="smartSearched" class="smart-results">
        <div v-if="!smartResults.length" class="empty-msg-sm">No matches found</div>
        <table v-else class="data-table smart-results-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Brand</th>
              <th>Match</th>
              <th class="th-inv">Qty</th>
              <th class="th-inv">Sale</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in smartResults" :key="r.product.id">
              <td class="col-name">{{ r.product.name }}</td>
              <td>{{ r.product.brand }}</td>
              <td>
                <span class="match-badge">~{{ Math.round((1 - r.distance) * 100) }}% match</span>
              </td>
              <td class="td-inv">{{ r.product.qty ?? 0 }}</td>
              <td class="td-inv">{{ r.product.sale_price != null ? r.product.sale_price : '—' }}</td>
              <td><button class="btn-sm" @click="openEdit(r.product)">Edit</button></td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div class="table-wrap">
      <table class="data-table">
        <thead>
          <tr>
            <th>Name</th>
            <th>Brand</th>
            <th>Category</th>
            <th class="th-inv">Qty</th>
            <th class="th-inv">Cost</th>
            <th class="th-inv">Sale</th>
            <th class="th-inv">Margin</th>
            <th>Active</th>
            <th class="th-embed" title="Whether this product's own name+brand embedding exists">Product Embedding</th>
            <th class="th-embed" title="Whether this product's aliases each have their own embedding">Alias Embeddings</th>
            <th class="th-embed" title="Number of hot-added key/value attributes on this product">Attributes</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="filtered.length === 0">
            <td colspan="12" class="empty">No products found.</td>
          </tr>
          <tr v-for="p in filtered" :key="p.id" :class="{ inactive: !p.is_active }">
            <td class="col-name">{{ p.name }}</td>
            <td>{{ p.brand }}</td>
            <td>{{ p.category }}</td>
            <td class="td-inv" @click="startCellEdit(p, 'qty')">
              <input
                v-if="isEditingCell(p, 'qty')"
                v-model="editCellValue"
                type="number" min="0" step="1"
                class="inline-cell-input"
                autofocus
                @click.stop
                @keydown="handleCellKeydown($event, p, 'qty')"
                @blur="saveCellEdit(p, 'qty')"
              />
              <span v-else class="editable-cell">{{ p.qty ?? 0 }}</span>
            </td>
            <td class="td-inv" @click="startCellEdit(p, 'cost_price')">
              <input
                v-if="isEditingCell(p, 'cost_price')"
                v-model="editCellValue"
                type="number" step="0.01"
                class="inline-cell-input"
                autofocus
                @click.stop
                @keydown="handleCellKeydown($event, p, 'cost_price')"
                @blur="saveCellEdit(p, 'cost_price')"
              />
              <span v-else class="editable-cell">{{ p.cost_price != null ? p.cost_price : '—' }}</span>
            </td>
            <td class="td-inv" @click="startCellEdit(p, 'sale_price')">
              <input
                v-if="isEditingCell(p, 'sale_price')"
                v-model="editCellValue"
                type="number" step="0.01"
                class="inline-cell-input"
                autofocus
                @click.stop
                @keydown="handleCellKeydown($event, p, 'sale_price')"
                @blur="saveCellEdit(p, 'sale_price')"
              />
              <span v-else class="editable-cell">{{ p.sale_price != null ? p.sale_price : '—' }}</span>
            </td>
            <td class="td-inv">
              <span v-if="margin(p) != null" :class="margin(p) < 0 ? 'neg' : 'pos'">{{ formatMoney(margin(p)) }}</span>
              <span v-else class="muted">—</span>
            </td>
            <td>
              <span :class="['status-dot', p.is_active ? 'active' : 'inactive']">
                {{ p.is_active ? 'Active' : 'Inactive' }}
              </span>
            </td>
            <td class="th-embed">
              <span :class="['embed-dot', p.has_embedding ? 'yes' : 'no']">{{ p.has_embedding ? '✓' : '✗' }}</span>
            </td>
            <td class="th-embed">
              <span v-if="!p.alias_embedding_status?.total" class="muted">—</span>
              <span
                v-else
                class="embed-dot"
                :class="p.alias_embedding_status.embedded === p.alias_embedding_status.total ? 'yes' : 'partial'"
              >{{ p.alias_embedding_status.embedded }}/{{ p.alias_embedding_status.total }}</span>
            </td>
            <td class="th-embed">
              <span v-if="!p.attributes?.length" class="muted">—</span>
              <span v-else class="embed-dot yes">{{ p.attributes.length }}</span>
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

    <!-- Price List modal -->
    <div v-if="priceList.open" class="modal-backdrop" @click.self="closePriceList">
      <div class="modal modal-wide">
        <div class="modal-head">
          <h3>Price List (WhatsApp)</h3>
          <p class="inv-sub">
            AI-formatted from current in-stock, priced products — this exact text is sent when the
            "Price List" button is clicked on an inquiry.
            <RouterLink to="/ai-instructions" class="edit-prompt-link" @click="closePriceList">Edit AI instructions →</RouterLink>
          </p>
        </div>
        <div class="modal-body">
          <div v-if="priceList.error" class="bulk-error">{{ priceList.error }}</div>
          <div v-if="priceList.generatedAt" class="price-list-meta">
            Last generated {{ formatDateTime(priceList.generatedAt) }}
          </div>
          <textarea
            v-model="priceList.body"
            class="bulk-textarea price-list-preview"
            rows="18"
            readonly
            placeholder="No price list generated yet — click Regenerate."
          />
        </div>
        <div class="modal-foot">
          <span class="foot-spacer" />
          <div class="foot-actions">
            <button class="btn-ghost" @click="closePriceList">Close</button>
            <button class="btn-primary" :disabled="priceList.generating" @click="regeneratePriceList">
              {{ priceList.generating ? 'Generating…' : 'Regenerate' }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Create / Edit modal -->
    <div v-if="modal.open" class="modal-backdrop">
      <div
        class="modal product-modal"
        :style="{ transform: `translate(${productModalDrag.x}px, ${productModalDrag.y}px)` }"
      >
        <div class="modal-head product-modal-head" @mousedown="startProductModalDrag">
          <div>
            <h3>{{ modal.id ? 'Edit Product' : 'Add Product' }}</h3>
            <p class="product-modal-subtitle">Catalog details, pricing, and search aliases</p>
          </div>
          <button type="button" class="modal-close" @mousedown.stop @click="closeModal" title="Close">×</button>
        </div>

        <div class="modal-body product-modal-body">
          <div class="product-modal-col">
            <div class="form-section card-section">
              <div class="section-label">Basic Info</div>
              <div class="form-group">
                <label>Name *</label>
                <input v-model="modal.name" placeholder="iPhone 17 Pro Max" />
              </div>
              <div class="form-row form-row-3">
                <div class="form-group">
                  <label>Brand</label>
                  <input v-model="modal.brand" placeholder="Apple" />
                </div>
                <div class="form-group">
                  <label>Category</label>
                  <input v-model="modal.category" placeholder="Smartphones" />
                </div>
                <div class="form-group">
                  <label>SKU</label>
                  <input v-model="modal.sku" placeholder="Internal SKU or model number" />
                </div>
              </div>
            </div>

            <div class="form-section card-section">
              <div class="section-label">Pricing &amp; Stock</div>
              <div class="form-row form-row-4">
                <div class="form-group">
                  <label>Qty</label>
                  <input v-model.number="modal.qty" type="number" min="0" placeholder="0" />
                </div>
                <div class="form-group">
                  <label>Cost Price</label>
                  <input v-model="modal.cost_price" type="number" step="0.01" placeholder="e.g. 850" />
                </div>
                <div class="form-group">
                  <label>Sale Price</label>
                  <input v-model="modal.sale_price" type="number" step="0.01" placeholder="e.g. 950" />
                </div>
                <div class="form-group">
                  <label>Currency</label>
                  <input v-model="modal.currency" placeholder="USD" />
                </div>
              </div>
            </div>
          </div>

          <div class="product-modal-col">
            <div class="form-section card-section alias-section">
              <div class="section-label">
                Aliases
                <span class="hint">— alternate names/codes customers use (e.g. "17PM 256", "SKU-4421") — each one gets its own AI embedding so search finds this product no matter how it's phrased</span>
              </div>
              <div class="alias-input-box">
                <span v-for="a in modalAliases" :key="a.id" class="alias-chip removable">
                  {{ a.alias }}
                  <button type="button" class="alias-remove" @click="removeSavedAlias(a)" title="Remove">×</button>
                </span>
                <span v-for="(a, i) in pendingAliases" :key="`pending-${i}`" class="alias-chip removable pending" title="Will be saved with this product">
                  {{ a }}
                  <button type="button" class="alias-remove" @click="removePendingAlias(i)" title="Remove">×</button>
                </span>
                <input
                  v-model="aliasInput"
                  class="alias-input"
                  placeholder="Type an alias, press Enter…"
                  @keydown="handleAliasKeydown"
                  @blur="addAliasChip"
                />
              </div>
              <div v-if="aliasError" class="alias-error">{{ aliasError }}</div>
            </div>

            <div class="form-section card-section attribute-section">
              <div class="section-label">
                Attributes
                <span class="hint">— hot-add any extra key/value detail for this product (e.g. "Color: Silver", "Warranty: 1 year")</span>
              </div>
              <div class="attribute-list">
                <div v-for="a in modalAttributes" :key="a.id" class="attribute-row">
                  <input
                    class="attribute-key"
                    :value="a.key"
                    @change="updateSavedAttribute(a, { key: $event.target.value })"
                  />
                  <input
                    class="attribute-value"
                    :value="a.value"
                    @change="updateSavedAttribute(a, { value: $event.target.value })"
                  />
                  <button type="button" class="alias-remove" @click="removeSavedAttribute(a)" title="Remove">×</button>
                </div>
                <div v-for="(a, i) in pendingAttributes" :key="`pending-attr-${i}`" class="attribute-row pending" title="Will be saved with this product">
                  <input class="attribute-key" :value="a.key" disabled />
                  <input class="attribute-value" :value="a.value" disabled />
                  <button type="button" class="alias-remove" @click="removePendingAttribute(i)" title="Remove">×</button>
                </div>
                <div class="attribute-row attribute-row-new">
                  <input
                    v-model="newAttrKey"
                    class="attribute-key"
                    placeholder="Key (e.g. Color)"
                    @keydown.enter.prevent="addAttribute"
                  />
                  <input
                    v-model="newAttrValue"
                    class="attribute-value"
                    placeholder="Value (e.g. Silver)"
                    @keydown.enter.prevent="addAttribute"
                  />
                  <button type="button" class="btn-ghost attribute-add" :disabled="!newAttrKey.trim()" @click="addAttribute">Add</button>
                </div>
              </div>
              <div v-if="attrError" class="alias-error">{{ attrError }}</div>
            </div>
          </div>
        </div>

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
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { RouterLink } from 'vue-router'
import { tradingApi } from '../api/index.js'

const products    = ref([])
const search      = ref('')
const showInactive = ref(false)
const saving      = ref(false)

// Smart Search — separate embedding-based search, additive to the plain filter above.
// Deliberately search-on-submit (Enter/button), not search-as-you-type: the active
// embedding provider may be on a rate-limited free tier (§ AI Providers rate limiting),
// so firing a request per keystroke would be wasteful and slow to respond.
const smartQuery     = ref('')
const smartSearching = ref(false)
const smartSearched  = ref(false)
const smartResults   = ref([])
const smartError     = ref('')

async function runSmartSearch() {
  const q = smartQuery.value.trim()
  if (!q) return
  smartSearching.value = true
  smartError.value = ''
  try {
    const { data } = await tradingApi.searchProductEmbeddings({ q, top_k: 10 })
    smartResults.value = data.results || []
    smartSearched.value = true
  } catch (e) {
    smartError.value = e.response?.data?.detail || 'Smart search failed'
    smartResults.value = []
    smartSearched.value = true
  } finally {
    smartSearching.value = false
  }
}

function clearSmartSearch() {
  smartQuery.value = ''
  smartResults.value = []
  smartSearched.value = false
  smartError.value = ''
}

const modal = ref({
  open: false, id: null,
  name: '', brand: '', category: '', sku: '',
})

// Aliases are managed live via their own endpoints, independent of the main product
// save — modalAliases holds already-persisted rows (edit mode, fetched on open),
// pendingAliases holds not-yet-persisted strings (create mode, flushed to the API
// right after the product itself is created).
const modalAliases   = ref([])
const pendingAliases = ref([])
const aliasInput      = ref('')
const aliasSaving     = ref(false)
const aliasError      = ref('')

// Attributes — same live-CRUD-independent-of-product-save pattern as aliases above,
// just key/value pairs instead of a single string.
const modalAttributes   = ref([])
const pendingAttributes = ref([])
const newAttrKey    = ref('')
const newAttrValue  = ref('')
const attrSaving    = ref(false)
const attrError     = ref('')

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

const priceList = ref({
  open: false, body: '', generatedAt: null,
  generating: false, error: '',
})

function formatDateTime(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

async function openPriceList() {
  priceList.value.open  = true
  priceList.value.error = ''
  try {
    const { data } = await tradingApi.getPriceList()
    priceList.value.body        = data.body
    priceList.value.generatedAt = data.generated_at
  } catch (e) {
    priceList.value.error = e.response?.data?.error || 'Failed to load price list'
  }
}

function closePriceList() {
  priceList.value.open = false
}

async function regeneratePriceList() {
  priceList.value.generating = true
  priceList.value.error      = ''
  try {
    const { data } = await tradingApi.regeneratePriceList()
    priceList.value.body        = data.body
    priceList.value.generatedAt = data.generated_at
  } catch (e) {
    priceList.value.error = e.response?.data?.error || 'Failed to generate price list'
  } finally {
    priceList.value.generating = false
  }
}

function margin(p) {
  if (p.cost_price == null || p.sale_price == null) return null
  return p.sale_price - p.cost_price
}

function formatMoney(n) {
  return n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

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

const totalPnl = computed(() =>
  filtered.value.reduce((sum, p) => {
    const m = margin(p)
    return m == null ? sum : sum + m * (p.qty ?? 0)
  }, 0)
)

async function load() {
  const { data } = await tradingApi.listProducts({ active: 'all' })
  products.value = data
}

// Embedding coverage — the only durable signal that a background embedding job
// silently failed (provider hiccup, rate limit, etc.), since those failures only
// ever land in a console warning with nothing persisted otherwise.
const embeddingStatus = ref(null)
const backfilling     = ref(false)

const embeddingMissing = computed(() => {
  if (!embeddingStatus.value) return 0
  return embeddingStatus.value.products.missing + embeddingStatus.value.aliases.missing
})

async function loadEmbeddingStatus() {
  try {
    const { data } = await tradingApi.getEmbeddingStatus()
    embeddingStatus.value = data
  } catch { /* non-critical — badge just won't show this cycle */ }
}

async function runBackfillEmbeddings() {
  backfilling.value = true
  try {
    await tradingApi.backfillEmbeddings()
    await loadEmbeddingStatus()
  } finally {
    backfilling.value = false
  }
}

// ── Inline cell edit (Qty / Cost / Sale) ────────────────────────────────────────

const editingCell   = ref(null) // { id, field }
const editCellValue = ref('')
let suppressBlurSave = false

function isEditingCell(p, field) {
  return editingCell.value?.id === p.id && editingCell.value?.field === field
}

function startCellEdit(p, field) {
  if (isEditingCell(p, field)) return
  editingCell.value = { id: p.id, field }
  editCellValue.value = p[field] ?? ''
}

async function saveCellEdit(p, field) {
  if (suppressBlurSave) { suppressBlurSave = false; editingCell.value = null; return }
  editingCell.value = null
  const raw = editCellValue.value
  const value = field === 'qty'
    ? (raw === '' ? 0 : Number(raw))
    : (raw === '' ? null : Number(raw))
  const current = p[field] ?? (field === 'qty' ? 0 : null)
  if (value === current) return
  const { data } = await tradingApi.updateProduct(p.id, { [field]: value })
  const idx = products.value.findIndex(x => x.id === p.id)
  if (idx !== -1) products.value[idx] = data
}

function handleCellKeydown(e, p, field) {
  if (e.key === 'Enter') {
    e.target.blur()
  } else if (e.key === 'Escape') {
    suppressBlurSave = true
    e.target.blur()
  }
}

// Dragging for the product modal — cumulative translate offset from its default
// centered position, same technique used for the trading-desk popups.
const productModalDrag = ref({ x: 0, y: 0 })
let productModalDragState = null

function startProductModalDrag(e) {
  productModalDragState = {
    startX: e.clientX,
    startY: e.clientY,
    baseX: productModalDrag.value.x,
    baseY: productModalDrag.value.y,
  }
  window.addEventListener('mousemove', onProductModalDrag)
  window.addEventListener('mouseup', stopProductModalDrag)
}

function onProductModalDrag(e) {
  if (!productModalDragState) return
  productModalDrag.value = {
    x: productModalDragState.baseX + (e.clientX - productModalDragState.startX),
    y: productModalDragState.baseY + (e.clientY - productModalDragState.startY),
  }
}

function stopProductModalDrag() {
  productModalDragState = null
  window.removeEventListener('mousemove', onProductModalDrag)
  window.removeEventListener('mouseup', stopProductModalDrag)
}

function resetAliasState() {
  modalAliases.value = []
  pendingAliases.value = []
  aliasInput.value = ''
  aliasError.value = ''
}

function resetAttributeState() {
  modalAttributes.value = []
  pendingAttributes.value = []
  newAttrKey.value = ''
  newAttrValue.value = ''
  attrError.value = ''
}

function openCreate() {
  modal.value = {
    open: true, id: null, name: '', brand: '', category: '', sku: '',
    qty: 0, cost_price: '', sale_price: '', currency: 'USD',
  }
  productModalDrag.value = { x: 0, y: 0 }
  resetAliasState()
  resetAttributeState()
}

async function openEdit(p) {
  modal.value = {
    open: true, id: p.id,
    name: p.name, brand: p.brand, category: p.category, sku: p.sku,
    qty: p.qty ?? 0,
    cost_price: p.cost_price ?? '',
    sale_price: p.sale_price ?? '',
    currency: p.currency || 'USD',
  }
  productModalDrag.value = { x: 0, y: 0 }
  resetAliasState()
  resetAttributeState()
  try {
    const { data } = await tradingApi.listProductAliases(p.id)
    modalAliases.value = data
  } catch { /* non-critical — alias section just starts empty */ }
  try {
    const { data } = await tradingApi.listProductAttributes(p.id)
    modalAttributes.value = data
  } catch { /* non-critical — attribute section just starts empty */ }
}

function closeModal() {
  modal.value.open = false
  loadEmbeddingStatus()
}

// Enter or comma commits the current text as a chip. In edit mode this persists
// immediately (its own embedding gets queued server-side); in create mode it's held
// locally and flushed right after the product itself is created (see save()).
async function addAliasChip() {
  const text = aliasInput.value.trim().replace(/,+$/, '').trim()
  if (!text) return
  aliasInput.value = ''
  aliasError.value = ''

  if (!modal.value.id) {
    if (!pendingAliases.value.some(a => a.toLowerCase() === text.toLowerCase())) {
      pendingAliases.value.push(text)
    }
    return
  }

  aliasSaving.value = true
  try {
    const { data } = await tradingApi.addProductAlias(modal.value.id, text)
    modalAliases.value.push(data)
  } catch (e) {
    aliasError.value = e.response?.data?.detail || 'Failed to add alias'
  } finally {
    aliasSaving.value = false
  }
}

function handleAliasKeydown(e) {
  if (e.key === 'Enter' || e.key === ',') {
    e.preventDefault()
    addAliasChip()
    return
  }
  // Backspace on an empty input removes the most recently added chip — the one
  // immediately to the left of the cursor, same convention as Gmail's "To" field.
  if (e.key === 'Backspace' && !aliasInput.value) {
    if (pendingAliases.value.length) {
      removePendingAlias(pendingAliases.value.length - 1)
    } else if (modalAliases.value.length) {
      removeSavedAlias(modalAliases.value[modalAliases.value.length - 1])
    }
  }
}

function removePendingAlias(i) {
  pendingAliases.value.splice(i, 1)
}

async function removeSavedAlias(alias) {
  try {
    await tradingApi.deleteProductAlias(modal.value.id, alias.id)
    modalAliases.value = modalAliases.value.filter(a => a.id !== alias.id)
  } catch {
    aliasError.value = 'Failed to remove alias'
  }
}

// Same create-vs-edit split as aliases: pendingAttributes holds not-yet-persisted
// key/value pairs in create mode, flushed right after the product itself is created.
async function addAttribute() {
  const key = newAttrKey.value.trim()
  const value = newAttrValue.value.trim()
  if (!key) return
  attrError.value = ''

  if (!modal.value.id) {
    if (!pendingAttributes.value.some(a => a.key.toLowerCase() === key.toLowerCase())) {
      pendingAttributes.value.push({ key, value })
    }
    newAttrKey.value = ''
    newAttrValue.value = ''
    return
  }

  attrSaving.value = true
  try {
    const { data } = await tradingApi.addProductAttribute(modal.value.id, key, value)
    modalAttributes.value.push(data)
    newAttrKey.value = ''
    newAttrValue.value = ''
  } catch (e) {
    attrError.value = e.response?.data?.detail || 'Failed to add attribute'
  } finally {
    attrSaving.value = false
  }
}

function removePendingAttribute(i) {
  pendingAttributes.value.splice(i, 1)
}

async function removeSavedAttribute(attr) {
  try {
    await tradingApi.deleteProductAttribute(modal.value.id, attr.id)
    modalAttributes.value = modalAttributes.value.filter(a => a.id !== attr.id)
  } catch {
    attrError.value = 'Failed to remove attribute'
  }
}

async function updateSavedAttribute(attr, patch) {
  attrError.value = ''
  try {
    const { data } = await tradingApi.updateProductAttribute(modal.value.id, attr.id, patch)
    const idx = modalAttributes.value.findIndex(a => a.id === attr.id)
    if (idx !== -1) modalAttributes.value[idx] = data
  } catch (e) {
    attrError.value = e.response?.data?.detail || 'Failed to update attribute'
  }
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
      is_active: true,
      qty:        modal.value.qty === '' || modal.value.qty == null ? 0 : Number(modal.value.qty),
      cost_price: modal.value.cost_price === '' || modal.value.cost_price == null ? null : Number(modal.value.cost_price),
      sale_price: modal.value.sale_price === '' || modal.value.sale_price == null ? null : Number(modal.value.sale_price),
      currency:   modal.value.currency?.trim() || 'USD',
    }
    if (modal.value.id) {
      await tradingApi.updateProduct(modal.value.id, payload)
    } else {
      const { data } = await tradingApi.createProduct(payload)
      for (const alias of pendingAliases.value) {
        await tradingApi.addProductAlias(data.id, alias).catch(() => {})
      }
      for (const attr of pendingAttributes.value) {
        await tradingApi.addProductAttribute(data.id, attr.key, attr.value).catch(() => {})
      }
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

onMounted(() => { load(); loadEmbeddingStatus() })
onUnmounted(stopProductModalDrag)
</script>

<style scoped>
.products-view { display: flex; flex-direction: column; height: 100%; padding: 20px; gap: 14px; }
.view-header { display: flex; align-items: center; justify-content: space-between; }
.header-left { display: flex; align-items: center; gap: 10px; }
.header-left h2 { margin: 0; font-size: 1.2rem; }
.count-badge { background: #e5e7eb; border-radius: 999px; padding: 2px 10px; font-size: 0.8rem; }
.pnl-badge { border-radius: 999px; padding: 2px 10px; font-size: 0.8rem; font-weight: 600; }
.pnl-badge.positive { background: #dcfce7; color: #15803d; }
.pnl-badge.negative { background: #fee2e2; color: #dc2626; }
.embed-badge { border-radius: 999px; padding: 2px 10px; font-size: 0.8rem; font-weight: 600; background: #e0e7ff; color: #4338ca; }
.embed-badge.warn { background: #fef9c3; color: #92400e; }
.backfill-btn { padding: 4px 12px; border: 1px solid #f59e0b; border-radius: 999px; background: #fffbeb; color: #92400e; cursor: pointer; font-size: 0.8rem; font-weight: 600; }
.backfill-btn:hover { background: #fef3c7; }
.backfill-btn:disabled { opacity: 0.6; cursor: not-allowed; }
.toolbar { display: flex; gap: 12px; align-items: center; }
.search-input { flex: 1; padding: 7px 12px; border: 1px solid #d1d5db; border-radius: 6px; font-size: 0.9rem; }
.toggle-label { font-size: 0.88rem; display: flex; gap: 6px; align-items: center; cursor: pointer; }
.smart-search-box { background: #f5f3ff; border: 1px solid #ddd6fe; border-radius: 8px; padding: 10px 12px; display: flex; flex-direction: column; gap: 8px; }
.smart-search-row { display: flex; gap: 8px; align-items: center; }
.smart-search-icon { color: #7c3aed; font-size: 1rem; }
.smart-search-row .search-input { background: #fff; }
.btn-primary.sm { padding: 6px 14px; font-size: 0.85rem; }
.smart-results { border-top: 1px solid #ddd6fe; padding-top: 8px; }
.smart-results-table { background: #fff; border-radius: 6px; overflow: hidden; }
.match-badge { background: #ede9fe; color: #6d28d9; padding: 1px 8px; border-radius: 999px; font-size: 0.75rem; font-weight: 600; }
.empty-msg-sm { text-align: center; color: #9ca3af; font-size: 0.85rem; padding: 12px; }
.table-wrap { flex: 1; overflow-y: auto; border: 1px solid #e5e7eb; border-radius: 8px; }
.data-table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
.data-table th { background: #f9fafb; padding: 10px 14px; text-align: left; font-size: 0.8rem; color: #6b7280; border-bottom: 1px solid #e5e7eb; }
.data-table td { padding: 10px 14px; border-bottom: 1px solid #f3f4f6; vertical-align: top; }
.data-table tr:last-child td { border-bottom: none; }
.data-table tr.inactive { opacity: 0.5; }
.col-name { font-weight: 500; }
.alias-chip { background: #eff6ff; color: #1d4ed8; border-radius: 4px; padding: 1px 7px; font-size: 0.78rem; }
.td-inv .pos { color: #15803d; }
.td-inv .neg { color: #dc2626; }
.editable-cell { cursor: pointer; border-bottom: 1px dashed #d1d5db; padding-bottom: 1px; }
.editable-cell:hover { border-color: #2563eb; color: #2563eb; }
.inline-cell-input { width: 72px; text-align: right; border: 1px solid #2563eb; border-radius: 4px; padding: 2px 5px; font-size: 0.9rem; font-variant-numeric: tabular-nums; }
.inline-cell-input:focus { outline: none; box-shadow: 0 0 0 2px rgba(37,99,235,0.2); }
.col-actions { display: flex; gap: 6px; white-space: nowrap; }
.status-dot { font-size: 0.8rem; font-weight: 500; }
.status-dot.active { color: #16a34a; }
.status-dot.inactive { color: #9ca3af; }
.th-embed { text-align: center; font-size: 0.78rem; }
.embed-dot { font-weight: 600; }
.embed-dot.yes { color: #16a34a; }
.embed-dot.no { color: #dc2626; }
.embed-dot.partial { color: #d97706; }
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
.form-group { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
.form-group label { font-size: 0.83rem; color: #374151; font-weight: 500; }
.form-group input, .form-group textarea { width: 100%; box-sizing: border-box; padding: 7px 10px; border: 1px solid #d1d5db; border-radius: 6px; font-size: 0.9rem; }
.form-row { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.form-row-3 { grid-template-columns: repeat(3, minmax(0, 1fr)); }
.form-row-4 { grid-template-columns: repeat(4, minmax(0, 1fr)); }
.hint { font-weight: 400; color: #6b7280; }
.modal-actions { padding: 14px 24px; border-top: 1px solid #e5e7eb; display: flex; justify-content: flex-end; gap: 8px; flex-shrink: 0; }
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
.price-list-meta { font-size: 0.8rem; color: #6b7280; margin-bottom: 8px; }
.price-list-preview { font-family: inherit; background: #fafafa; color: #1f2937; white-space: pre-wrap; }
.bulk-result { color: #16a34a; font-size: 0.85rem; }
.preview-header { display: flex; justify-content: space-between; align-items: center; font-size: 0.85rem; color: #374151; }
.preview-table-wrap { max-height: 240px; overflow-y: auto; border: 1px solid #e5e7eb; border-radius: 6px; }
.inline-input { width: 100%; border: none; background: transparent; font-size: 0.85rem; padding: 2px 4px; outline: none; }
.inline-input:focus { background: #eff6ff; border-radius: 3px; }
/* Product create/edit modal */
.product-modal {
  width: 1200px;
  max-width: calc(100vw - 32px);
  max-height: 85vh;
  box-shadow: 0 20px 60px rgba(0,0,0,0.3);
}
.product-modal-head {
  display: flex;
  flex-direction: row;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 18px 24px;
  background: linear-gradient(to bottom, #fafbff, #ffffff);
  border-bottom: 1px solid #e5e7eb;
  cursor: move;
  user-select: none;
}
.product-modal-head h3 { margin: 0 0 2px; }
.product-modal-subtitle { margin: 0; font-size: 0.8rem; color: #9ca3af; }
.modal-close {
  border: none;
  background: transparent;
  font-size: 1.5rem;
  line-height: 1;
  color: #9ca3af;
  cursor: pointer;
  padding: 2px 8px;
  border-radius: 6px;
  flex-shrink: 0;
}
.modal-close:hover { background: #f3f4f6; color: #374151; }
.product-modal-body { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; align-items: start; }
.product-modal-col { display: flex; flex-direction: column; gap: 16px; min-width: 0; }
.card-section {
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 16px;
  border-bottom: 1px solid #e5e7eb;
}
.alias-section { flex: 1; }
.form-section { display: flex; flex-direction: column; gap: 12px; }
.section-label { font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.05em; color: #9ca3af; font-weight: 700; }
.alias-input-box {
  display: flex; flex-wrap: wrap; align-content: flex-start; align-items: center; gap: 6px;
  padding: 10px; border: 1px solid #d1d5db; border-radius: 8px; background: #fff;
  min-height: 200px; max-height: 340px; overflow-y: auto;
}
.alias-input-box:focus-within { border-color: #2563eb; box-shadow: 0 0 0 2px rgba(37,99,235,0.15); }
.alias-chip.removable { display: inline-flex; align-items: center; gap: 4px; }
.alias-chip.pending { background: #fef9c3; color: #92400e; }
.alias-remove { border: none; background: transparent; color: inherit; opacity: 0.6; cursor: pointer; font-size: 0.9rem; line-height: 1; padding: 0; }
.alias-remove:hover { opacity: 1; }
.alias-input { flex: 1; min-width: 140px; border: none; outline: none; font-size: 0.85rem; padding: 3px 2px; }
.alias-error { color: #dc2626; font-size: 0.8rem; }
.attribute-section { flex: 1; }
.attribute-list { display: flex; flex-direction: column; gap: 6px; }
.attribute-row { display: flex; align-items: center; gap: 6px; }
.attribute-row.pending { opacity: 0.7; }
.attribute-key {
  flex: 0 0 38%; border: 1px solid #d1d5db; border-radius: 6px; font-size: 0.85rem;
  padding: 6px 8px; background: #fff; font-weight: 500;
}
.attribute-value { flex: 1; min-width: 0; border: 1px solid #d1d5db; border-radius: 6px; font-size: 0.85rem; padding: 6px 8px; background: #fff; }
.attribute-row-new .attribute-key, .attribute-row-new .attribute-value { background: #fff; }
.attribute-add { flex-shrink: 0; padding: 6px 12px; font-size: 0.82rem; }
@media (max-width: 860px) {
  .product-modal-body { grid-template-columns: 1fr; }
}
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
