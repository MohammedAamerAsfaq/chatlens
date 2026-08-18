<template>
  <div class="selling-offers-view">
    <div class="page-head">
      <div>
        <p class="eyebrow">Customer offers</p>
        <h1>Selling Offers</h1>
        <p class="subtitle">
          Create selling inquiries, select inventory products, build a customer list, and send offers manually through WhatsApp.
        </p>
      </div>
      <button class="primary-btn" @click="resetDraft">+ New Selling Inquiry</button>
    </div>

    <div v-if="error" class="error-box">{{ error }}</div>

    <div class="layout-grid">
      <section class="panel compose-panel">
        <div class="panel-head">
          <div>
            <h2>Create Selling Inquiry</h2>
            <p>Save an offer first, then use the offer row to auto-add customers from WTB inquiry products.</p>
          </div>
          <span class="status-chip open">Draft</span>
        </div>

        <div class="form-grid">
          <label>
            <span>Inquiry name</span>
            <input v-model="draft.name" placeholder="Example: iPhone 17 Pro Max UAE stock offer" />
          </label>
          <label>
            <span>Status</span>
            <select v-model="draft.status">
              <option value="open">Inquiry Open</option>
              <option value="closed">Inquiry Closed</option>
            </select>
          </label>
        </div>

        <div class="section-block">
          <div class="section-title-row">
            <div>
              <h3>Products to Offer</h3>
              <p>Multiple inventory products can be added to one selling inquiry.</p>
            </div>
          </div>

          <div class="product-picker">
            <input v-model="productSearch" placeholder="Search inventory product..." @keydown.enter.prevent="searchProducts" />
            <button class="ghost-btn" :disabled="searchingProducts" @click="searchProducts">
              {{ searchingProducts ? 'Searching...' : 'Search' }}
            </button>
          </div>

          <div v-if="productOptions.length" class="option-list">
            <button v-for="product in productOptions" :key="product.id" class="option-row" @click="addDraftProduct(product)">
              <strong>{{ productLabel(product) }}</strong>
              <span>{{ product.qty }} in stock - {{ money(product.sale_price, product.currency) }}</span>
            </button>
          </div>

          <div class="product-list">
            <div v-for="product in draft.products" :key="product.id" class="product-row">
              <div>
                <strong>{{ productLabel(product) }}</strong>
                <span>{{ product.qty }} in stock - {{ money(product.sale_price, product.currency) }}</span>
              </div>
              <button class="link-btn danger" @click="removeDraftProduct(product.id)">Remove</button>
            </div>
            <div v-if="draft.products.length === 0" class="empty-note">No products selected.</div>
          </div>
        </div>

        <div class="section-block">
          <div class="section-title-row">
            <div>
              <h3>Offer Message Format</h3>
              <p>Stored on this selling offer. Central reusable templates can be added later.</p>
            </div>
          </div>
          <div class="template-grid">
            <label>
              <span>Header</span>
              <textarea v-model="draft.header_template" rows="2" />
            </label>
            <label>
              <span>Product line</span>
              <textarea v-model="draft.product_line_template" rows="2" />
            </label>
            <label>
              <span>Footer</span>
              <textarea v-model="draft.footer_template" rows="2" />
            </label>
          </div>
        </div>

        <div class="form-actions">
          <button class="ghost-btn" @click="resetDraft">Reset</button>
          <button class="primary-btn" :disabled="savingOffer" @click="createOffer">
            {{ savingOffer ? 'Creating...' : 'Create Selling Inquiry' }}
          </button>
        </div>
      </section>

      <aside class="panel preview-panel">
        <div class="panel-head compact">
          <div>
            <h2>Offer Preview</h2>
            <p>Message users will send manually through WhatsApp.</p>
          </div>
        </div>
        <div class="phone-preview">
          <pre>{{ draftPreview }}</pre>
        </div>
        <div class="hint-box">
          WhatsApp sending stays manual. The system opens WhatsApp with pre-filled text and records button presses.
        </div>
      </aside>
    </div>

    <section class="panel list-panel">
      <div class="panel-head">
        <div>
          <h2>Existing Selling Inquiries</h2>
          <p>Each row shows status and customer notification progress.</p>
        </div>
        <button class="ghost-btn" :disabled="loadingOffers" @click="loadOffers">
          {{ loadingOffers ? 'Refreshing...' : 'Refresh' }}
        </button>
      </div>

      <div class="offer-list">
        <div v-if="loadingOffers" class="empty-note">Loading selling offers...</div>
        <div v-else-if="offers.length === 0" class="empty-note">No selling offers created yet.</div>
        <div v-for="offer in offers" :key="offer.id" class="offer-card">
          <button class="offer-summary" @click="toggleOffer(offer.id)">
            <div>
              <strong>{{ offer.name }}</strong>
              <span>{{ offer.products.length }} products - {{ offer.customer_count }} customers</span>
            </div>
            <div class="offer-right">
              <span class="progress-pill">{{ offer.notified_count }}/{{ offer.customer_count }} notified</span>
              <span :class="['status-chip', offer.status]">{{ offer.status === 'open' ? 'Open' : 'Closed' }}</span>
              <span class="chevron">{{ expandedOffers.has(offer.id) ? 'UP' : 'DOWN' }}</span>
            </div>
          </button>

          <div v-if="expandedOffers.has(offer.id)" class="offer-detail">
            <div class="detail-grid">
              <div>
                <div class="section-title-row compact-title">
                  <h3>Products</h3>
                  <span class="muted">{{ offer.products.length }} selected</span>
                </div>
                <div class="detail-products">
                  <div v-for="row in offer.products" :key="row.id" class="product-token-row">
                    <div>
                      <strong>{{ row.product_name }}</strong>
                      <span>{{ row.quantity ?? '-' }} qty - {{ money(row.price, row.currency) }}</span>
                    </div>
                    <button class="link-btn" :disabled="busyAction === `auto-${offer.id}-${row.product}`" @click="autoAddCustomers(offer, row)">
                      {{ busyAction === `auto-${offer.id}-${row.product}` ? 'Finding...' : 'Find customers from Inquiry Products' }}
                    </button>
                  </div>
                </div>
              </div>

              <div>
                <div class="section-title-row compact-title">
                  <h3>Manual Add Customer</h3>
                </div>
                <div class="customer-tools">
                  <input v-model="customerSearch[offer.id]" placeholder="Search customer name or phone..." @keydown.enter.prevent="searchContacts(offer)" />
                  <button class="ghost-btn" @click="searchContacts(offer)">Search</button>
                </div>
                <div v-if="contactOptions[offer.id]?.length" class="option-list">
                  <button v-for="contact in contactOptions[offer.id]" :key="contact.id" class="option-row" @click="addCustomer(offer, contact)">
                    <strong>{{ contactLabel(contact) }}</strong>
                    <span>{{ contact.phone_number || contact.wa_contact_id }} - {{ contact.account_name }}</span>
                  </button>
                </div>
              </div>
            </div>

            <div class="detail-customer-list">
              <div v-if="offer.customers.length === 0" class="empty-note">No customers added yet.</div>
              <div v-for="customer in offer.customers" :key="customer.id" class="customer-row compact-row">
                <div class="customer-main">
                  <strong>{{ customer.contact_name }}</strong>
                  <span>{{ customer.phone_number || 'No phone' }} - {{ customer.account_name }} - {{ customer.source === 'auto' ? 'Auto: WTB inquiry product' : 'Manual add' }}</span>
                </div>
                <span class="notify-pill" :class="{ sent: customer.sent_count > 0 }">
                  {{ customer.sent_count > 0 ? `WA pressed ${customer.sent_count}x` : 'Not notified' }}
                </span>
                <a
                  class="wa-btn"
                  :href="whatsappUrl(customer.phone_number, offerPreview(offer))"
                  @click="markSent(offer, customer)"
                >
                  WA
                </a>
              </div>
            </div>

            <div class="detail-actions">
              <button v-if="offer.status === 'open'" class="ghost-btn" @click="closeOffer(offer)">Close Inquiry</button>
              <button v-else class="ghost-btn" @click="reopenOffer(offer)">Reopen Inquiry</button>
            </div>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { contactsApi, tradingApi } from '@/api'

const DEFAULT_HEADER = 'Hello, available stock offer:'
const DEFAULT_LINE = '- {product_name} - Qty {qty} - {price}'
const DEFAULT_FOOTER = 'Reply with required quantity. Subject to availability.'

const offers = ref([])
const productOptions = ref([])
const expandedOffers = reactive(new Set())
const customerSearch = reactive({})
const contactOptions = reactive({})
const productSearch = ref('')
const loadingOffers = ref(false)
const searchingProducts = ref(false)
const savingOffer = ref(false)
const busyAction = ref('')
const error = ref('')

const draft = reactive({
  name: '',
  status: 'open',
  products: [],
  header_template: DEFAULT_HEADER,
  product_line_template: DEFAULT_LINE,
  footer_template: DEFAULT_FOOTER,
})

const draftPreview = computed(() => formatOfferMessage({
  header_template: draft.header_template,
  product_line_template: draft.product_line_template,
  footer_template: draft.footer_template,
  products: draft.products.map(product => ({
    product_name: productLabel(product),
    quantity: product.qty,
    price: product.sale_price,
    currency: product.currency,
  })),
}))

onMounted(loadOffers)

async function loadOffers() {
  loadingOffers.value = true
  error.value = ''
  try {
    const { data } = await tradingApi.listSellingOffers({ page_size: 50 })
    offers.value = data.results || data
  } catch (exc) {
    error.value = apiError(exc, 'Failed to load selling offers.')
  } finally {
    loadingOffers.value = false
  }
}

async function searchProducts() {
  searchingProducts.value = true
  error.value = ''
  try {
    const { data } = await tradingApi.listProducts({ search: productSearch.value, active: 'true' })
    productOptions.value = data.results || data
  } catch (exc) {
    error.value = apiError(exc, 'Product search failed.')
  } finally {
    searchingProducts.value = false
  }
}

function addDraftProduct(product) {
  if (draft.products.some(row => row.id === product.id)) return
  draft.products.push(product)
}

function removeDraftProduct(productId) {
  draft.products = draft.products.filter(product => product.id !== productId)
}

async function createOffer() {
  if (!draft.name.trim()) {
    error.value = 'Inquiry name is required.'
    return
  }
  savingOffer.value = true
  error.value = ''
  try {
    const payload = {
      name: draft.name.trim(),
      status: draft.status,
      header_template: draft.header_template,
      product_line_template: draft.product_line_template,
      footer_template: draft.footer_template,
      product_ids: draft.products.map(product => product.id),
    }
    const { data } = await tradingApi.createSellingOffer(payload)
    offers.value.unshift(data)
    expandedOffers.add(data.id)
    resetDraft()
  } catch (exc) {
    error.value = apiError(exc, 'Create selling inquiry failed.')
  } finally {
    savingOffer.value = false
  }
}

async function autoAddCustomers(offer, productRow) {
  busyAction.value = `auto-${offer.id}-${productRow.product}`
  error.value = ''
  try {
    const { data } = await tradingApi.autoAddSellingOfferCustomers(offer.id, productRow.product)
    replaceOffer(data.offer)
  } catch (exc) {
    error.value = apiError(exc, 'Auto customer discovery failed.')
  } finally {
    busyAction.value = ''
  }
}

async function searchContacts(offer) {
  const query = customerSearch[offer.id] || ''
  error.value = ''
  try {
    const { data } = await contactsApi.list({ search: query, type: 'phone', page_size: 10 })
    contactOptions[offer.id] = data.results || data
  } catch (exc) {
    error.value = apiError(exc, 'Contact search failed.')
  }
}

async function addCustomer(offer, contact) {
  error.value = ''
  try {
    await tradingApi.addSellingOfferCustomer(offer.id, contact.id)
    await refreshOffer(offer.id)
    contactOptions[offer.id] = []
    customerSearch[offer.id] = ''
  } catch (exc) {
    error.value = apiError(exc, 'Add customer failed.')
  }
}

async function markSent(offer, customer) {
  try {
    const { data } = await tradingApi.markSellingOfferCustomerSent(offer.id, customer.id)
    const current = offers.value.find(row => row.id === offer.id)
    if (!current) return
    const idx = current.customers.findIndex(row => row.id === customer.id)
    if (idx !== -1) current.customers[idx] = data
    current.notified_count = current.customers.filter(row => row.sent_count > 0).length
  } catch (exc) {
    error.value = apiError(exc, 'Could not record WA press.')
  }
}

async function closeOffer(offer) {
  error.value = ''
  try {
    const { data } = await tradingApi.closeSellingOffer(offer.id)
    replaceOffer(data)
  } catch (exc) {
    error.value = apiError(exc, 'Close inquiry failed.')
  }
}

async function reopenOffer(offer) {
  error.value = ''
  try {
    const { data } = await tradingApi.updateSellingOffer(offer.id, { status: 'open' })
    replaceOffer(data)
  } catch (exc) {
    error.value = apiError(exc, 'Reopen inquiry failed.')
  }
}

async function refreshOffer(id) {
  const { data } = await tradingApi.listSellingOffers({ page_size: 50 })
  offers.value = data.results || data
  expandedOffers.add(id)
}

function replaceOffer(updated) {
  const idx = offers.value.findIndex(row => row.id === updated.id)
  if (idx === -1) offers.value.unshift(updated)
  else offers.value[idx] = updated
}

function resetDraft() {
  draft.name = ''
  draft.status = 'open'
  draft.products = []
  draft.header_template = DEFAULT_HEADER
  draft.product_line_template = DEFAULT_LINE
  draft.footer_template = DEFAULT_FOOTER
  productOptions.value = []
  productSearch.value = ''
}

function toggleOffer(id) {
  if (expandedOffers.has(id)) expandedOffers.delete(id)
  else expandedOffers.add(id)
}

function productLabel(product) {
  return `${product.brand || ''} ${product.name || product.product_name || ''}`.trim()
}

function contactLabel(contact) {
  return contact.display_name || contact.push_name || contact.phone_number || contact.wa_contact_id
}

function money(value, currency = '') {
  if (value === null || value === undefined || value === '') return '-'
  const num = Number(value)
  const amount = Number.isNaN(num) ? value : num.toLocaleString(undefined, { maximumFractionDigits: 2 })
  return `${currency || ''} ${amount}`.trim()
}

function formatOfferMessage(offer) {
  const lines = (offer.products || []).map(row => {
    const line = offer.product_line_template || DEFAULT_LINE
    return line
      .replaceAll('{product_name}', row.product_name || '')
      .replaceAll('{qty}', row.quantity ?? '-')
      .replaceAll('{price}', money(row.price, row.currency))
  })
  return [offer.header_template || DEFAULT_HEADER, '', ...lines, '', offer.footer_template || DEFAULT_FOOTER].join('\n')
}

function offerPreview(offer) {
  return formatOfferMessage(offer)
}

function whatsappUrl(phone, text = '') {
  const params = new URLSearchParams()
  if (phone) params.set('phone', phone)
  if (text) params.set('text', text)
  return `whatsapp://send?${params.toString()}`
}

function apiError(exc, fallback) {
  const data = exc?.response?.data
  if (typeof data === 'string') return data
  if (data?.detail) return data.detail
  if (data?.error) return data.error
  if (data && typeof data === 'object') return Object.entries(data).map(([key, val]) => `${key}: ${val}`).join(' | ')
  return fallback
}
</script>

<style scoped>
.selling-offers-view {
  height: 100%;
  overflow-y: auto;
  padding: 24px;
  background: #f8fafc;
  color: #111827;
}
.page-head,
.panel-head,
.section-title-row,
.offer-summary,
.customer-row,
.form-actions,
.detail-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}
.page-head {
  margin-bottom: 20px;
}
.eyebrow {
  margin: 0 0 6px;
  color: #0f766e;
  font-size: 0.72rem;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}
h1,
h2,
h3,
p {
  margin: 0;
}
h1 {
  font-size: 1.8rem;
  font-weight: 900;
}
h2 {
  font-size: 1.05rem;
  font-weight: 850;
}
h3 {
  font-size: 0.9rem;
  font-weight: 800;
}
.subtitle,
.panel-head p,
.section-title-row p {
  margin-top: 5px;
  color: #64748b;
  font-size: 0.86rem;
}
.error-box {
  margin-bottom: 14px;
  border: 1px solid #fecaca;
  border-radius: 12px;
  background: #fef2f2;
  color: #b91c1c;
  padding: 12px 14px;
  font-weight: 700;
}
.layout-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 360px;
  gap: 18px;
  align-items: start;
}
.panel {
  border: 1px solid #dbe4ee;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.96);
  box-shadow: 0 12px 32px rgba(15, 23, 42, 0.05);
}
.compose-panel,
.preview-panel,
.list-panel {
  padding: 18px;
}
.list-panel {
  margin-top: 18px;
}
.panel-head {
  padding-bottom: 14px;
  border-bottom: 1px solid #edf2f7;
}
.panel-head.compact {
  border-bottom: none;
  padding-bottom: 10px;
}
.form-grid {
  display: grid;
  grid-template-columns: 1fr 220px;
  gap: 12px;
  margin-top: 16px;
}
label {
  display: flex;
  flex-direction: column;
  gap: 6px;
  color: #64748b;
  font-size: 0.74rem;
  font-weight: 800;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}
input,
select,
textarea {
  border: 1px solid #cbd5e1;
  border-radius: 11px;
  padding: 0 12px;
  background: #fff;
  color: #111827;
  font-size: 0.9rem;
  text-transform: none;
  letter-spacing: 0;
  font-weight: 500;
}
input,
select {
  height: 40px;
}
textarea {
  min-height: 58px;
  padding-top: 10px;
  resize: vertical;
}
.section-block {
  margin-top: 18px;
  padding-top: 18px;
  border-top: 1px solid #edf2f7;
}
.compact-title {
  margin-bottom: 10px;
}
.product-picker,
.customer-tools {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 8px;
  margin-top: 12px;
}
.template-grid,
.product-list,
.customer-list,
.offer-list,
.detail-customer-list,
.option-list,
.detail-products {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 12px;
}
.option-row,
.product-row,
.customer-row,
.offer-card,
.product-token-row {
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  background: #fff;
}
.option-row {
  display: block;
  width: 100%;
  padding: 10px 12px;
  text-align: left;
  cursor: pointer;
}
.product-row,
.product-token-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px;
}
.product-row strong,
.customer-main strong,
.offer-summary strong,
.option-row strong,
.product-token-row strong {
  display: block;
  color: #111827;
  font-weight: 850;
}
.product-row span,
.customer-main span,
.offer-summary span,
.option-row span,
.product-token-row span,
.muted {
  display: block;
  margin-top: 3px;
  color: #64748b;
  font-size: 0.78rem;
}
.customer-row {
  padding: 10px 12px;
}
.customer-main {
  min-width: 0;
  flex: 1;
}
.status-chip,
.notify-pill,
.progress-pill {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 4px 10px;
  font-size: 0.72rem;
  font-weight: 850;
  white-space: nowrap;
}
.status-chip.open {
  background: #dcfce7;
  color: #15803d;
}
.status-chip.closed {
  background: #f1f5f9;
  color: #64748b;
}
.notify-pill {
  background: #f8fafc;
  color: #94a3b8;
}
.notify-pill.sent {
  background: #e0f2fe;
  color: #0369a1;
}
.progress-pill {
  background: #fff7ed;
  color: #c2410c;
}
.primary-btn,
.ghost-btn,
.link-btn,
.wa-btn {
  border: 1px solid transparent;
  border-radius: 11px;
  cursor: pointer;
  font-weight: 850;
  text-decoration: none;
}
.primary-btn {
  height: 40px;
  padding: 0 16px;
  background: #0f766e;
  color: #fff;
}
.ghost-btn {
  height: 38px;
  padding: 0 13px;
  border-color: #cbd5e1;
  background: #fff;
  color: #334155;
}
.link-btn {
  padding: 7px 10px;
  background: #ecfeff;
  color: #0e7490;
  font-size: 0.76rem;
}
.link-btn.danger {
  background: #fff1f2;
  color: #be123c;
}
.wa-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 32px;
  padding: 0 12px;
  background: #dcfce7;
  color: #15803d;
}
button:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}
.form-actions {
  justify-content: flex-end;
  margin-top: 18px;
  padding-top: 18px;
  border-top: 1px solid #edf2f7;
}
.phone-preview {
  min-height: 260px;
  border: 1px solid #dbe4ee;
  border-radius: 14px;
  background: #0f172a;
  color: #d1fae5;
  padding: 12px;
  font-size: 0.78rem;
  line-height: 1.55;
}
pre {
  margin: 0;
  white-space: pre-wrap;
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
}
.hint-box {
  margin-top: 12px;
  border: 1px solid #fed7aa;
  border-radius: 14px;
  background: #fff7ed;
  color: #9a3412;
  padding: 12px;
  font-size: 0.82rem;
  line-height: 1.45;
}
.offer-summary {
  width: 100%;
  padding: 14px 16px;
  border: none;
  background: transparent;
  text-align: left;
  cursor: pointer;
}
.offer-right {
  display: flex;
  align-items: center;
  gap: 8px;
}
.chevron {
  color: #94a3b8;
  font-size: 0.68rem;
  font-weight: 900;
}
.offer-detail {
  padding: 0 16px 16px;
  border-top: 1px solid #edf2f7;
}
.detail-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
  padding-top: 12px;
}
.compact-row {
  border-radius: 12px;
}
.detail-actions {
  justify-content: flex-end;
  margin-top: 12px;
}
.empty-note {
  color: #94a3b8;
  font-size: 0.86rem;
  padding: 10px 0;
}
@media (max-width: 1080px) {
  .layout-grid,
  .detail-grid {
    grid-template-columns: 1fr;
  }
}
@media (max-width: 720px) {
  .selling-offers-view {
    padding: 16px;
  }
  .page-head,
  .panel-head,
  .section-title-row,
  .offer-summary,
  .customer-row,
  .form-actions {
    align-items: stretch;
    flex-direction: column;
  }
  .form-grid,
  .product-picker,
  .customer-tools {
    grid-template-columns: 1fr;
  }
  .offer-right {
    flex-wrap: wrap;
  }
}
</style>
