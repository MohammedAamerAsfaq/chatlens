<script setup>
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { tradingApi, contactsApi, accountsApi } from '@/api'

const accounts   = ref([])
const inquiries  = ref([])
const loading    = ref(false)

const filterAccount = ref('all')
const filterStatus  = ref('open')

let pollTimer = null

async function fetchAccounts() {
  try {
    const { data } = await accountsApi.list()
    accounts.value = data.results ?? data
  } catch {}
}

async function fetchInquiries(showSpinner = false) {
  if (showSpinner) loading.value = true
  try {
    const params = {}
    if (filterAccount.value !== 'all') params.account = filterAccount.value
    if (filterStatus.value  !== 'all') params.status  = filterStatus.value
    const { data } = await tradingApi.listBuyingInquiries(params)
    inquiries.value = data.results ?? data
  } catch {}
  finally { loading.value = false }
}

onMounted(async () => {
  await fetchAccounts()
  await fetchInquiries(true)
  pollTimer = setInterval(() => fetchInquiries(), 15000)
})
onUnmounted(() => clearInterval(pollTimer))

function refetchOnFilterChange() { fetchInquiries(true) }

// ── Create inquiry ─────────────────────────────────────────────────────────────

const createForm = reactive({
  open: false, account: '', product_name: '', quantity: '', notes: '', saving: false,
})

function openCreate() {
  createForm.open = true
  createForm.account = accounts.value[0]?.id || ''
  createForm.product_name = ''
  createForm.quantity = ''
  createForm.notes = ''
}
function closeCreate() { createForm.open = false }

async function submitCreate() {
  if (!createForm.account || !createForm.product_name.trim()) return
  createForm.saving = true
  try {
    await tradingApi.createBuyingInquiry({
      account: createForm.account,
      product_name: createForm.product_name.trim(),
      quantity: createForm.quantity.trim(),
      notes: createForm.notes.trim(),
    })
    closeCreate()
    await fetchInquiries()
  } finally {
    createForm.saving = false
  }
}

async function toggleInquiryStatus(inquiry) {
  const next = inquiry.status === 'open' ? 'closed' : 'open'
  const { data } = await tradingApi.updateBuyingInquiry(inquiry.id, { status: next })
  inquiry.status = data.status
}

async function deleteInquiry(inquiry) {
  if (!confirm(`Delete buying inquiry "${inquiry.product_name}"? This removes all its supplier cards too.`)) return
  await tradingApi.deleteBuyingInquiry(inquiry.id)
  inquiries.value = inquiries.value.filter(i => i.id !== inquiry.id)
}

// ── Supplier cards ──────────────────────────────────────────────────────────────

function waSupplierLink(inquiry, quote) {
  const clean = (quote.supplier_phone || '').replace(/\D/g, '')
  if (!clean) return null
  let text = inquiry.product_name
  if (inquiry.quantity) text += ` x${inquiry.quantity}`
  if (inquiry.notes) text += `\n${inquiry.notes}`
  text += '\n\nPrice?'
  const params = new URLSearchParams({ phone: clean, text })
  return `whatsapp://send?${params.toString()}`
}

function patchQuote(inquiry, updated) {
  const idx = inquiry.supplier_quotes.findIndex(q => q.id === updated.id)
  if (idx !== -1) inquiry.supplier_quotes[idx] = updated
}

async function askPrice(inquiry, quote) {
  const link = waSupplierLink(inquiry, quote)
  if (!link) return
  window.location.href = link
  try {
    const { data } = await tradingApi.askSupplierQuote(quote.id)
    patchQuote(inquiry, data)
  } catch {}
}

async function markDeclined(inquiry, quote) {
  const { data } = await tradingApi.updateSupplierQuote(quote.id, { status: 'declined' })
  patchQuote(inquiry, data)
}

async function removeSupplier(inquiry, quote) {
  if (!confirm(`Remove ${quote.supplier_name} from this inquiry?`)) return
  await tradingApi.deleteSupplierQuote(quote.id)
  inquiry.supplier_quotes = inquiry.supplier_quotes.filter(q => q.id !== quote.id)
}

// Inline quote-logging form, keyed by supplier_quote id
const quoteForms = reactive({})

function openQuoteForm(quote) {
  quoteForms[quote.id] = {
    open: true,
    price: quote.quoted_price ?? '',
    currency: quote.quoted_currency || 'USD',
    note: quote.quote_note || '',
  }
}
function closeQuoteForm(quote) {
  if (quoteForms[quote.id]) quoteForms[quote.id].open = false
}

async function saveQuoteForm(inquiry, quote) {
  const form = quoteForms[quote.id]
  if (!form) return
  const { data } = await tradingApi.updateSupplierQuote(quote.id, {
    status: 'quoted',
    quoted_price: form.price === '' ? null : form.price,
    quoted_currency: form.currency || 'USD',
    quote_note: form.note,
  })
  patchQuote(inquiry, data)
  form.open = false
}

// ── Add supplier picker ──────────────────────────────────────────────────────────

const addSupplierState = reactive({}) // { [inquiryId]: { open, options, selected, loading } }

async function openAddSupplier(inquiry) {
  const existingIds = new Set(inquiry.supplier_quotes.map(q => q.supplier))
  addSupplierState[inquiry.id] = { open: true, options: [], selected: '', loading: true }
  try {
    const { data } = await contactsApi.list({ account: inquiry.account, page_size: 200 })
    const results = data.results ?? data
    addSupplierState[inquiry.id].options = results.filter(c =>
      ((c.role_tags || []).includes('supplier') || ['supplier', 'both'].includes(c.role_category || c.category)) && !existingIds.has(c.id)
    )
  } finally {
    addSupplierState[inquiry.id].loading = false
  }
}
function closeAddSupplier(inquiry) {
  if (addSupplierState[inquiry.id]) addSupplierState[inquiry.id].open = false
}

async function confirmAddSupplier(inquiry) {
  const st = addSupplierState[inquiry.id]
  if (!st?.selected) return
  const { data } = await tradingApi.addSupplierToInquiry(inquiry.id, st.selected)
  inquiry.supplier_quotes.push(data)
  st.open = false
}

// ── Display helpers ──────────────────────────────────────────────────────────────

const STATUS_LABEL = {
  not_asked: 'Not Asked',
  asked: 'Asked',
  quoted: 'Quoted',
  declined: 'Declined / No Stock',
}
const STATUS_STYLE = {
  not_asked: 'bg-gray-100 text-gray-500',
  asked: 'bg-yellow-100 text-yellow-700',
  quoted: 'bg-green-100 text-green-700',
  declined: 'bg-red-100 text-red-700',
}

function relativeTime(dt) {
  if (!dt) return ''
  const diff = Math.floor((Date.now() - new Date(dt)) / 1000)
  if (diff < 60)    return `${diff}s ago`
  if (diff < 3600)  return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  return `${Math.floor(diff / 86400)}d ago`
}

const filteredCount = computed(() => inquiries.value.length)
</script>

<template>
  <div class="h-full w-full overflow-y-auto bg-gray-50">
  <div class="max-w-7xl mx-auto px-6 py-6">

    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-2xl font-bold text-gray-900">Buying Inquiries</h1>
        <p class="text-sm text-gray-500 mt-1">Shop a purchase request around your tagged suppliers and track who quoted what</p>
      </div>
      <button
        @click="openCreate"
        class="px-4 py-2 bg-green-600 hover:bg-green-700 text-white text-sm font-medium rounded-lg transition-colors"
      >+ New Buying Inquiry</button>
    </div>

    <!-- Filters -->
    <div class="flex items-center gap-3 mb-4 flex-wrap">
      <select
        v-model="filterAccount" @change="refetchOnFilterChange"
        class="border border-gray-200 rounded-lg px-3 py-1.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-green-500 min-w-[160px]"
      >
        <option value="all">All accounts</option>
        <option v-for="acc in accounts" :key="acc.id" :value="acc.id">
          {{ acc.display_name || acc.phone_number || `Account #${acc.id}` }}
        </option>
      </select>

      <select
        v-model="filterStatus" @change="refetchOnFilterChange"
        class="border border-gray-200 rounded-lg px-3 py-1.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-green-500"
      >
        <option value="open">Open</option>
        <option value="closed">Closed</option>
        <option value="all">All</option>
      </select>

      <span class="text-sm text-gray-400">{{ filteredCount }} inquiries</span>
    </div>

    <!-- Loading / empty -->
    <div v-if="loading" class="text-center text-gray-400 py-12 text-sm">Loading…</div>
    <div v-else-if="inquiries.length === 0" class="text-center text-gray-400 py-12 text-sm">
      No buying inquiries yet — click "+ New Buying Inquiry" to start one.
    </div>

    <!-- Inquiry cards -->
    <div v-else class="flex flex-col gap-5">
      <div v-for="inquiry in inquiries" :key="inquiry.id" class="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">

        <!-- Inquiry header -->
        <div class="flex items-start justify-between px-5 py-4 border-b border-gray-100 flex-wrap gap-2">
          <div>
            <div class="flex items-center gap-2 flex-wrap">
              <h2 class="text-base font-semibold text-gray-900">{{ inquiry.product_name }}</h2>
              <span v-if="inquiry.quantity" class="text-xs text-gray-500">× {{ inquiry.quantity }}</span>
              <span :class="['text-xs font-medium px-2 py-0.5 rounded-full', inquiry.status === 'open' ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-500']">
                {{ inquiry.status === 'open' ? 'Open' : 'Closed' }}
              </span>
            </div>
            <p v-if="inquiry.notes" class="text-sm text-gray-500 mt-1 whitespace-pre-wrap">{{ inquiry.notes }}</p>
            <p class="text-xs text-gray-400 mt-1">{{ inquiry.account_name }}</p>
          </div>
          <div class="flex items-center gap-2 shrink-0">
            <button
              @click="toggleInquiryStatus(inquiry)"
              class="text-xs px-3 py-1.5 rounded-lg border border-gray-200 hover:bg-gray-50 transition-colors text-gray-600"
            >{{ inquiry.status === 'open' ? 'Close' : 'Reopen' }}</button>
            <button
              @click="deleteInquiry(inquiry)"
              class="text-xs px-3 py-1.5 rounded-lg border border-red-200 text-red-600 hover:bg-red-50 transition-colors"
            >Delete</button>
          </div>
        </div>

        <!-- Supplier cards grid -->
        <div class="p-5">
          <div v-if="inquiry.supplier_quotes.length === 0" class="text-sm text-gray-400 mb-3">
            No suppliers tagged yet — tag contacts as "Supplier" on the Contacts page, or add one below.
          </div>

          <div class="grid gap-3" style="grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));">
            <div
              v-for="quote in inquiry.supplier_quotes" :key="quote.id"
              class="border border-gray-200 rounded-lg p-3 flex flex-col gap-2"
            >
              <div class="flex items-center justify-between gap-2">
                <span class="text-sm font-medium text-gray-800 truncate">{{ quote.supplier_name }}</span>
                <span :class="['text-[10px] font-semibold px-2 py-0.5 rounded-full shrink-0', STATUS_STYLE[quote.status]]">
                  {{ STATUS_LABEL[quote.status] }}
                </span>
              </div>
              <span class="text-xs font-mono text-gray-400">{{ quote.supplier_phone ? `+${quote.supplier_phone}` : '—' }}</span>

              <span v-if="quote.status === 'asked'" class="text-xs text-gray-400">Asked {{ relativeTime(quote.asked_at) }}</span>
              <div v-if="quote.status === 'quoted'" class="text-sm font-semibold text-green-700">
                {{ quote.quoted_currency }} {{ quote.quoted_price }}
                <div v-if="quote.quote_note" class="text-xs font-normal text-gray-500 mt-0.5">{{ quote.quote_note }}</div>
              </div>

              <!-- Inline quote-logging form -->
              <div v-if="quoteForms[quote.id]?.open" class="flex flex-col gap-1.5 mt-1 border-t border-gray-100 pt-2">
                <div class="flex gap-1.5">
                  <input v-model="quoteForms[quote.id].currency" placeholder="USD" class="w-16 text-xs border border-gray-200 rounded px-1.5 py-1" />
                  <input v-model.number="quoteForms[quote.id].price" type="number" step="0.01" placeholder="Price" class="flex-1 text-xs border border-gray-200 rounded px-1.5 py-1 min-w-0" />
                </div>
                <input v-model="quoteForms[quote.id].note" placeholder="Note (optional)" class="text-xs border border-gray-200 rounded px-1.5 py-1" />
                <div class="flex gap-1.5">
                  <button @click="saveQuoteForm(inquiry, quote)" class="flex-1 text-xs bg-green-600 hover:bg-green-700 text-white rounded py-1">Save</button>
                  <button @click="closeQuoteForm(quote)" class="text-xs px-2 border border-gray-200 rounded py-1 text-gray-500 hover:bg-gray-50">✕</button>
                </div>
              </div>

              <!-- Action row -->
              <div v-else class="flex items-center gap-1.5 mt-1 flex-wrap">
                <a
                  v-if="waSupplierLink(inquiry, quote)"
                  @click.prevent="askPrice(inquiry, quote)"
                  href="#"
                  class="flex items-center gap-1 text-xs px-2 py-1 rounded bg-green-50 text-green-700 hover:bg-green-100 transition-colors"
                >
                  <svg viewBox="0 0 24 24" fill="currentColor" width="11" height="11"><path d="M12.04 2C6.58 2 2.13 6.45 2.13 11.91c0 1.75.46 3.45 1.32 4.95L2.05 22l5.25-1.38c1.45.79 3.08 1.21 4.74 1.21 5.46 0 9.91-4.45 9.91-9.91S17.5 2 12.04 2zm4.82 13.68c-.2.56-1.18 1.07-1.62 1.14-.44.07-.98.1-1.58-.1-.36-.12-.83-.28-1.42-.55-2.5-1.08-4.13-3.6-4.26-3.77-.13-.17-1.05-1.4-1.05-2.67 0-1.27.66-1.9.9-2.16.23-.26.5-.32.67-.32.17 0 .33 0 .48.01.15.01.36-.06.56.43.2.49.7 1.7.76 1.82.06.13.1.27.02.43-.08.17-.12.27-.23.41-.11.14-.24.31-.33.42-.11.13-.23.27-.1.53.13.26.59 1 1.27 1.63.87.8 1.61 1.04 1.87 1.16.26.12.41.1.57-.06.16-.16.66-.77.83-1.04.17-.26.34-.22.57-.13.23.09 1.44.68 1.69.8.25.12.41.18.47.28.07.1.07.56-.13 1.12z"/></svg>
                  {{ quote.status === 'not_asked' ? 'Ask Price' : 'Ask Again' }}
                </a>
                <button @click="openQuoteForm(quote)" class="text-xs px-2 py-1 rounded bg-blue-50 text-blue-700 hover:bg-blue-100 transition-colors">Log Quote</button>
                <button v-if="quote.status !== 'declined'" @click="markDeclined(inquiry, quote)" class="text-xs px-2 py-1 rounded bg-gray-50 text-gray-500 hover:bg-gray-100 transition-colors">No Stock</button>
                <button @click="removeSupplier(inquiry, quote)" class="text-xs px-1.5 py-1 rounded text-red-400 hover:bg-red-50 transition-colors ml-auto" title="Remove">✕</button>
              </div>
            </div>
          </div>

          <!-- Add supplier -->
          <div class="mt-4">
            <button
              v-if="!addSupplierState[inquiry.id]?.open"
              @click="openAddSupplier(inquiry)"
              class="text-xs px-3 py-1.5 rounded-lg border border-dashed border-gray-300 text-gray-500 hover:bg-gray-50 transition-colors"
            >+ Add supplier</button>
            <div v-else class="flex items-center gap-2 flex-wrap">
              <select v-model="addSupplierState[inquiry.id].selected" class="text-sm border border-gray-200 rounded-lg px-2 py-1.5 min-w-[200px]">
                <option value="" disabled>{{ addSupplierState[inquiry.id].loading ? 'Loading…' : 'Select a supplier…' }}</option>
                <option v-for="c in addSupplierState[inquiry.id].options" :key="c.id" :value="c.id">
                  {{ c.display_name || c.push_name || c.phone_number }}
                </option>
              </select>
              <button @click="confirmAddSupplier(inquiry)" class="text-xs px-3 py-1.5 rounded-lg bg-green-600 hover:bg-green-700 text-white transition-colors">Add</button>
              <button @click="closeAddSupplier(inquiry)" class="text-xs px-3 py-1.5 rounded-lg border border-gray-200 text-gray-500 hover:bg-gray-50 transition-colors">Cancel</button>
              <span v-if="!addSupplierState[inquiry.id].loading && addSupplierState[inquiry.id].options.length === 0" class="text-xs text-gray-400">
                No more suppliers tagged for this account — tag more on the Contacts page.
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
  </div>

  <!-- Create modal -->
  <Teleport to="body">
    <div v-if="createForm.open" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" @click.self="closeCreate">
      <div class="bg-white rounded-xl shadow-xl w-full max-w-md p-6 flex flex-col gap-3">
        <h2 class="text-lg font-semibold text-gray-900">New Buying Inquiry</h2>

        <div class="flex flex-col gap-1">
          <label class="text-xs font-medium text-gray-600">Account</label>
          <select v-model="createForm.account" class="border border-gray-200 rounded-lg px-3 py-2 text-sm">
            <option v-for="acc in accounts" :key="acc.id" :value="acc.id">
              {{ acc.display_name || acc.phone_number || `Account #${acc.id}` }}
            </option>
          </select>
        </div>

        <div class="flex flex-col gap-1">
          <label class="text-xs font-medium text-gray-600">Product *</label>
          <input v-model="createForm.product_name" placeholder="iPhone 17 Pro Max 256GB" class="border border-gray-200 rounded-lg px-3 py-2 text-sm" />
        </div>

        <div class="flex flex-col gap-1">
          <label class="text-xs font-medium text-gray-600">Quantity</label>
          <input v-model="createForm.quantity" placeholder="50 units" class="border border-gray-200 rounded-lg px-3 py-2 text-sm" />
        </div>

        <div class="flex flex-col gap-1">
          <label class="text-xs font-medium text-gray-600">Notes</label>
          <textarea v-model="createForm.notes" rows="2" placeholder="Any colors/regions/conditions to mention" class="border border-gray-200 rounded-lg px-3 py-2 text-sm resize-vertical"></textarea>
        </div>

        <p class="text-xs text-gray-400">All contacts currently tagged "Supplier" on this account will be added as cards automatically.</p>

        <div class="flex justify-end gap-2 mt-2">
          <button @click="closeCreate" class="px-4 py-2 text-sm border border-gray-200 rounded-lg text-gray-600 hover:bg-gray-50 transition-colors">Cancel</button>
          <button
            @click="submitCreate"
            :disabled="createForm.saving || !createForm.account || !createForm.product_name.trim()"
            class="px-4 py-2 text-sm bg-green-600 hover:bg-green-700 disabled:opacity-50 text-white rounded-lg transition-colors"
          >{{ createForm.saving ? 'Creating…' : 'Create' }}</button>
        </div>
      </div>
    </div>
  </Teleport>
</template>
