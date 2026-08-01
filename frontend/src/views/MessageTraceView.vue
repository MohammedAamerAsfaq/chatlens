<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { messageTraceApi, accountsApi } from '@/api'

const rows      = ref([])
const accounts  = ref([])
const loading   = ref(false)

const filterAccount = ref('all')
const search         = ref('')

const page            = ref(1)
const pageSize        = ref(25)
const totalCount      = ref(0)
const pageSizeOptions = [10, 25, 50, 100]

const totalPages = computed(() => Math.max(1, Math.ceil(totalCount.value / pageSize.value)))
const pageStart  = computed(() => totalCount.value === 0 ? 0 : (page.value - 1) * pageSize.value + 1)
const pageEnd    = computed(() => Math.min(page.value * pageSize.value, totalCount.value))

// Row identity is (account_id, provider_message_id) — provider_message_id alone
// isn't unique across accounts. expandedDetails caches the full trace per key so
// re-collapsing/re-expanding the same row doesn't refetch.
const expandedKey     = ref(null)
const expandedDetails = ref({})
const expandLoading   = ref(null)

function rowKey(row) { return `${row.account_id}:${row.provider_message_id}` }

let pollTimer = null
let searchDebounce = null

const SOURCE_LABELS = {
  baileys_event:          'Worker Event',
  whatsapp_message:       'Ingested Message',
  sync_log:               'Sync Log',
  dropped_message:        'Dropped Message',
  unresolved_message:     'Unresolved Message',
  stuck_receipt:          'Stuck Receipt',
  worker_alert:           'Worker Alert',
  ai_parsing_log:         'AI Parsing Log',
  message_embedding:      'Embedding',
  message_classification: 'Classification',
  inquiry:                'Inquiry',
}

const OUTCOME_LABELS = {
  delivered_and_linked_to_inquiry: 'Delivered — linked to Inquiry',
  delivered:                       'Delivered',
  dropped:                         'Dropped',
  self_healed:                     'Dropped, then self-healed',
  unresolved:                      'Preserved unresolved',
  no_trace_found:                  'No trace found',
  no_final_record:                 'No final outcome yet',
  partial_trace_no_final_outcome:  'Partial trace — no clear outcome',
}

function outcomeLabel(outcome) {
  if (OUTCOME_LABELS[outcome]) return OUTCOME_LABELS[outcome]
  if (outcome?.startsWith('unresolved_')) return `Preserved unresolved — ${outcome.replace('unresolved_', '')}`
  return outcome
}

function outcomeStyle(outcome) {
  if (outcome === 'delivered_and_linked_to_inquiry' || outcome === 'delivered' || outcome === 'self_healed') {
    return 'bg-green-100 text-green-700'
  }
  if (outcome === 'no_trace_found' || outcome === 'dropped') {
    return 'bg-red-100 text-red-700'
  }
  if (outcome?.startsWith('unresolved') || outcome === 'partial_trace_no_final_outcome' || outcome === 'no_final_record') {
    return 'bg-amber-100 text-amber-700'
  }
  return 'bg-gray-100 text-gray-600'
}

function statusStyle(statusValue) {
  const s = (statusValue || '').toLowerCase()
  if (/(fail|drop|error|incorrect)/.test(s)) return 'bg-red-100 text-red-700'
  if (/(success|delivered|resolved|sent|deal_done|linked)/.test(s)) return 'bg-green-100 text-green-700'
  if (/(pending|skipped|warning)/.test(s)) return 'bg-amber-100 text-amber-700'
  return 'bg-gray-100 text-gray-600'
}

function buildParams() {
  const p = { page: page.value, page_size: pageSize.value }
  if (filterAccount.value !== 'all') p.account = filterAccount.value
  if (search.value.trim())          p.search  = search.value.trim()
  return p
}

async function fetchList(showSpinner = false) {
  if (showSpinner) loading.value = true
  try {
    const { data } = await messageTraceApi.list(buildParams())
    rows.value       = data.results
    totalCount.value = data.count
  } catch {}
  finally { loading.value = false }
}

async function fetchAccounts() {
  try {
    const { data } = await accountsApi.list()
    accounts.value = data.results ?? data
  } catch {}
}

async function toggleRow(row) {
  const key = rowKey(row)
  if (expandedKey.value === key) {
    expandedKey.value = null
    return
  }
  expandedKey.value = key
  if (expandedDetails.value[key]) return
  expandLoading.value = key
  try {
    const { data } = await messageTraceApi.trace(row.account_id, row.provider_message_id)
    expandedDetails.value = { ...expandedDetails.value, [key]: data }
  } catch (e) {
    expandedDetails.value = {
      ...expandedDetails.value,
      [key]: { error: e.response?.data?.error || e.message || 'Trace failed', timeline: [] },
    }
  } finally {
    expandLoading.value = null
  }
}

function formatTime(dt) {
  if (!dt) return '—'
  return new Date(dt).toLocaleString()
}

function relativeTime(dt) {
  const diff = Math.floor((Date.now() - new Date(dt)) / 1000)
  if (diff < 60)    return `${diff}s ago`
  if (diff < 3600)  return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  return `${Math.floor(diff / 86400)}d ago`
}

const hasMeta = (meta) => meta && Object.keys(meta).length > 0

watch([filterAccount, pageSize], () => { page.value = 1; fetchList() })
watch(page, () => fetchList())
watch(search, () => {
  clearTimeout(searchDebounce)
  searchDebounce = setTimeout(() => { page.value = 1; fetchList() }, 400)
})

onMounted(() => {
  fetchAccounts()
  fetchList(true)
  pollTimer = setInterval(() => fetchList(), 15000)
})
onUnmounted(() => { clearInterval(pollTimer); clearTimeout(searchDebounce) })
</script>

<template>
  <div class="h-full w-full overflow-y-auto bg-gray-50">
    <div class="max-w-7xl mx-auto px-6 py-6">

      <!-- Header -->
      <div class="mb-6">
        <h1 class="text-2xl font-bold text-gray-900">Message Trace</h1>
        <p class="text-sm text-gray-500 mt-1">
          Every message the worker has ever recorded a trace for — click a row to see its full
          lifecycle: every worker event, drop, preservation, or classification step, in order.
        </p>
      </div>

      <!-- Filters -->
      <div class="flex items-center gap-3 mb-4 flex-wrap">
        <select
          v-model="filterAccount"
          class="border border-gray-200 rounded-lg px-3 py-1.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-green-500 min-w-[160px]"
        >
          <option value="all">All accounts</option>
          <option v-for="acc in accounts" :key="acc.id" :value="acc.id">
            {{ acc.display_name || acc.phone_number || `Account #${acc.id}` }}
          </option>
        </select>

        <input
          v-model="search"
          placeholder="Search provider message id…"
          class="border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-green-500 font-mono min-w-[220px]"
        />

        <span class="text-sm text-gray-400 flex-1">{{ totalCount.toLocaleString() }} messages</span>

        <div class="flex items-center gap-2 text-sm text-gray-500">
          <span>Rows:</span>
          <div class="flex border border-gray-200 rounded-lg overflow-hidden">
            <button
              v-for="n in pageSizeOptions"
              :key="n"
              @click="pageSize = n"
              :class="['px-2.5 py-1 text-xs transition-colors', pageSize === n ? 'bg-green-600 text-white' : 'hover:bg-gray-50 text-gray-600']"
            >{{ n }}</button>
          </div>
        </div>
      </div>

      <!-- Table -->
      <div class="bg-white rounded-xl border border-gray-200 overflow-hidden shadow-sm">
        <div v-if="loading" class="text-center text-gray-400 py-12 text-sm">Loading…</div>

        <div v-else-if="rows.length === 0" class="text-center text-gray-400 py-12 text-sm">
          No traced messages found
        </div>

        <table v-else class="w-full text-sm">
          <thead>
            <tr class="bg-gray-50 border-b border-gray-100 text-xs text-gray-500 uppercase tracking-wide">
              <th class="text-left px-4 py-3 w-28">Last Seen</th>
              <th class="text-left px-4 py-3 w-36">Account</th>
              <th class="text-left px-4 py-3">Provider Message ID</th>
              <th class="text-left px-4 py-3 w-40">Sender</th>
              <th class="text-left px-4 py-3 w-40">Outcome</th>
              <th class="text-left px-4 py-3 w-20">Events</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-50">
            <template v-for="row in rows" :key="rowKey(row)">
              <tr
                @click="toggleRow(row)"
                :class="['cursor-pointer transition-colors', expandedKey === rowKey(row) ? 'bg-gray-100' : 'hover:bg-gray-50']"
              >
                <td class="px-4 py-2.5">
                  <span class="text-gray-500 text-xs" :title="formatTime(row.last_seen)">{{ relativeTime(row.last_seen) }}</span>
                </td>
                <td class="px-4 py-2.5">
                  <span class="text-xs text-gray-700 truncate block max-w-[130px]">{{ row.account_name }}</span>
                </td>
                <td class="px-4 py-2.5">
                  <span class="text-xs font-mono text-gray-700">{{ row.provider_message_id }}</span>
                </td>
                <td class="px-4 py-2.5">
                  <span class="text-xs text-gray-700 truncate block max-w-[150px]">
                    {{ row.push_name || row.sender_number || '—' }}
                  </span>
                </td>
                <td class="px-4 py-2.5">
                  <span :class="['text-xs font-medium px-2 py-0.5 rounded-full', outcomeStyle(row.outcome)]">
                    {{ outcomeLabel(row.outcome) }}
                  </span>
                </td>
                <td class="px-4 py-2.5 text-xs text-gray-500">{{ row.event_count }}</td>
              </tr>

              <!-- Expanded detail: full ordered trace timeline -->
              <tr v-if="expandedKey === rowKey(row)" :key="`${rowKey(row)}-detail`">
                <td colspan="6" class="px-6 py-4 bg-gray-50 border-t border-gray-100">
                  <div v-if="expandLoading === rowKey(row)" class="text-center text-gray-400 py-6 text-sm">Loading trace…</div>

                  <template v-else-if="expandedDetails[rowKey(row)]">
                    <p v-if="expandedDetails[rowKey(row)].error" class="text-sm text-red-600">
                      {{ expandedDetails[rowKey(row)].error }}
                    </p>
                    <ol v-else class="relative border-l-2 border-gray-200 ml-3">
                      <li v-for="(ev, idx) in expandedDetails[rowKey(row)].timeline" :key="idx" class="mb-4 ml-6">
                        <span class="absolute -left-[9px] w-4 h-4 rounded-full bg-white border-2 border-green-500"></span>
                        <div class="bg-white rounded-xl border border-gray-200 shadow-sm p-3">
                          <div class="flex items-center gap-2 flex-wrap mb-1.5">
                            <span class="text-xs text-gray-400">{{ formatTime(ev.timestamp) }}</span>
                            <span class="text-xs font-semibold px-2 py-0.5 rounded-full bg-gray-100 text-gray-700">
                              {{ SOURCE_LABELS[ev.source] || ev.source }}
                            </span>
                            <span class="text-xs px-2 py-0.5 rounded-full bg-blue-50 text-blue-700">{{ ev.stage }}</span>
                            <span :class="['text-xs font-medium px-2 py-0.5 rounded-full', statusStyle(ev.status)]">{{ ev.status }}</span>
                          </div>
                          <p class="text-sm text-gray-800">{{ ev.detail }}</p>
                          <details v-if="hasMeta(ev.meta)" class="mt-2">
                            <summary class="text-xs text-gray-400 cursor-pointer hover:text-gray-600">details</summary>
                            <pre class="bg-gray-900 text-green-400 text-xs rounded-lg p-3 mt-2 overflow-x-auto max-h-48 leading-relaxed">{{ JSON.stringify(ev.meta, null, 2) }}</pre>
                          </details>
                        </div>
                      </li>
                    </ol>
                  </template>
                </td>
              </tr>
            </template>
          </tbody>
        </table>

        <!-- Pagination -->
        <div v-if="totalCount > 0" class="flex items-center justify-between px-4 py-3 border-t border-gray-100 bg-gray-50 text-sm text-gray-500">
          <span>Showing {{ pageStart.toLocaleString() }}–{{ pageEnd.toLocaleString() }} of {{ totalCount.toLocaleString() }}</span>
          <div class="flex items-center gap-1">
            <button @click="page--" :disabled="page === 1" class="px-3 py-1.5 rounded-lg border border-gray-200 text-xs disabled:opacity-40 hover:bg-white transition-colors">← Prev</button>
            <span class="px-3 py-1.5 text-xs">Page {{ page }} of {{ totalPages }}</span>
            <button @click="page++" :disabled="page >= totalPages" class="px-3 py-1.5 rounded-lg border border-gray-200 text-xs disabled:opacity-40 hover:bg-white transition-colors">Next →</button>
          </div>
        </div>
      </div>

    </div>
  </div>
</template>
