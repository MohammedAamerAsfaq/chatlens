<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { tradingApi } from '@/api'
import { useConversationsStore } from '@/stores/conversations'

const router = useRouter()
const conversations = useConversationsStore()
const rows = ref([])
const loading = ref(false)
const error = ref('')
const total = ref(0)
const page = ref(1)
const pageSize = ref(25)
const ordering = ref('last_seen_newest')
const detailRow = ref(null)
const pageSizeOptions = [25, 50, 100]
const smartQuery = ref('')
const smartResults = ref([])
const smartSearching = ref(false)
const smartSearched = ref(false)
const smartError = ref('')
const backfillRunning = ref(false)
const backfillMessage = ref('')
const embeddingStatus = ref({
  total: 0,
  embedded: 0,
  pending: 0,
  error: 0,
  skipped: 0,
  pending_work: 0,
})
const dateInput = ref('')
const dateError = ref('')
let requestSeq = 0
let searchTimer = null

const filters = ref({
  status: '',
  type: '',
  brand: '',
  search: '',
  date: '',
})

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))
const pageStart = computed(() => total.value === 0 ? 0 : (page.value - 1) * pageSize.value + 1)
const pageEnd = computed(() => Math.min(page.value * pageSize.value, total.value))
const trackingCount = computed(() => rows.value.filter(row => row.status === 'tracking').length)
const promotedCount = computed(() => rows.value.filter(row => row.status === 'promoted_to_inventory').length)

function params() {
  const p = { page: page.value, page_size: pageSize.value, ordering: ordering.value }
  for (const [key, value] of Object.entries(filters.value)) {
    if (value !== '') p[key] = value
  }
  return p
}

function statusParams() {
  const p = {}
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
    const { data } = await tradingApi.listNonInventoryProducts(params())
    if (seq !== requestSeq) return
    rows.value = data.results ?? data
    total.value = data.count ?? rows.value.length
    await loadEmbeddingStatus()
  } catch (err) {
    if (seq !== requestSeq) return
    error.value = err.response?.data?.detail || err.message || 'Failed to load non-inventory products'
  } finally {
    if (seq === requestSeq) loading.value = false
  }
}

async function loadEmbeddingStatus() {
  const { data } = await tradingApi.getNonInventoryProductEmbeddingStatus(statusParams())
  embeddingStatus.value = {
    total: data.total || 0,
    embedded: data.embedded || 0,
    pending: data.pending || 0,
    error: data.error || 0,
    skipped: data.skipped || 0,
    pending_work: data.pending_work || 0,
  }
}

async function runSmartSearch() {
  const q = smartQuery.value.trim()
  if (!q) {
    smartResults.value = []
    smartSearched.value = false
    smartError.value = ''
    return
  }
  smartSearching.value = true
  smartError.value = ''
  smartSearched.value = true
  try {
    const { data } = await tradingApi.searchNonInventoryProductEmbeddings({ q, top_k: 20 })
    smartResults.value = (data.results || []).map(item => ({
      row: item.non_inventory_product,
      distance: item.distance,
    }))
  } catch (err) {
    smartResults.value = []
    smartError.value = err.response?.data?.detail || err.message || 'Embedding search failed'
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

async function backfillEmbeddings() {
  backfillRunning.value = true
  backfillMessage.value = ''
  try {
    const { data } = await tradingApi.backfillNonInventoryProductEmbeddings({ limit: 250 })
    if (data.status) {
      embeddingStatus.value = data.status
    }
    backfillMessage.value = `Backfill complete: ${data.embedded || 0} embedded, ${data.skipped || 0} skipped, ${data.errors || 0} errors. Current status: ${embeddingStatus.value.embedded || 0} embedded, ${embeddingStatus.value.pending_work || 0} pending work.`
    await load()
  } catch (err) {
    backfillMessage.value = err.response?.data?.detail || err.message || 'Embedding backfill failed'
  } finally {
    backfillRunning.value = false
  }
}

function resetFilters() {
  filters.value = { status: '', type: '', brand: '', search: '', date: '' }
  dateInput.value = ''
  dateError.value = ''
  page.value = 1
  load()
}

function formatTime(value) {
  if (!value) return '-'
  return new Date(value).toLocaleString()
}

function parseDdMmYyyy(value) {
  const text = String(value || '').trim()
  if (!text) return ''
  const match = text.match(/^(\d{2})\/(\d{2})\/(\d{4})$/)
  if (!match) return null
  const [, dd, mm, yyyy] = match
  const date = new Date(Number(yyyy), Number(mm) - 1, Number(dd))
  if (
    date.getFullYear() !== Number(yyyy)
    || date.getMonth() !== Number(mm) - 1
    || date.getDate() !== Number(dd)
  ) {
    return null
  }
  return `${yyyy}-${mm}-${dd}`
}

function statusClass(value) {
  const base = 'text-xs font-medium px-2 py-0.5 rounded-full capitalize '
  const classes = {
    tracking: 'bg-blue-100 text-blue-700',
    promoted_to_inventory: 'bg-green-100 text-green-700',
    dismissed: 'bg-gray-100 text-gray-500',
    merged: 'bg-purple-100 text-purple-700',
    buy: 'bg-green-100 text-green-700',
    sell: 'bg-amber-100 text-amber-700',
    deterministic: 'bg-blue-100 text-blue-700',
    embedding: 'bg-indigo-100 text-indigo-700',
    ai: 'bg-purple-100 text-purple-700',
    manual: 'bg-green-100 text-green-700',
    pending: 'bg-amber-100 text-amber-700',
    embedded: 'bg-green-100 text-green-700',
    error: 'bg-red-100 text-red-700',
    skipped: 'bg-gray-100 text-gray-500',
  }
  return base + (classes[value] || 'bg-gray-100 text-gray-500')
}

function statusLabel(value) {
  return String(value || '-').replaceAll('_', ' ')
}

function matchPercent(distance) {
  if (distance == null) return '-'
  return `${Math.max(0, Math.round((1 - Number(distance)) * 100))}%`
}

function openDetail(row) {
  detailRow.value = row
}

function closeDetail() {
  detailRow.value = null
}

function latestMention(row) {
  return row?.latest_mentions?.[0] || null
}

function mentionProductText(mention, row = null) {
  return (
    mention?.raw_text
    || mention?.canonical_name_from_ai
    || row?.canonical_name
    || ''
  ).trim()
}

function waLinkForRow(row) {
  const mention = latestMention(row)
  const phone = mention?.contact_phone
  if (!phone) return null
  const clean = phone.split('@')[0].replace(/\D/g, '')
  if (!clean) return null
  const text = mentionProductText(mention, row)
  const params = new URLSearchParams({ phone: clean })
  if (text) params.set('text', text)
  return `whatsapp://send?${params.toString()}`
}

async function viewChat(row) {
  const mention = latestMention(row)
  if (!mention?.source_chat_id) return
  if (mention.account && conversations.selectedAccountId !== mention.account) {
    await conversations.switchAccount(mention.account)
  }
  conversations.selectChat(mention.source_chat_id, {
    messageId: mention.source_message,
    messageTime: mention.message_time,
  })
  router.push({ name: 'conversations' })
}

onMounted(load)

watch(
  () => [filters.value.status, filters.value.type, filters.value.brand, filters.value.date, pageSize.value, ordering.value],
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

watch(dateInput, () => {
  const parsed = parseDdMmYyyy(dateInput.value)
  if (parsed === null) {
    dateError.value = 'Use dd/MM/yyyy'
    return
  }
  dateError.value = ''
  filters.value.date = parsed
})
</script>

<template>
  <div class="h-full w-full overflow-y-auto bg-gray-50">
    <div class="max-w-7xl mx-auto px-6 py-6">
      <div class="mb-6 flex items-start justify-between gap-4">
        <div>
          <h1 class="text-2xl font-bold text-gray-900">Non-Inventory Products</h1>
          <p class="text-sm text-gray-500 mt-1">Track products mentioned in inquiries but not yet mapped to inventory</p>
        </div>
        <div class="flex items-center gap-2">
          <button
            class="px-4 py-2 rounded-lg border border-indigo-200 bg-white text-indigo-700 text-sm font-semibold hover:bg-indigo-50 disabled:opacity-50 transition-colors"
            :disabled="backfillRunning"
            @click="backfillEmbeddings"
          >
            {{ backfillRunning ? 'Backfilling...' : 'Backfill Embeddings' }}
          </button>
          <button
            class="px-4 py-2 rounded-lg bg-green-600 text-white text-sm font-semibold hover:bg-green-700 disabled:opacity-50 transition-colors"
            :disabled="loading"
            @click="load"
          >
            {{ loading ? 'Loading...' : 'Refresh' }}
          </button>
        </div>
      </div>

      <div class="mb-4 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
        This page displays products mentioned in inquiries but not mapped to inventory. V2 unmatched lines are auto-tracked after matching completes; manual tracking remains available from inquiry product popups.
      </div>
      <div v-if="backfillMessage" class="mb-4 rounded-lg border border-indigo-200 bg-indigo-50 px-4 py-3 text-sm text-indigo-800">
        {{ backfillMessage }}
      </div>

      <div class="flex items-center gap-6 mb-6 bg-white rounded-xl border border-gray-200 px-6 py-4 shadow-sm flex-wrap">
        <div>
          <p class="text-xs text-gray-400 uppercase tracking-wide">Total</p>
          <p class="text-xl font-bold text-gray-900">{{ total.toLocaleString() }}</p>
        </div>
        <div class="w-px h-8 bg-gray-100"></div>
        <div>
          <p class="text-xs text-blue-500 uppercase tracking-wide">Tracking</p>
          <p class="text-xl font-bold text-gray-900">{{ trackingCount.toLocaleString() }}</p>
        </div>
        <div class="w-px h-8 bg-gray-100"></div>
        <div>
          <p class="text-xs text-green-500 uppercase tracking-wide">Promoted</p>
          <p class="text-xl font-bold text-gray-900">{{ promotedCount.toLocaleString() }}</p>
        </div>
        <div class="w-px h-8 bg-gray-100"></div>
        <div>
          <p class="text-xs text-indigo-500 uppercase tracking-wide">Embedded</p>
          <p class="text-xl font-bold text-gray-900">{{ embeddingStatus.embedded.toLocaleString() }}</p>
        </div>
        <div class="w-px h-8 bg-gray-100"></div>
        <div>
          <p class="text-xs text-amber-500 uppercase tracking-wide">Pending Work</p>
          <p class="text-xl font-bold text-gray-900">{{ embeddingStatus.pending_work.toLocaleString() }}</p>
          <p class="text-[11px] text-gray-400 mt-0.5">
            Pending {{ embeddingStatus.pending.toLocaleString() }} / Error {{ embeddingStatus.error.toLocaleString() }}
          </p>
        </div>
      </div>

      <div class="flex items-center gap-3 mb-4 flex-wrap">
        <input
          v-model="filters.search"
          class="filter-control flex-1 min-w-[260px]"
          placeholder="Search name, key, brand, raw mention..."
          @keydown.enter="load"
        />
        <input v-model="filters.brand" class="filter-control min-w-[140px]" placeholder="Brand" />
        <select v-model="filters.status" class="filter-control">
          <option value="">All statuses</option>
          <option value="tracking">Tracking</option>
          <option value="promoted_to_inventory">Promoted</option>
          <option value="dismissed">Dismissed</option>
          <option value="merged">Merged</option>
        </select>
        <select v-model="filters.type" class="filter-control">
          <option value="">WTB + WTS</option>
          <option value="buy">Mentioned in WTB</option>
          <option value="sell">Mentioned in WTS</option>
        </select>
        <div>
          <input
            v-model="dateInput"
            class="filter-control w-[135px]"
            placeholder="dd/MM/yyyy"
            inputmode="numeric"
          />
          <div v-if="dateError" class="text-xs text-red-600 mt-1">{{ dateError }}</div>
        </div>
        <select v-model="ordering" class="filter-control min-w-[180px]">
          <option value="last_seen_newest">Last seen newest</option>
          <option value="last_seen_oldest">Last seen oldest</option>
          <option value="first_seen_newest">First seen newest</option>
          <option value="first_seen_oldest">First seen oldest</option>
          <option value="mentions_desc">Most mentions</option>
          <option value="mentions_asc">Fewest mentions</option>
          <option value="name_asc">Name A-Z</option>
          <option value="name_desc">Name Z-A</option>
        </select>
        <button class="px-3 py-1.5 rounded-lg border border-gray-200 text-sm bg-white text-gray-500 hover:bg-gray-50 transition-colors" @click="resetFilters">Reset</button>
      </div>

      <div class="mb-4 rounded-xl border border-indigo-100 bg-indigo-50/40 p-4">
        <div class="flex items-center gap-3 flex-wrap">
          <span class="text-indigo-600 text-sm font-bold">Smart Search</span>
          <input
            v-model="smartQuery"
            class="filter-control flex-1 min-w-[260px]"
            placeholder="Search non-inventory products by meaning..."
            @keydown.enter="runSmartSearch"
          />
          <button
            class="px-4 py-2 rounded-lg bg-indigo-600 text-white text-sm font-semibold hover:bg-indigo-700 disabled:opacity-50 transition-colors"
            :disabled="smartSearching || !smartQuery.trim()"
            @click="runSmartSearch"
          >
            {{ smartSearching ? 'Searching...' : 'Smart Search' }}
          </button>
          <button class="px-3 py-2 rounded-lg border border-gray-200 text-sm bg-white text-gray-600 hover:bg-gray-50" @click="clearSmartSearch">
            Clear
          </button>
        </div>
        <div v-if="smartError" class="mt-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{{ smartError }}</div>
        <div v-if="smartSearched && !smartSearching" class="mt-3">
          <div v-if="!smartResults.length && !smartError" class="text-sm text-gray-500">
            No embedding matches found. If records are pending, run Backfill Embeddings first.
          </div>
          <div v-else class="overflow-x-auto rounded-lg border border-indigo-100 bg-white">
            <table class="w-full text-sm min-w-[960px]">
              <thead>
                <tr class="bg-white border-b border-indigo-100 text-xs text-gray-500 uppercase tracking-wide">
                  <th class="text-left px-4 py-2">Product</th>
                  <th class="text-left px-4 py-2 w-28">Match</th>
                  <th class="text-left px-4 py-2 w-32">Mentions</th>
                  <th class="text-left px-4 py-2 w-52">Latest Mention</th>
                  <th class="text-left px-4 py-2 w-36"></th>
                </tr>
              </thead>
              <tbody class="divide-y divide-gray-50">
                <tr v-for="result in smartResults" :key="result.row.id" class="hover:bg-gray-50">
                  <td class="px-4 py-2 align-top">
                    <div class="font-semibold text-gray-900">{{ result.row.canonical_name }}</div>
                    <div class="text-xs text-gray-500 mt-0.5">{{ result.row.brand || 'No brand' }}</div>
                  </td>
                  <td class="px-4 py-2 align-top">
                    <span class="text-xs font-semibold rounded-full bg-indigo-100 text-indigo-700 px-2 py-0.5">{{ matchPercent(result.distance) }}</span>
                    <div class="text-xs text-gray-400 mt-1">d {{ result.distance }}</div>
                  </td>
                  <td class="px-4 py-2 align-top">
                    <div class="font-semibold text-gray-900">{{ result.row.mention_count }}</div>
                    <div class="text-xs text-gray-500">WTB {{ result.row.buy_mention_count }} / WTS {{ result.row.sell_mention_count }}</div>
                  </td>
                  <td class="px-4 py-2 align-top">
                    <div class="text-xs text-gray-400">{{ formatTime(result.row.last_seen_at) }}</div>
                    <div class="text-xs text-gray-700 mt-1 max-w-[280px] truncate">
                      {{ latestMention(result.row)?.raw_text || latestMention(result.row)?.canonical_name_from_ai || '-' }}
                    </div>
                  </td>
                  <td class="px-4 py-2 align-top">
                    <div class="flex items-center gap-3 flex-wrap">
                      <button class="text-xs text-green-700 font-semibold hover:text-green-800" @click="openDetail(result.row)">Details</button>
                      <button
                        v-if="latestMention(result.row)?.source_chat_id"
                        class="text-xs text-blue-700 font-semibold hover:text-blue-800"
                        @click="viewChat(result.row)"
                      >
                        Chat ->
                      </button>
                      <a
                        v-if="waLinkForRow(result.row)"
                        :href="waLinkForRow(result.row)"
                        class="text-xs text-green-700 font-semibold hover:text-green-800"
                      >
                        WA
                      </a>
                    </div>
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
            <button class="px-3 py-1.5 text-xs hover:bg-gray-50 disabled:opacity-40" :disabled="page <= 1 || loading" @click="page--">Previous</button>
            <span class="px-3 py-1.5 text-xs border-x border-gray-200">Page {{ page }} of {{ totalPages }}</span>
            <button class="px-3 py-1.5 text-xs hover:bg-gray-50 disabled:opacity-40" :disabled="page >= totalPages || loading" @click="page++">Next</button>
          </div>
        </div>
      </div>

      <div v-if="error" class="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{{ error }}</div>

      <div class="bg-white rounded-xl border border-gray-200 overflow-hidden shadow-sm">
        <div v-if="loading" class="text-center text-gray-400 py-12 text-sm">Loading non-inventory products...</div>
        <div v-else-if="!rows.length" class="text-center text-gray-400 py-12 text-sm">
          No non-inventory products found. Rows will appear here after records are created manually or the resolver is wired in a later phase.
        </div>
        <div v-else class="overflow-x-auto">
          <table class="w-full text-sm min-w-[1120px]">
            <thead>
              <tr class="bg-gray-50 border-b border-gray-100 text-xs text-gray-500 uppercase tracking-wide">
                <th class="text-left px-4 py-3">Product</th>
                <th class="text-left px-4 py-3 w-28">Status</th>
                <th class="text-left px-4 py-3 w-32">Mentions</th>
                <th class="text-left px-4 py-3 w-56">Latest Mention</th>
                <th class="text-left px-4 py-3 w-48">Promoted / Merged</th>
                <th class="text-left px-4 py-3 w-28">Embedding</th>
                <th class="text-left px-4 py-3 w-44"></th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-50">
              <tr v-for="row in rows" :key="row.id" class="hover:bg-gray-50 transition-colors">
                <td class="px-4 py-3 align-top">
                  <div class="font-semibold text-gray-900">{{ row.canonical_name }}</div>
                  <div class="text-xs text-gray-500 mt-0.5">{{ row.brand || 'No brand' }}</div>
                  <div class="text-xs text-gray-400 mt-1 max-w-[420px] truncate">{{ row.normalized_key || row.normalized_name }}</div>
                </td>
                <td class="px-4 py-3 align-top">
                  <span :class="statusClass(row.status)">{{ statusLabel(row.status) }}</span>
                </td>
                <td class="px-4 py-3 align-top">
                  <div class="font-semibold text-gray-900">{{ row.mention_count }}</div>
                  <div class="text-xs text-gray-500 mt-0.5">WTB {{ row.buy_mention_count }} / WTS {{ row.sell_mention_count }}</div>
                </td>
                <td class="px-4 py-3 align-top">
                  <div class="text-xs text-gray-400">{{ formatTime(row.last_seen_at) }}</div>
                  <div v-if="row.latest_mentions?.length" class="text-xs text-gray-700 mt-1 max-w-[280px] max-h-10 overflow-hidden leading-snug">
                    {{ row.latest_mentions[0].raw_text || row.latest_mentions[0].canonical_name_from_ai }}
                  </div>
                  <div v-else class="text-xs text-gray-400 mt-1">No mention rows</div>
                </td>
                <td class="px-4 py-3 align-top">
                  <div v-if="row.promoted_product_name" class="font-medium text-green-700">{{ row.promoted_product_name }}</div>
                  <div v-else-if="row.merged_into_name" class="font-medium text-purple-700">Merged into {{ row.merged_into_name }}</div>
                  <div v-else class="text-xs text-gray-400">Not promoted</div>
                </td>
                <td class="px-4 py-3 align-top">
                  <span :class="statusClass(row.embedding_status)">{{ row.embedding_status }}</span>
                  <div v-if="row.embedding_model" class="text-xs text-gray-400 mt-0.5">{{ row.embedding_model }}</div>
                </td>
                <td class="px-4 py-3 align-top">
                  <div class="flex items-center gap-3 flex-wrap">
                    <button class="text-xs text-green-700 font-semibold hover:text-green-800" @click="openDetail(row)">View details</button>
                    <button
                      v-if="latestMention(row)?.source_chat_id"
                      class="text-xs text-blue-700 font-semibold hover:text-blue-800"
                      @click="viewChat(row)"
                    >
                      Chat →
                    </button>
                    <a
                      v-if="waLinkForRow(row)"
                      :href="waLinkForRow(row)"
                      class="text-xs text-green-700 font-semibold hover:text-green-800"
                    >
                      WA
                    </a>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <div v-if="detailRow" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" @click.self="closeDetail">
      <div class="bg-white rounded-xl shadow-xl w-full max-w-4xl max-h-[90vh] overflow-hidden flex flex-col">
        <div class="px-6 py-4 border-b border-gray-100 flex items-start justify-between gap-4">
          <div>
            <p class="text-xs uppercase tracking-wide text-gray-400">Non-Inventory Product #{{ detailRow.id }}</p>
            <h2 class="text-lg font-bold text-gray-900 mt-1">{{ detailRow.canonical_name }}</h2>
            <p class="text-sm text-gray-500 mt-1">{{ detailRow.brand || 'No brand' }} · {{ statusLabel(detailRow.status) }}</p>
          </div>
          <div class="flex items-center gap-3">
            <button
              v-if="latestMention(detailRow)?.source_chat_id"
              class="text-xs text-blue-700 font-semibold hover:text-blue-800"
              @click="viewChat(detailRow)"
            >
              Chat →
            </button>
            <a
              v-if="waLinkForRow(detailRow)"
              :href="waLinkForRow(detailRow)"
              class="text-xs text-green-700 font-semibold hover:text-green-800"
            >
              WA
            </a>
            <button class="text-gray-400 hover:text-gray-700 text-xl leading-none" @click="closeDetail">×</button>
          </div>
        </div>

        <div class="p-6 overflow-y-auto space-y-5">
          <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div class="rounded-lg border border-gray-100 bg-gray-50 p-3">
              <p class="text-xs text-gray-400 uppercase tracking-wide">Total</p>
              <p class="text-lg font-bold text-gray-900 mt-1">{{ detailRow.mention_count }}</p>
            </div>
            <div class="rounded-lg border border-gray-100 bg-gray-50 p-3">
              <p class="text-xs text-gray-400 uppercase tracking-wide">WTB</p>
              <p class="text-lg font-bold text-green-700 mt-1">{{ detailRow.buy_mention_count }}</p>
            </div>
            <div class="rounded-lg border border-gray-100 bg-gray-50 p-3">
              <p class="text-xs text-gray-400 uppercase tracking-wide">WTS</p>
              <p class="text-lg font-bold text-amber-700 mt-1">{{ detailRow.sell_mention_count }}</p>
            </div>
            <div class="rounded-lg border border-gray-100 bg-gray-50 p-3">
              <p class="text-xs text-gray-400 uppercase tracking-wide">Last Seen</p>
              <p class="text-sm font-medium text-gray-800 mt-1">{{ formatTime(detailRow.last_seen_at) }}</p>
            </div>
          </div>

          <div class="rounded-lg border border-gray-100 p-4">
            <p class="text-xs text-gray-400 uppercase tracking-wide mb-2">Attributes</p>
            <pre class="text-xs bg-gray-900 text-green-100 rounded-lg p-3 overflow-auto">{{ JSON.stringify(detailRow.attributes || {}, null, 2) }}</pre>
          </div>

          <div class="rounded-lg border border-gray-100 p-4">
            <p class="text-xs text-gray-400 uppercase tracking-wide mb-3">Latest Mentions</p>
            <div v-if="!detailRow.latest_mentions?.length" class="text-sm text-gray-400">No mention rows.</div>
            <div v-else class="space-y-3">
              <div v-for="mention in detailRow.latest_mentions" :key="mention.id" class="rounded-lg border border-gray-100 bg-gray-50 p-3">
                <div class="flex items-center justify-between gap-3">
                  <span :class="statusClass(mention.inquiry_type)">{{ mention.inquiry_type }}</span>
                  <span class="text-xs text-gray-400">{{ formatTime(mention.message_time) }}</span>
                </div>
                <p class="font-semibold text-gray-900 mt-2">{{ mention.canonical_name_from_ai }}</p>
                <p class="text-sm text-gray-700 mt-1 whitespace-pre-wrap">{{ mention.raw_text || mention.source_message_text || '-' }}</p>
                <div class="text-xs text-gray-500 mt-2">
                  {{ mention.contact_name || 'Unknown contact' }} · {{ mention.contact_phone || mention.account_name || '-' }}
                </div>
                <div class="text-xs text-gray-400 mt-1">
                  Match source: {{ mention.match_source || '-' }}
                  <span v-if="mention.match_confidence != null"> · Confidence: {{ mention.match_confidence }}</span>
                </div>
              </div>
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
