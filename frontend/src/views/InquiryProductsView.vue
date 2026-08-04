<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { accountsApi, tradingApi } from '@/api'
import { useConversationsStore } from '@/stores/conversations'

const router = useRouter()
const conversations = useConversationsStore()
const rows = ref([])
const accounts = ref([])
const loading = ref(false)
const error = ref('')
const total = ref(0)
const page = ref(1)
const pageSize = ref(25)
const pageSizeOptions = [25, 50, 100]
const ordering = ref('created_newest')
const detailRow = ref(null)
const smartQuery = ref('')
const smartSearching = ref(false)
const smartSearched = ref(false)
const smartResults = ref([])
const smartError = ref('')
let requestSeq = 0
let searchTimer = null

const filters = ref({
  account: '',
  type: '',
  decision_status: '',
  match_status: '',
  embedding_status: '',
  product_state: '',
  search: '',
  date: '',
})

const mappedCount = computed(() => rows.value.filter(r => r.product).length)
const pendingCount = computed(() => rows.value.filter(r => r.decision_status === 'pending').length)
const unmatchedCount = computed(() => rows.value.filter(r => r.match_status === 'unmatched').length)
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))
const pageStart = computed(() => total.value === 0 ? 0 : (page.value - 1) * pageSize.value + 1)
const pageEnd = computed(() => Math.min(page.value * pageSize.value, total.value))

function params() {
  const p = { page: page.value, page_size: pageSize.value, ordering: ordering.value }
  for (const [key, value] of Object.entries(filters.value)) {
    if (value !== '') p[key] = value
  }
  return p
}

async function load() {
  const seq = ++requestSeq
  loading.value = true
  error.value = ''
  try {
    const { data } = await tradingApi.listInquiryProducts(params())
    if (seq !== requestSeq) return
    rows.value = data.results ?? data
    total.value = data.count ?? rows.value.length
  } catch (err) {
    if (seq !== requestSeq) return
    error.value = err.response?.data?.detail || err.message || 'Failed to load inquiry products'
  } finally {
    if (seq === requestSeq) loading.value = false
  }
}

async function loadAccounts() {
  const { data } = await accountsApi.list()
  accounts.value = data.results ?? data
}

function smartSearchParams(query) {
  const p = { q: query, top_k: 20 }
  for (const key of ['account', 'type', 'decision_status', 'match_status', 'embedding_status', 'product_state', 'date']) {
    const value = filters.value[key]
    if (value !== '') p[key] = value
  }
  return p
}

async function runSmartSearch() {
  const q = smartQuery.value.trim()
  if (!q) return
  smartSearching.value = true
  smartError.value = ''
  try {
    const { data } = await tradingApi.searchInquiryProductEmbeddings(smartSearchParams(q))
    smartResults.value = data.results || []
    smartSearched.value = true
  } catch (err) {
    smartError.value = err.response?.data?.detail || err.message || 'Smart search failed'
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

function resetFilters() {
  filters.value = {
    account: '',
    type: '',
    decision_status: '',
    match_status: '',
    embedding_status: '',
    product_state: '',
    search: '',
    date: '',
  }
  clearSmartSearch()
  page.value = 1
  load()
}

function formatTime(value) {
  if (!value) return '-'
  return new Date(value).toLocaleString()
}

function statusClass(value) {
  const base = 'text-xs font-medium px-2 py-0.5 rounded-full capitalize '
  const classes = {
    pending: 'bg-amber-100 text-amber-700',
    mapped: 'bg-green-100 text-green-700',
    created: 'bg-green-100 text-green-700',
    dismissed: 'bg-gray-100 text-gray-500',
    exact: 'bg-green-100 text-green-700',
    near: 'bg-amber-100 text-amber-700',
    unmatched: 'bg-red-100 text-red-700',
    manual_confirmed: 'bg-green-100 text-green-700',
    rejected: 'bg-gray-100 text-gray-500',
    embedded: 'bg-green-100 text-green-700',
    error: 'bg-red-100 text-red-700',
    skipped: 'bg-gray-100 text-gray-500',
  }
  return base + (classes[value] || 'bg-gray-100 text-gray-500')
}

function directionClass(value) {
  const base = 'text-xs font-medium px-2 py-0.5 rounded-full capitalize '
  const classes = {
    buy: 'bg-green-100 text-green-700',
    sell: 'bg-amber-100 text-amber-700',
    both: 'bg-blue-100 text-blue-700',
  }
  return base + (classes[value] || 'bg-gray-100 text-gray-500')
}

function openDetail(row) {
  detailRow.value = row
}

function closeDetail() {
  detailRow.value = null
}

async function viewChat(row) {
  if (!row?.source_chat_id) return
  if (row.account && conversations.selectedAccountId !== row.account) {
    await conversations.switchAccount(row.account)
  }
  conversations.selectChat(row.source_chat_id, {
    messageId: row.source_message,
    messageTime: row.source_message_time,
  })
  router.push({ name: 'conversations' })
}

onMounted(async () => {
  await Promise.all([loadAccounts(), load()])
})

watch(
  () => [
    filters.value.account,
    filters.value.type,
    filters.value.decision_status,
    filters.value.match_status,
    filters.value.embedding_status,
    filters.value.product_state,
    filters.value.date,
    pageSize.value,
    ordering.value,
  ],
  () => {
    page.value = 1
    load()
  },
)

watch(page, () => load())

watch(() => filters.value.search, () => {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    page.value = 1
    load()
  }, 300)
})
</script>

<template>
  <div class="h-full w-full overflow-y-auto bg-gray-50">
    <div class="max-w-7xl mx-auto px-6 py-6">
      <div class="mb-6 flex items-start justify-between gap-4">
        <div>
          <h1 class="text-2xl font-bold text-gray-900">Inquiry Products</h1>
          <p class="text-sm text-gray-500 mt-1">Check product lines extracted from inquiry messages</p>
        </div>
        <button
          class="px-4 py-2 rounded-lg bg-green-600 text-white text-sm font-semibold hover:bg-green-700 disabled:opacity-50 transition-colors"
          :disabled="loading"
          @click="load"
        >
          {{ loading ? 'Loading...' : 'Refresh' }}
        </button>
      </div>

      <div class="flex items-center gap-6 mb-6 bg-white rounded-xl border border-gray-200 px-6 py-4 shadow-sm flex-wrap">
        <div>
          <p class="text-xs text-gray-400 uppercase tracking-wide">Total</p>
          <p class="text-xl font-bold text-gray-900">{{ total.toLocaleString() }}</p>
        </div>
        <div class="w-px h-8 bg-gray-100"></div>
        <div>
          <p class="text-xs text-amber-500 uppercase tracking-wide">Pending</p>
          <p class="text-xl font-bold text-gray-900">{{ pendingCount.toLocaleString() }}</p>
        </div>
        <div class="w-px h-8 bg-gray-100"></div>
        <div>
          <p class="text-xs text-green-500 uppercase tracking-wide">Mapped</p>
          <p class="text-xl font-bold text-gray-900">{{ mappedCount.toLocaleString() }}</p>
        </div>
        <div class="w-px h-8 bg-gray-100"></div>
        <div>
          <p class="text-xs text-red-500 uppercase tracking-wide">Unmatched</p>
          <p class="text-xl font-bold text-gray-900">{{ unmatchedCount.toLocaleString() }}</p>
        </div>
      </div>

      <div class="flex items-center gap-3 mb-4 flex-wrap">
        <div class="relative flex-1 min-w-[260px]">
          <svg class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-4.35-4.35M17 11A6 6 0 1 1 5 11a6 6 0 0 1 12 0z"/>
          </svg>
          <input
            v-model="filters.search"
            class="w-full pl-9 pr-3 py-1.5 text-sm border border-gray-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-green-500"
            placeholder="Search product, message, contact..."
            @keydown.enter="load"
          />
        </div>
        <select v-model="filters.account" class="filter-control min-w-[160px]">
          <option value="">All accounts</option>
          <option v-for="account in accounts" :key="account.id" :value="account.id">
            {{ account.display_name || account.phone_number || `Account ${account.id}` }}
          </option>
        </select>
        <select v-model="filters.type" class="filter-control">
          <option value="">All directions</option>
          <option value="buy">WTB / Buy</option>
          <option value="sell">WTS / Sell</option>
          <option value="both">Both</option>
        </select>
        <select v-model="filters.decision_status" class="filter-control">
          <option value="">All decisions</option>
          <option value="pending">Pending</option>
          <option value="mapped">Mapped</option>
          <option value="created">Created</option>
          <option value="dismissed">Dismissed</option>
        </select>
        <select v-model="filters.match_status" class="filter-control">
          <option value="">All matches</option>
          <option value="exact">Exact</option>
          <option value="near">Near</option>
          <option value="unmatched">Unmatched</option>
          <option value="manual_confirmed">Manual confirmed</option>
          <option value="rejected">Rejected</option>
        </select>
        <select v-model="filters.product_state" class="filter-control">
          <option value="">Mapped + unmapped</option>
          <option value="mapped">Mapped only</option>
          <option value="unmapped">Unmapped only</option>
        </select>
        <select v-model="filters.embedding_status" class="filter-control">
          <option value="">All embeddings</option>
          <option value="pending">Pending</option>
          <option value="embedded">Embedded</option>
          <option value="error">Error</option>
          <option value="skipped">Skipped</option>
        </select>
        <input v-model="filters.date" type="date" class="filter-control" />
        <select v-model="ordering" class="filter-control min-w-[190px]">
          <option value="created_newest">Newest product created</option>
          <option value="created_oldest">Oldest product created</option>
          <option value="seen_newest">Latest inquiry first</option>
          <option value="seen_oldest">Oldest inquiry first</option>
          <option value="name_asc">Product name A-Z</option>
          <option value="name_desc">Product name Z-A</option>
          <option value="decision">Decision status</option>
          <option value="match">Match status</option>
        </select>
        <button class="px-3 py-1.5 rounded-lg border border-gray-200 text-sm bg-white text-gray-500 hover:bg-gray-50 transition-colors" @click="resetFilters">Reset</button>
      </div>

      <div class="mb-4 rounded-xl border border-green-100 bg-white px-4 py-4 shadow-sm">
        <div class="flex items-center gap-3 flex-wrap">
          <div class="flex items-center justify-center w-8 h-8 rounded-full bg-green-50 text-green-700 font-bold">*</div>
          <div class="relative flex-1 min-w-[280px]">
            <input
              v-model="smartQuery"
              class="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-green-500"
              placeholder="Smart Search extracted products by meaning, any phrasing or word order..."
              @keydown.enter="runSmartSearch"
            />
          </div>
          <button
            class="px-4 py-2 rounded-lg bg-green-600 text-white text-sm font-semibold hover:bg-green-700 disabled:opacity-50 transition-colors"
            :disabled="smartSearching || !smartQuery.trim()"
            @click="runSmartSearch"
          >
            {{ smartSearching ? 'Searching...' : 'Smart Search' }}
          </button>
          <button
            v-if="smartSearched"
            class="px-3 py-2 rounded-lg border border-gray-200 text-sm bg-white text-gray-500 hover:bg-gray-50 transition-colors"
            @click="clearSmartSearch"
          >
            Clear
          </button>
        </div>

        <p class="text-xs text-gray-500 mt-2">
          Uses Inquiry Product embeddings and respects the current account/status/date filters. Plain text search above remains unchanged.
        </p>
        <div v-if="smartError" class="mt-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{{ smartError }}</div>

        <div v-if="smartSearched" class="mt-4">
          <div v-if="!smartResults.length" class="text-sm text-gray-400 py-4">No smart matches found.</div>
          <div v-else class="overflow-x-auto rounded-lg border border-gray-100">
            <table class="w-full text-sm min-w-[980px]">
              <thead>
                <tr class="bg-gray-50 border-b border-gray-100 text-xs text-gray-500 uppercase tracking-wide">
                  <th class="text-left px-4 py-3">Product Line</th>
                  <th class="text-left px-4 py-3 w-24">Match</th>
                  <th class="text-left px-4 py-3 w-24">Direction</th>
                  <th class="text-left px-4 py-3 w-48">Contact</th>
                  <th class="text-left px-4 py-3 w-56">Inventory Match</th>
                  <th class="text-left px-4 py-3 w-64">Source</th>
                  <th class="text-left px-4 py-3 w-28"></th>
                </tr>
              </thead>
              <tbody class="divide-y divide-gray-50">
                <tr v-for="result in smartResults" :key="result.inquiry_product.id" class="hover:bg-gray-50 transition-colors">
                  <td class="px-4 py-3 align-top">
                    <div class="font-semibold text-gray-900">{{ result.inquiry_product.canonical_name }}</div>
                    <div class="text-xs text-gray-400 mt-0.5">#{{ result.inquiry_product.id }} - index {{ result.inquiry_product.source_product_index ?? '-' }}</div>
                  </td>
                  <td class="px-4 py-3 align-top">
                    <span class="text-xs font-semibold px-2 py-0.5 rounded-full bg-blue-50 text-blue-700">
                      ~{{ Math.round((1 - result.distance) * 100) }}%
                    </span>
                    <div class="text-xs text-gray-400 mt-1">distance {{ result.distance }}</div>
                  </td>
                  <td class="px-4 py-3 align-top">
                    <span :class="directionClass(result.inquiry_product.inquiry_type)">{{ result.inquiry_product.inquiry_type || '-' }}</span>
                  </td>
                  <td class="px-4 py-3 align-top">
                    <div class="font-medium text-gray-900 truncate max-w-[180px]">{{ result.inquiry_product.contact_name || 'Unknown' }}</div>
                    <div class="text-xs text-gray-500 mt-0.5">{{ result.inquiry_product.contact_phone || result.inquiry_product.account_name || '-' }}</div>
                  </td>
                  <td class="px-4 py-3 align-top">
                    <div v-if="result.inquiry_product.product" class="font-medium text-gray-900">{{ result.inquiry_product.product_name }}</div>
                    <div v-else class="text-xs text-red-600">No inventory product mapped</div>
                  </td>
                  <td class="px-4 py-3 align-top">
                    <div class="text-xs text-gray-400">{{ formatTime(result.inquiry_product.source_message_time || result.inquiry_product.first_seen_at) }}</div>
                    <div class="text-xs text-gray-700 mt-1 max-w-[280px] max-h-10 overflow-hidden leading-snug">{{ result.inquiry_product.source_message_text || '-' }}</div>
                  </td>
                  <td class="px-4 py-3 align-top">
                    <button class="text-xs text-green-700 font-semibold hover:text-green-800" @click="openDetail(result.inquiry_product)">View details</button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <div class="flex items-center justify-between mb-4 gap-3 flex-wrap">
        <div class="text-xs text-gray-500">
          Showing {{ pageStart.toLocaleString() }}-{{ pageEnd.toLocaleString() }} of {{ total.toLocaleString() }}
        </div>
        <div class="flex items-center gap-3">
          <div class="inline-flex border border-gray-200 rounded-lg overflow-hidden bg-white">
            <button
              v-for="n in pageSizeOptions"
              :key="n"
              @click="pageSize = n"
              :class="['px-2.5 py-1 text-xs transition-colors', pageSize === n ? 'bg-green-600 text-white' : 'hover:bg-gray-50 text-gray-600']"
            >
              {{ n }}
            </button>
          </div>
          <div class="inline-flex items-center border border-gray-200 rounded-lg overflow-hidden bg-white text-gray-600">
            <button
              class="px-3 py-1.5 text-xs hover:bg-gray-50 disabled:opacity-40"
              :disabled="page <= 1 || loading"
              @click="page--"
            >
              Previous
            </button>
            <span class="px-3 py-1.5 text-xs border-x border-gray-200">Page {{ page }} of {{ totalPages }}</span>
            <button
              class="px-3 py-1.5 text-xs hover:bg-gray-50 disabled:opacity-40"
              :disabled="page >= totalPages || loading"
              @click="page++"
            >
              Next
            </button>
          </div>
        </div>
      </div>

      <div v-if="error" class="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{{ error }}</div>

      <div class="bg-white rounded-xl border border-gray-200 overflow-hidden shadow-sm">
        <div v-if="loading" class="text-center text-gray-400 py-12 text-sm">Loading inquiry products...</div>
        <div v-else-if="!rows.length" class="text-center text-gray-400 py-12 text-sm">No inquiry product rows found.</div>
        <div v-else class="overflow-x-auto">
          <table class="w-full text-sm min-w-[1180px]">
            <thead>
              <tr class="bg-gray-50 border-b border-gray-100 text-xs text-gray-500 uppercase tracking-wide">
                <th class="text-left px-4 py-3">Product Line</th>
                <th class="text-left px-4 py-3 w-24">Direction</th>
                <th class="text-left px-4 py-3 w-48">Contact</th>
                <th class="text-left px-4 py-3 w-56">Inventory Match</th>
                <th class="text-left px-4 py-3 w-28">Decision</th>
                <th class="text-left px-4 py-3 w-40">Match</th>
                <th class="text-left px-4 py-3 w-32">Embedding</th>
                <th class="text-left px-4 py-3 w-80">Source</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-50">
              <tr v-for="row in rows" :key="row.id" class="hover:bg-gray-50 transition-colors">
                <td class="px-4 py-3 align-top">
                  <div class="font-semibold text-gray-900">{{ row.canonical_name }}</div>
                  <div class="text-xs text-gray-400 mt-0.5">#{{ row.id }} - index {{ row.source_product_index ?? '-' }}</div>
                  <div v-if="row.quantity || row.price" class="text-xs text-gray-500 mt-0.5">
                    Qty: {{ row.quantity ?? '-' }}
                    <span v-if="row.price"> - {{ row.currency || '' }} {{ row.price }}</span>
                  </div>
                </td>
                <td class="px-4 py-3 align-top">
                  <span :class="directionClass(row.inquiry_type)">{{ row.inquiry_type || '-' }}</span>
                </td>
                <td class="px-4 py-3 align-top">
                  <div class="font-medium text-gray-900 truncate max-w-[180px]">{{ row.contact_name || 'Unknown' }}</div>
                  <div class="text-xs text-gray-500 mt-0.5">{{ row.contact_phone || row.account_name || '-' }}</div>
                </td>
                <td class="px-4 py-3 align-top">
                  <div v-if="row.product" class="font-medium text-gray-900">{{ row.product_name }}</div>
                  <div v-else class="text-xs text-red-600">No inventory product mapped</div>
                </td>
                <td class="px-4 py-3 align-top"><span :class="statusClass(row.decision_status)">{{ row.decision_status }}</span></td>
                <td class="px-4 py-3 align-top">
                  <span :class="statusClass(row.match_status)">{{ row.match_status }}</span>
                  <div v-if="row.match_source" class="text-xs text-gray-400 mt-0.5">{{ row.match_source }}</div>
                  <div v-if="row.match_reason" class="text-xs text-gray-500 mt-1 max-w-[240px] leading-snug">{{ row.match_reason }}</div>
                </td>
                <td class="px-4 py-3 align-top">
                  <span :class="statusClass(row.embedding_status)">{{ row.embedding_status }}</span>
                  <div v-if="row.embedding_model" class="text-xs text-gray-400 mt-0.5">{{ row.embedding_model }}</div>
                  <div v-if="row.embedding_error" class="text-xs text-red-600 mt-1 max-w-[220px] leading-snug">{{ row.embedding_error }}</div>
                </td>
                <td class="px-4 py-3 align-top">
                  <div class="text-xs text-gray-400">{{ formatTime(row.source_message_time || row.first_seen_at) }}</div>
                  <div class="text-xs text-gray-700 mt-1 max-w-[340px] max-h-12 overflow-hidden leading-snug">{{ row.source_message_text || '-' }}</div>
                  <div class="flex items-center gap-3 mt-1">
                    <button class="text-xs text-green-700 font-semibold hover:text-green-800" @click="openDetail(row)">View details</button>
                    <button
                      v-if="row.source_chat_id"
                      class="text-xs text-blue-700 font-semibold hover:text-blue-800"
                      @click="viewChat(row)"
                    >
                      Chat →
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div class="flex items-center justify-between mt-4 gap-3 flex-wrap text-xs text-gray-500">
        <span>Showing {{ pageStart.toLocaleString() }}-{{ pageEnd.toLocaleString() }} of {{ total.toLocaleString() }}</span>
        <div class="inline-flex items-center border border-gray-200 rounded-lg overflow-hidden bg-white text-gray-600">
          <button
            class="px-3 py-1.5 hover:bg-gray-50 disabled:opacity-40"
            :disabled="page <= 1 || loading"
            @click="page--"
          >
            Previous
          </button>
          <span class="px-3 py-1.5 border-x border-gray-200">Page {{ page }} of {{ totalPages }}</span>
          <button
            class="px-3 py-1.5 hover:bg-gray-50 disabled:opacity-40"
            :disabled="page >= totalPages || loading"
            @click="page++"
          >
            Next
          </button>
        </div>
      </div>
    </div>

    <div v-if="detailRow" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" @click.self="closeDetail">
      <div class="bg-white rounded-xl shadow-xl w-full max-w-3xl max-h-[90vh] overflow-hidden flex flex-col">
        <div class="px-6 py-4 border-b border-gray-100 flex items-start justify-between gap-4">
          <div>
            <p class="text-xs uppercase tracking-wide text-gray-400">Inquiry Product #{{ detailRow.id }}</p>
            <h2 class="text-lg font-bold text-gray-900 mt-1">{{ detailRow.canonical_name }}</h2>
            <p class="text-sm text-gray-500 mt-1">{{ detailRow.contact_name || 'Unknown contact' }} · {{ detailRow.account_name || 'No account' }}</p>
          </div>
          <button class="text-gray-400 hover:text-gray-700 text-xl leading-none" @click="closeDetail">×</button>
        </div>

        <div class="p-6 overflow-y-auto space-y-5">
          <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div class="rounded-lg border border-gray-100 bg-gray-50 p-3">
              <p class="text-xs text-gray-400 uppercase tracking-wide">Direction</p>
              <span class="inline-block mt-2" :class="directionClass(detailRow.inquiry_type)">{{ detailRow.inquiry_type || '-' }}</span>
            </div>
            <div class="rounded-lg border border-gray-100 bg-gray-50 p-3">
              <p class="text-xs text-gray-400 uppercase tracking-wide">Decision</p>
              <span class="inline-block mt-2" :class="statusClass(detailRow.decision_status)">{{ detailRow.decision_status }}</span>
            </div>
            <div class="rounded-lg border border-gray-100 bg-gray-50 p-3">
              <p class="text-xs text-gray-400 uppercase tracking-wide">Match</p>
              <span class="inline-block mt-2" :class="statusClass(detailRow.match_status)">{{ detailRow.match_status }}</span>
            </div>
            <div class="rounded-lg border border-gray-100 bg-gray-50 p-3">
              <p class="text-xs text-gray-400 uppercase tracking-wide">Created</p>
              <p class="text-sm font-medium text-gray-800 mt-2">{{ formatTime(detailRow.created_at) }}</p>
            </div>
          </div>

          <div class="grid md:grid-cols-2 gap-4">
            <div class="rounded-lg border border-gray-100 p-4">
              <p class="text-xs text-gray-400 uppercase tracking-wide mb-2">Extracted Product</p>
              <p class="font-semibold text-gray-900">{{ detailRow.canonical_name }}</p>
              <p class="text-sm text-gray-500 mt-2">
                Qty: {{ detailRow.quantity ?? '-' }}
                <span v-if="detailRow.price"> · {{ detailRow.currency || '' }} {{ detailRow.price }}</span>
              </p>
              <p class="text-xs text-gray-400 mt-2">Source index {{ detailRow.source_product_index ?? '-' }}</p>
            </div>

            <div class="rounded-lg border border-gray-100 p-4">
              <p class="text-xs text-gray-400 uppercase tracking-wide mb-2">Inventory Match</p>
              <p v-if="detailRow.product" class="font-semibold text-gray-900">{{ detailRow.product_name }}</p>
              <p v-else class="text-sm text-red-600">No inventory product mapped</p>
              <p v-if="detailRow.match_source" class="text-xs text-gray-400 mt-2">Source: {{ detailRow.match_source }}</p>
              <p v-if="detailRow.match_reason" class="text-sm text-gray-600 mt-2 leading-relaxed">{{ detailRow.match_reason }}</p>
            </div>
          </div>

          <div class="rounded-lg border border-gray-100 p-4">
            <p class="text-xs text-gray-400 uppercase tracking-wide mb-2">AI Summary</p>
            <p class="text-sm text-gray-800 leading-relaxed whitespace-pre-wrap">{{ detailRow.inquiry_summary || '-' }}</p>
          </div>

          <div class="rounded-lg border border-gray-100 p-4">
            <div class="flex items-center justify-between gap-3 mb-2">
              <p class="text-xs text-gray-400 uppercase tracking-wide">Original Message</p>
              <div class="flex items-center gap-3">
                <p class="text-xs text-gray-400">{{ formatTime(detailRow.source_message_time || detailRow.first_seen_at) }}</p>
                <button
                  v-if="detailRow.source_chat_id"
                  class="text-xs text-blue-700 font-semibold hover:text-blue-800"
                  @click="viewChat(detailRow)"
                >
                  Chat →
                </button>
              </div>
            </div>
            <p class="text-sm text-gray-800 leading-relaxed whitespace-pre-wrap">{{ detailRow.source_message_text || '-' }}</p>
          </div>

          <div class="grid md:grid-cols-3 gap-4 text-sm">
            <div>
              <p class="text-xs text-gray-400 uppercase tracking-wide">Contact</p>
              <p class="font-medium text-gray-900 mt-1">{{ detailRow.contact_name || '-' }}</p>
              <p class="text-gray-500">{{ detailRow.contact_phone || '-' }}</p>
            </div>
            <div>
              <p class="text-xs text-gray-400 uppercase tracking-wide">Inquiry</p>
              <p class="font-medium text-gray-900 mt-1">#{{ detailRow.inquiry }}</p>
              <p class="text-gray-500">Message #{{ detailRow.source_message || '-' }}</p>
            </div>
            <div>
              <p class="text-xs text-gray-400 uppercase tracking-wide">Embedding</p>
              <span class="inline-block mt-1" :class="statusClass(detailRow.embedding_status)">{{ detailRow.embedding_status }}</span>
              <p v-if="detailRow.embedding_model" class="text-gray-500 mt-1">{{ detailRow.embedding_model }}</p>
            </div>
          </div>
        </div>

        <div class="px-6 py-4 border-t border-gray-100 flex justify-end bg-white">
          <button class="px-4 py-2 rounded-lg border border-gray-200 text-sm bg-white hover:bg-gray-50" @click="closeDetail">Close</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.filter-control {
  border: 1px solid #e5e7eb;
  border-radius: 0.5rem;
  padding: 0.375rem 0.75rem;
  font-size: 0.875rem;
  background: white;
}

.filter-control:focus {
  outline: none;
  box-shadow: 0 0 0 2px rgb(34 197 94 / 0.45);
}
</style>
