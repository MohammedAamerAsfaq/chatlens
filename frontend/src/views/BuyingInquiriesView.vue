<template>
  <div class="buying-inquiries-view">
    <div class="page-head">
      <div>
        <p class="eyebrow">Supplier inquiries</p>
        <h1>Buying Inquiries</h1>
        <p class="subtitle">
          Create buying inquiries, select required inventory products, build a supplier list, and ask manually through WhatsApp.
        </p>
      </div>
      <button class="primary-btn" @click="resetDraft">+ New Buying Inquiry</button>
    </div>

    <div v-if="error" class="error-box">{{ error }}</div>

    <div class="layout-grid">
      <section class="panel compose-panel">
        <div class="panel-head">
          <div>
            <h2>Create Buying Inquiry</h2>
            <p>Save an inquiry first, then use the inquiry row to auto-add suppliers from WTS inquiry products.</p>
          </div>
          <span class="status-chip open">Draft</span>
        </div>

        <div class="form-grid">
          <label>
            <span>Inquiry name</span>
            <input v-model="draft.name" placeholder="Example: Need iPhone 17 Pro Max Japan stock" />
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
              <h3>Products to Buy</h3>
              <p>Multiple inventory products can be added to one buying inquiry.</p>
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
              <h3>Ask Message Format</h3>
              <p>Stored on this buying inquiry. Central reusable templates can be added later.</p>
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
          <button class="primary-btn" :disabled="savingInquiry" @click="createInquiry">
            {{ savingInquiry ? 'Creating...' : 'Create Buying Inquiry' }}
          </button>
        </div>
      </section>

      <aside class="panel preview-panel">
        <div class="panel-head compact">
          <div>
            <h2>Ask Preview</h2>
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
          <h2>Existing Buying Inquiries</h2>
          <p>Each row shows status and supplier notification progress.</p>
        </div>
        <button class="ghost-btn" :disabled="loadingInquiries" @click="loadInquiries">
          {{ loadingInquiries ? 'Refreshing...' : 'Refresh' }}
        </button>
      </div>

      <div class="list-tools">
        <input
          v-model="inquirySearch"
          placeholder="Search buying inquiries, products, suppliers..."
          @keydown.enter.prevent="applyInquirySearch"
        />
        <button class="ghost-btn" @click="applyInquirySearch">Search</button>
        <button class="ghost-btn" :disabled="!inquirySearch" @click="clearInquirySearch">Clear</button>
        <select v-model.number="inquiryPageSize" @change="changeInquiryPageSize">
          <option :value="10">10</option>
          <option :value="25">25</option>
          <option :value="50">50</option>
          <option :value="100">100</option>
        </select>
      </div>

      <div class="list-meta">
        <span>{{ inquiryRangeText }}</span>
        <div class="pager">
          <button class="ghost-btn" :disabled="inquiryPage <= 1 || loadingInquiries" @click="goInquiryPage(inquiryPage - 1)">Previous</button>
          <span>Page {{ inquiryPage }} of {{ inquiryTotalPages }}</span>
          <button class="ghost-btn" :disabled="inquiryPage >= inquiryTotalPages || loadingInquiries" @click="goInquiryPage(inquiryPage + 1)">Next</button>
        </div>
      </div>

      <div class="inquiry-list">
        <div v-if="loadingInquiries" class="empty-note">Loading buying inquiries...</div>
        <div v-else-if="inquiries.length === 0" class="empty-note">No buying inquiries created yet.</div>
        <div v-for="(inquiry, index) in inquiries" :key="inquiry.id" class="inquiry-card">
          <button class="inquiry-summary" @click="toggleInquiry(inquiry.id)">
            <div class="inquiry-title-row">
              <span class="row-index"><span>{{ inquiryRowNumber(index) }}</span></span>
              <div>
                <strong>{{ inquiry.name }}</strong>
                <span>{{ inquiry.products.length }} products - {{ inquiry.supplier_count }} suppliers</span>
              </div>
            </div>
            <div class="inquiry-right">
              <span class="progress-pill">{{ inquiry.notified_count }}/{{ inquiry.supplier_count }} notified</span>
              <span :class="['status-chip', inquiry.status]">{{ inquiry.status === 'open' ? 'Open' : 'Closed' }}</span>
              <span v-if="editingInquiryId === inquiry.id" class="edit-pill">Editing</span>
              <span
                :class="['caret-btn', expandedInquiries.has(inquiry.id) ? 'is-open' : '']"
                :aria-label="expandedInquiries.has(inquiry.id) ? 'Collapse inquiry' : 'Expand inquiry'"
              >
                <FontAwesomeIcon :icon="expandedInquiries.has(inquiry.id) ? faChevronDown : faChevronRight" />
              </span>
            </div>
          </button>

          <div v-if="expandedInquiries.has(inquiry.id)" class="inquiry-detail">
            <div class="edit-toolbar">
              <template v-if="editingInquiryId !== inquiry.id">
                <button class="ghost-btn" @click="startEditInquiry(inquiry)">Edit Inquiry</button>
                <button class="ghost-btn" :disabled="busyAction === `duplicate-${inquiry.id}`" @click="duplicateInquiry(inquiry)">
                  {{ busyAction === `duplicate-${inquiry.id}` ? 'Duplicating...' : 'Duplicate' }}
                </button>
                <button class="ghost-btn danger" :disabled="busyAction === `delete-${inquiry.id}`" @click="deleteInquiry(inquiry)">
                  {{ busyAction === `delete-${inquiry.id}` ? 'Deleting...' : 'Delete' }}
                </button>
              </template>
              <template v-else>
                <button class="primary-btn" :disabled="busyAction === `save-${inquiry.id}`" @click="saveEditInquiry(inquiry)">
                  {{ busyAction === `save-${inquiry.id}` ? 'Saving...' : 'Save Changes' }}
                </button>
                <button class="ghost-btn" @click="cancelEditInquiry">Cancel</button>
              </template>
            </div>

            <div v-if="editingInquiryId === inquiry.id" class="edit-panel">
              <div class="form-grid">
                <label>
                  <span>Inquiry name</span>
                  <input v-model="editDraft.name" />
                </label>
                <label>
                  <span>Status</span>
                  <select v-model="editDraft.status">
                    <option value="open">Inquiry Open</option>
                    <option value="closed">Inquiry Closed</option>
                  </select>
                </label>
              </div>
              <div class="template-grid edit-template-grid">
                <label>
                  <span>Header</span>
                  <textarea v-model="editDraft.header_template" rows="2" />
                </label>
                <label>
                  <span>Product line</span>
                  <textarea v-model="editDraft.product_line_template" rows="2" />
                </label>
                <label>
                  <span>Footer</span>
                  <textarea v-model="editDraft.footer_template" rows="2" />
                </label>
              </div>
            </div>

            <div class="detail-grid">
              <div>
                <div class="section-title-row compact-title">
                  <h3>Products</h3>
                  <span class="muted">{{ inquiry.products.length }} selected</span>
                </div>
                <div v-if="editingInquiryId === inquiry.id" class="product-picker inline-picker">
                  <input
                    v-model="editProductSearch[inquiry.id]"
                    placeholder="Search product to add..."
                    @keydown.enter.prevent="searchEditProducts(inquiry)"
                  />
                  <button class="ghost-btn" @click="searchEditProducts(inquiry)">Search</button>
                  <button
                    class="ghost-btn"
                    :disabled="!editProductSearch[inquiry.id] && !editProductOptions[inquiry.id]?.length"
                    @click="clearEditProductSearch(inquiry.id)"
                  >
                    Clear
                  </button>
                </div>
                <div v-if="editingInquiryId === inquiry.id && editProductOptions[inquiry.id]?.length" class="option-list">
                  <button
                    v-for="product in editProductOptions[inquiry.id]"
                    :key="product.id"
                    class="option-row"
                    @click="addProductToInquiry(inquiry, product)"
                  >
                    <strong>{{ productLabel(product) }}</strong>
                    <span>{{ product.qty }} in stock - {{ money(product.sale_price, product.currency) }}</span>
                  </button>
                </div>
                <div class="detail-products">
                  <div v-for="(row, productIndex) in inquiry.products" :key="row.id" class="product-token-row">
                    <span class="row-index"><span>{{ productIndex + 1 }}</span></span>
                    <div>
                      <strong>{{ row.product_name }}</strong>
                      <span>{{ row.quantity ?? '-' }} qty - {{ money(row.target_price, row.currency) }}</span>
                    </div>
                    <div class="row-actions">
                      <button class="link-btn" :disabled="busyAction === `auto-${inquiry.id}-${row.product}`" @click="autoAddSuppliers(inquiry, row)">
                        {{ busyAction === `auto-${inquiry.id}-${row.product}` ? 'Finding...' : 'Find suppliers from Inquiry Products' }}
                      </button>
                      <button
                        v-if="editingInquiryId === inquiry.id"
                        class="link-btn danger"
                        :disabled="busyAction === `remove-product-${inquiry.id}-${row.product}`"
                        @click="removeProductFromInquiry(inquiry, row)"
                      >
                        Remove
                      </button>
                    </div>
                  </div>
                </div>
              </div>

              <div>
                <div class="section-title-row compact-title">
                  <h3>Manual Add Supplier</h3>
                </div>
                <div class="select-all-row">
                  <span class="muted">Select all sellers:</span>
                  <button
                    class="link-btn"
                    :disabled="!inquiry.products.length || busyAction === `auto-all-${inquiry.id}`"
                    :title="!inquiry.products.length ? 'Add products first' : 'Exact product match against sell-side inquiries'"
                    @click="autoAddAllSuppliers(inquiry)"
                  >
                    {{ busyAction === `auto-all-${inquiry.id}` ? 'Finding...' : 'Exact Match' }}
                  </button>
                  <button
                    class="link-btn"
                    :disabled="!inquiry.products.length || busyAction === `auto-all-embedding-${inquiry.id}`"
                    :title="!inquiry.products.length ? 'Add products first' : 'Similarity match using product embeddings, catches near-variant wording exact match misses'"
                    @click="autoAddAllSuppliersEmbedding(inquiry)"
                  >
                    {{ busyAction === `auto-all-embedding-${inquiry.id}` ? 'Finding...' : 'Embedded Search' }}
                  </button>
                  <button
                    class="link-btn"
                    :disabled="busyAction === `auto-all-tagged-${inquiry.id}`"
                    title="Every contact tagged Supplier or Both, regardless of inquiry product history"
                    @click="addAllTaggedSuppliers(inquiry)"
                  >
                    {{ busyAction === `auto-all-tagged-${inquiry.id}` ? 'Adding...' : 'Tagged Supplier / Both' }}
                  </button>
                  <button
                    class="link-btn"
                    :disabled="busyAction === `auto-all-tagged-strict-${inquiry.id}`"
                    title="Every contact tagged Supplier only, excludes contacts also tagged Customer (Both)"
                    @click="addAllTaggedSuppliersStrict(inquiry)"
                  >
                    {{ busyAction === `auto-all-tagged-strict-${inquiry.id}` ? 'Adding...' : 'Tagged Supplier' }}
                  </button>
                  <button
                    class="link-btn"
                    :disabled="busyAction === `auto-all-contacted-${inquiry.id}`"
                    title="Every contact previously sent a buying inquiry with the WA button actually clicked, from any other inquiry"
                    @click="addAllPreviouslyContactedSuppliers(inquiry)"
                  >
                    {{ busyAction === `auto-all-contacted-${inquiry.id}` ? 'Adding...' : 'Previously Contacted' }}
                  </button>
                </div>
                <div class="supplier-tools">
                  <input v-model="supplierSearch[inquiry.id]" placeholder="Search supplier name or phone..." @keydown.enter.prevent="searchContacts(inquiry)" />
                  <button class="ghost-btn" @click="searchContacts(inquiry)">Search</button>
                  <button
                    class="ghost-btn"
                    :disabled="!supplierSearch[inquiry.id] && !contactOptions[inquiry.id]?.length"
                    @click="clearContactSearch(inquiry.id)"
                  >
                    Clear
                  </button>
                </div>
                <div v-if="contactOptions[inquiry.id]?.length" class="option-list">
                  <button v-for="contact in contactOptions[inquiry.id]" :key="contact.id" class="option-row" @click="addSupplier(inquiry, contact)">
                    <strong>{{ contactLabel(contact) }}</strong>
                    <span>{{ contact.phone_number || contact.wa_contact_id }} - {{ contact.account_name }}</span>
                  </button>
                </div>
              </div>
            </div>

            <div class="supplier-list-title">
              <div>
                <h3>Suppliers to Ask</h3>
                <p>Saved supplier list for this buying inquiry.</p>
              </div>
              <div class="supplier-list-title-right">
                <span class="muted">{{ inquiry.suppliers.length }} suppliers</span>
                <button
                  class="link-btn danger"
                  :disabled="!inquiry.suppliers.length || busyAction === `remove-all-${inquiry.id}`"
                  @click="removeAllSuppliers(inquiry)"
                >
                  {{ busyAction === `remove-all-${inquiry.id}` ? 'Removing...' : 'Remove All Suppliers' }}
                </button>
              </div>
            </div>
            <div class="detail-supplier-list">
              <div v-if="inquiry.suppliers.length === 0" class="empty-note">No suppliers added yet.</div>
              <div v-for="(supplier, supplierIndex) in inquiry.suppliers" :key="supplier.id" class="supplier-row compact-row">
                <span class="row-index"><span>{{ supplierIndex + 1 }}</span></span>
                <div class="supplier-main">
                  <strong>{{ supplier.contact_name }}</strong>
                  <span>{{ supplier.phone_number || 'No phone' }} - {{ supplier.account_name }} - {{ supplier.source === 'auto' ? 'Auto: WTS inquiry product' : 'Manual add' }}</span>
                </div>
                <span class="notify-pill" :class="{ sent: supplier.sent_count > 0 }">
                  {{ supplier.sent_count > 0 ? `WA pressed ${supplier.sent_count}x` : 'Not notified' }}
                </span>
                <div class="row-actions">
                  <a
                    class="wa-btn"
                    :href="whatsappUrl(supplier.phone_number, inquiryPreview(inquiry))"
                    @click="markSent(inquiry, supplier)"
                  >
                    WA
                  </a>
                  <button
                    class="link-btn danger"
                    :disabled="busyAction === `remove-supplier-${inquiry.id}-${supplier.id}`"
                    @click="removeSupplierFromInquiry(inquiry, supplier)"
                  >
                    Remove
                  </button>
                </div>
              </div>
            </div>

            <div class="detail-actions">
              <button v-if="inquiry.status === 'open'" class="ghost-btn" @click="closeInquiry(inquiry)">Close Inquiry</button>
              <button v-else class="ghost-btn" @click="reopenInquiry(inquiry)">Reopen Inquiry</button>
            </div>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { FontAwesomeIcon } from '@fortawesome/vue-fontawesome'
import { faChevronDown, faChevronRight } from '@fortawesome/free-solid-svg-icons'
import { contactsApi, tradingApi } from '@/api'

const DEFAULT_HEADER = 'Hello, looking to buy:'
const DEFAULT_LINE = '- {product_name} - Qty {qty} - Target {price}'
const DEFAULT_FOOTER = 'Please reply with availability and best price.'

const inquiries = ref([])
const productOptions = ref([])
const expandedInquiries = reactive(new Set())
const supplierSearch = reactive({})
const contactOptions = reactive({})
const editProductSearch = reactive({})
const editProductOptions = reactive({})
const inquirySearch = ref('')
const inquiryPage = ref(1)
const inquiryPageSize = ref(25)
const inquiryTotal = ref(0)
const productSearch = ref('')
const loadingInquiries = ref(false)
const searchingProducts = ref(false)
const savingInquiry = ref(false)
const busyAction = ref('')
const error = ref('')
const editingInquiryId = ref(null)
const editDraft = reactive({
  name: '',
  status: 'open',
  header_template: DEFAULT_HEADER,
  product_line_template: DEFAULT_LINE,
  footer_template: DEFAULT_FOOTER,
})

const draft = reactive({
  name: '',
  status: 'open',
  products: [],
  header_template: DEFAULT_HEADER,
  product_line_template: DEFAULT_LINE,
  footer_template: DEFAULT_FOOTER,
})

const draftPreview = computed(() => formatInquiryMessage({
  header_template: draft.header_template,
  product_line_template: draft.product_line_template,
  footer_template: draft.footer_template,
  products: draft.products.map(product => ({
    product_name: productLabel(product),
    quantity: product.qty,
    target_price: product.sale_price,
    currency: product.currency,
  })),
}))

const inquiryTotalPages = computed(() => Math.max(1, Math.ceil(inquiryTotal.value / inquiryPageSize.value)))
const inquiryRangeText = computed(() => {
  if (!inquiryTotal.value) return 'Showing 0 buying inquiries'
  const start = (inquiryPage.value - 1) * inquiryPageSize.value + 1
  const end = Math.min(start + inquiries.value.length - 1, inquiryTotal.value)
  return `Showing ${start}-${end} of ${inquiryTotal.value}`
})

onMounted(loadInquiries)

async function loadInquiries() {
  loadingInquiries.value = true
  error.value = ''
  try {
    const { data } = await tradingApi.listBuyingInquiries({
      page: inquiryPage.value,
      page_size: inquiryPageSize.value,
      search: inquirySearch.value || undefined,
    })
    inquiries.value = data.results || data
    inquiryTotal.value = data.count ?? inquiries.value.length
  } catch (exc) {
    error.value = apiError(exc, 'Failed to load buying inquiries.')
  } finally {
    loadingInquiries.value = false
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

async function createInquiry() {
  if (!draft.name.trim()) {
    error.value = 'Inquiry name is required.'
    return
  }
  savingInquiry.value = true
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
    const { data } = await tradingApi.createBuyingInquiry(payload)
    inquirySearch.value = ''
    inquiryPage.value = 1
    await loadInquiries()
    expandedInquiries.add(data.id)
    resetDraft()
  } catch (exc) {
    error.value = apiError(exc, 'Create buying inquiry failed.')
  } finally {
    savingInquiry.value = false
  }
}

async function autoAddSuppliers(inquiry, productRow) {
  busyAction.value = `auto-${inquiry.id}-${productRow.product}`
  error.value = ''
  try {
    const { data } = await tradingApi.autoAddBuyingInquirySuppliers(inquiry.id, productRow.product)
    replaceInquiry(data.inquiry)
  } catch (exc) {
    error.value = apiError(exc, 'Auto supplier discovery failed.')
  } finally {
    busyAction.value = ''
  }
}

async function searchContacts(inquiry) {
  const query = supplierSearch[inquiry.id] || ''
  error.value = ''
  try {
    const { data } = await contactsApi.list({ search: query, type: 'phone', page_size: 10 })
    contactOptions[inquiry.id] = data.results || data
  } catch (exc) {
    error.value = apiError(exc, 'Contact search failed.')
  }
}

async function addSupplier(inquiry, contact) {
  error.value = ''
  try {
    await tradingApi.addSupplierToInquiry(inquiry.id, contact.id)
    await refreshInquiry(inquiry.id)
    contactOptions[inquiry.id] = []
    supplierSearch[inquiry.id] = ''
  } catch (exc) {
    error.value = apiError(exc, 'Add supplier failed.')
  }
}

async function autoAddAllSuppliers(inquiry) {
  busyAction.value = `auto-all-${inquiry.id}`
  error.value = ''
  try {
    const { data } = await tradingApi.autoAddAllBuyingInquirySuppliers(inquiry.id)
    replaceInquiry(data.inquiry)
  } catch (exc) {
    error.value = apiError(exc, 'Auto supplier discovery failed.')
  } finally {
    busyAction.value = ''
  }
}

async function autoAddAllSuppliersEmbedding(inquiry) {
  busyAction.value = `auto-all-embedding-${inquiry.id}`
  error.value = ''
  try {
    const { data } = await tradingApi.autoAddAllBuyingInquirySuppliersEmbedding(inquiry.id)
    replaceInquiry(data.inquiry)
  } catch (exc) {
    error.value = apiError(exc, 'Embedded supplier discovery failed.')
  } finally {
    busyAction.value = ''
  }
}

async function addAllTaggedSuppliers(inquiry) {
  busyAction.value = `auto-all-tagged-${inquiry.id}`
  error.value = ''
  try {
    const { data } = await tradingApi.addAllTaggedBuyingInquirySuppliers(inquiry.id)
    replaceInquiry(data.inquiry)
  } catch (exc) {
    error.value = apiError(exc, 'Add tagged suppliers failed.')
  } finally {
    busyAction.value = ''
  }
}

async function addAllTaggedSuppliersStrict(inquiry) {
  busyAction.value = `auto-all-tagged-strict-${inquiry.id}`
  error.value = ''
  try {
    const { data } = await tradingApi.addAllTaggedBuyingInquirySuppliersStrict(inquiry.id)
    replaceInquiry(data.inquiry)
  } catch (exc) {
    error.value = apiError(exc, 'Add tagged suppliers failed.')
  } finally {
    busyAction.value = ''
  }
}

async function addAllPreviouslyContactedSuppliers(inquiry) {
  busyAction.value = `auto-all-contacted-${inquiry.id}`
  error.value = ''
  try {
    const { data } = await tradingApi.addAllPreviouslyContactedBuyingInquirySuppliers(inquiry.id)
    replaceInquiry(data.inquiry)
  } catch (exc) {
    error.value = apiError(exc, 'Add previously contacted suppliers failed.')
  } finally {
    busyAction.value = ''
  }
}

async function removeAllSuppliers(inquiry) {
  if (!window.confirm(`Remove all ${inquiry.suppliers.length} suppliers from "${inquiry.name}"? This cannot be undone.`)) return
  busyAction.value = `remove-all-${inquiry.id}`
  error.value = ''
  try {
    const { data } = await tradingApi.removeAllBuyingInquirySuppliers(inquiry.id)
    replaceInquiry(data.inquiry)
  } catch (exc) {
    error.value = apiError(exc, 'Remove all suppliers failed.')
  } finally {
    busyAction.value = ''
  }
}

async function removeSupplierFromInquiry(inquiry, supplier) {
  busyAction.value = `remove-supplier-${inquiry.id}-${supplier.id}`
  error.value = ''
  try {
    await tradingApi.removeBuyingInquirySupplier(inquiry.id, supplier.id)
    await refreshInquiry(inquiry.id)
  } catch (exc) {
    error.value = apiError(exc, 'Remove supplier failed.')
  } finally {
    busyAction.value = ''
  }
}

async function duplicateInquiry(inquiry) {
  busyAction.value = `duplicate-${inquiry.id}`
  error.value = ''
  try {
    const { data } = await tradingApi.duplicateBuyingInquiry(inquiry.id)
    inquiries.value.unshift(data)
    inquiryTotal.value += 1
    expandedInquiries.add(data.id)
  } catch (exc) {
    error.value = apiError(exc, 'Duplicate inquiry failed.')
  } finally {
    busyAction.value = ''
  }
}

async function deleteInquiry(inquiry) {
  if (!window.confirm(`Delete "${inquiry.name}"? This cannot be undone.`)) return
  busyAction.value = `delete-${inquiry.id}`
  error.value = ''
  try {
    await tradingApi.deleteBuyingInquiry(inquiry.id)
    inquiries.value = inquiries.value.filter(row => row.id !== inquiry.id)
    inquiryTotal.value = Math.max(0, inquiryTotal.value - 1)
    expandedInquiries.delete(inquiry.id)
  } catch (exc) {
    error.value = apiError(exc, 'Delete inquiry failed.')
  } finally {
    busyAction.value = ''
  }
}

function startEditInquiry(inquiry) {
  editingInquiryId.value = inquiry.id
  editDraft.name = inquiry.name
  editDraft.status = inquiry.status
  editDraft.header_template = inquiry.header_template || DEFAULT_HEADER
  editDraft.product_line_template = inquiry.product_line_template || DEFAULT_LINE
  editDraft.footer_template = inquiry.footer_template || DEFAULT_FOOTER
}

function cancelEditInquiry() {
  editingInquiryId.value = null
}

async function saveEditInquiry(inquiry) {
  const name = editDraft.name.trim()
  if (!name) {
    error.value = 'Inquiry name is required.'
    return
  }
  busyAction.value = `save-${inquiry.id}`
  error.value = ''
  try {
    const { data } = await tradingApi.updateBuyingInquiry(inquiry.id, {
      name,
      status: editDraft.status,
      header_template: editDraft.header_template,
      product_line_template: editDraft.product_line_template,
      footer_template: editDraft.footer_template,
    })
    replaceInquiry(data)
    editingInquiryId.value = null
  } catch (exc) {
    error.value = apiError(exc, 'Save inquiry changes failed.')
  } finally {
    busyAction.value = ''
  }
}

async function searchEditProducts(inquiry) {
  error.value = ''
  try {
    const { data } = await tradingApi.listProducts({
      search: editProductSearch[inquiry.id] || '',
      active: 'true',
    })
    editProductOptions[inquiry.id] = (data.results || data).filter(
      product => !inquiry.products.some(row => row.product === product.id),
    )
  } catch (exc) {
    error.value = apiError(exc, 'Product search failed.')
  }
}

function clearEditProductSearch(inquiryId) {
  editProductSearch[inquiryId] = ''
  editProductOptions[inquiryId] = []
}

async function addProductToInquiry(inquiry, product) {
  busyAction.value = `add-product-${inquiry.id}-${product.id}`
  error.value = ''
  try {
    await tradingApi.addBuyingInquiryProduct(inquiry.id, product.id)
    clearEditProductSearch(inquiry.id)
    await refreshInquiry(inquiry.id)
  } catch (exc) {
    error.value = apiError(exc, 'Add product failed.')
  } finally {
    busyAction.value = ''
  }
}

async function removeProductFromInquiry(inquiry, productRow) {
  busyAction.value = `remove-product-${inquiry.id}-${productRow.product}`
  error.value = ''
  try {
    await tradingApi.removeBuyingInquiryProduct(inquiry.id, productRow.product)
    await refreshInquiry(inquiry.id)
  } catch (exc) {
    error.value = apiError(exc, 'Remove product failed.')
  } finally {
    busyAction.value = ''
  }
}

function clearContactSearch(inquiryId) {
  supplierSearch[inquiryId] = ''
  contactOptions[inquiryId] = []
}

async function markSent(inquiry, supplier) {
  try {
    const { data } = await tradingApi.markBuyingInquirySupplierSent(inquiry.id, supplier.id)
    const current = inquiries.value.find(row => row.id === inquiry.id)
    if (!current) return
    const idx = current.suppliers.findIndex(row => row.id === supplier.id)
    if (idx !== -1) current.suppliers[idx] = data
    current.notified_count = current.suppliers.filter(row => row.sent_count > 0).length
  } catch (exc) {
    error.value = apiError(exc, 'Could not record WA press.')
  }
}

async function closeInquiry(inquiry) {
  error.value = ''
  try {
    const { data } = await tradingApi.closeBuyingInquiry(inquiry.id)
    replaceInquiry(data)
  } catch (exc) {
    error.value = apiError(exc, 'Close inquiry failed.')
  }
}

async function reopenInquiry(inquiry) {
  error.value = ''
  try {
    const { data } = await tradingApi.updateBuyingInquiry(inquiry.id, { status: 'open' })
    replaceInquiry(data)
  } catch (exc) {
    error.value = apiError(exc, 'Reopen inquiry failed.')
  }
}

async function refreshInquiry(id) {
  await loadInquiries()
  expandedInquiries.add(id)
}

function replaceInquiry(updated) {
  const idx = inquiries.value.findIndex(row => row.id === updated.id)
  if (idx === -1) inquiries.value.unshift(updated)
  else inquiries.value[idx] = updated
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

function toggleInquiry(id) {
  if (expandedInquiries.has(id)) expandedInquiries.delete(id)
  else expandedInquiries.add(id)
}

function inquiryRowNumber(index) {
  return (inquiryPage.value - 1) * inquiryPageSize.value + index + 1
}

function applyInquirySearch() {
  inquiryPage.value = 1
  loadInquiries()
}

function clearInquirySearch() {
  inquirySearch.value = ''
  inquiryPage.value = 1
  loadInquiries()
}

function goInquiryPage(page) {
  inquiryPage.value = Math.min(Math.max(page, 1), inquiryTotalPages.value)
  loadInquiries()
}

function changeInquiryPageSize() {
  inquiryPage.value = 1
  loadInquiries()
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

function formatInquiryMessage(inquiry) {
  const lines = (inquiry.products || []).map(row => {
    const line = inquiry.product_line_template || DEFAULT_LINE
    return line
      .replaceAll('{product_name}', row.product_name || '')
      .replaceAll('{qty}', row.quantity ?? '-')
      .replaceAll('{price}', money(row.target_price, row.currency))
  })
  return [inquiry.header_template || DEFAULT_HEADER, '', ...lines, '', inquiry.footer_template || DEFAULT_FOOTER].join('\n')
}

function inquiryPreview(inquiry) {
  return formatInquiryMessage(inquiry)
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
.buying-inquiries-view {
  height: 100%;
  overflow-y: auto;
  padding: 24px;
  background: #f8fafc;
  color: #111827;
}
.page-head,
.panel-head,
.section-title-row,
.inquiry-summary,
.supplier-row,
.form-actions,
.detail-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}
.page-head { margin-bottom: 20px; }
.eyebrow {
  margin: 0 0 6px;
  color: #0f766e;
  font-size: 0.72rem;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}
h1, h2, h3, p { margin: 0; }
h1 { font-size: 1.8rem; font-weight: 900; }
h2 { font-size: 1.05rem; font-weight: 850; }
h3 { font-size: 0.9rem; font-weight: 800; }
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
.list-panel { padding: 18px; }
.list-panel { margin-top: 18px; }
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
input, select, textarea {
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
input, select { height: 40px; }
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
.compact-title { margin-bottom: 10px; }
.product-picker,
.supplier-tools {
  display: grid;
  grid-template-columns: 1fr auto auto;
  gap: 8px;
  margin-top: 12px;
}
.list-tools {
  display: grid;
  grid-template-columns: minmax(260px, 1fr) auto auto auto;
  gap: 8px;
  align-items: center;
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px solid #edf2f7;
}
.select-all-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
}
.select-all-row .muted {
  margin-top: 0;
}
.list-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 12px;
  color: #64748b;
  font-size: 0.84rem;
}
.pager {
  display: flex;
  align-items: center;
  gap: 8px;
}
.template-grid,
.product-list,
.inquiry-list,
.detail-supplier-list,
.option-list,
.detail-products {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 12px;
}
.option-row,
.product-row,
.supplier-row,
.inquiry-card,
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
.supplier-main strong,
.inquiry-summary strong,
.option-row strong,
.product-token-row strong {
  display: block;
  color: #111827;
  font-weight: 850;
}
.product-row span,
.supplier-main span,
.inquiry-summary span,
.option-row span,
.product-token-row span,
.muted {
  display: block;
  margin-top: 3px;
  color: #64748b;
  font-size: 0.78rem;
}
.supplier-row {
  padding: 10px 12px;
}
.supplier-main {
  min-width: 0;
  flex: 1;
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
.inquiry-summary {
  width: 100%;
  min-height: 78px;
  padding: 14px 16px;
  border: none;
  background: transparent;
  text-align: left;
  cursor: pointer;
}
.inquiry-right {
  display: flex;
  align-items: center;
  gap: 8px;
}
.inquiry-title-row {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}
.row-index {
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  padding: 0;
  border-radius: 999px;
  background: #f1f5f9;
  color: #475569;
  font-size: 0.76rem;
  font-weight: 850;
  font-variant-numeric: tabular-nums;
  line-height: 1;
  text-align: center;
  vertical-align: middle;
  flex: 0 0 auto;
}
.row-index > span {
  display: block;
  line-height: 1;
  transform: translateY(1px);
}
.caret-btn {
  position: relative;
  display: block;
  width: 30px;
  height: 30px;
  border: 1px solid #dbe4ee;
  border-radius: 999px;
  background: #fff;
  color: #475569;
  flex: 0 0 auto;
}
.caret-btn :deep(svg) {
  display: block;
  position: absolute;
  top: 50%;
  left: 50%;
  width: 11px;
  height: 11px;
  transform: translate(-50%, -50%);
}
.row-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
}
.detail-actions {
  justify-content: flex-end;
  margin-top: 12px;
}
.form-actions {
  justify-content: flex-end;
  margin-top: 18px;
  padding-top: 18px;
  border-top: 1px solid #edf2f7;
}
.inquiry-detail {
  padding: 0 16px 16px;
  border-top: 1px solid #edf2f7;
}
.edit-toolbar {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding-top: 12px;
}
.edit-panel {
  margin-top: 12px;
  padding: 14px;
  border: 1px solid #dbeafe;
  border-radius: 14px;
  background: #f8fbff;
}
.edit-template-grid { margin-top: 12px; }
.inline-picker {
  margin-bottom: 10px;
}
.detail-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
  padding-top: 12px;
}
.supplier-list-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 18px;
  padding-top: 16px;
  border-top: 1px solid #edf2f7;
}
.supplier-list-title p {
  margin-top: 4px;
  color: #64748b;
  font-size: 0.8rem;
}
.supplier-list-title-right {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}
.compact-row {
  border-radius: 12px;
}
.status-chip,
.notify-pill,
.progress-pill,
.edit-pill {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 4px 10px;
  font-size: 0.72rem;
  font-weight: 850;
  white-space: nowrap;
}
.status-chip.open { background: #dcfce7; color: #15803d; }
.status-chip.closed { background: #f1f5f9; color: #64748b; }
.notify-pill { background: #f8fafc; color: #94a3b8; }
.notify-pill.sent { background: #e0f2fe; color: #0369a1; }
.progress-pill { background: #fff7ed; color: #c2410c; }
.edit-pill { background: #eef2ff; color: #4338ca; }
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
.link-btn.danger,
.ghost-btn.danger {
  background: #fff1f2;
  color: #be123c;
  border-color: #fecdd3;
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
  .buying-inquiries-view {
    padding: 16px;
  }
  .page-head,
  .panel-head,
  .section-title-row,
  .inquiry-summary,
  .supplier-row,
  .form-actions {
    align-items: stretch;
    flex-direction: column;
  }
  .form-grid,
  .product-picker,
  .supplier-tools,
  .list-tools {
    grid-template-columns: 1fr;
  }
  .list-meta,
  .pager {
    align-items: stretch;
    flex-direction: column;
  }
  .inquiry-right {
    flex-wrap: wrap;
  }
}
</style>
