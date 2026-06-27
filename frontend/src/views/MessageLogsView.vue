<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { accountsApi, messageLogsApi } from '@/api'

const route  = useRoute()
const router = useRouter()

const logs        = ref([])
const accounts    = ref([])
const loading     = ref(false)
const clearing    = ref(false)
const showClear   = ref(false)
const expandedId  = ref(null)
const copiedId    = ref(null)
const highlightId = ref(null)   // set when arriving from a cross-link

// Filters
const selectedAccount = ref('none')
const filterDirection = ref('all')
const filterStatus    = ref('all')
const filterMessageId = ref('')    // exact match from URL or manual

// Pagination
const page            = ref(1)
const pageSize        = ref(25)
const totalCount      = ref(0)
const pageSizeOptions = [10, 25, 50, 100]

const totalPages = computed(() => Math.max(1, Math.ceil(totalCount.value / pageSize.value)))
const pageStart  = computed(() => totalCount.value === 0 ? 0 : (page.value - 1) * pageSize.value + 1)
const pageEnd    = computed(() => Math.min(page.value * pageSize.value, totalCount.value))

const selectedAccountObj = computed(() =>
  accounts.value.find(a => String(a.id) === String(selectedAccount.value))
)

let pollTimer = null

function buildParams() {
  const p = { page: page.value, page_size: pageSize.value }
  if (filterMessageId.value) p.message_id = filterMessageId.value
  return p
}

async function fetchLogs(showSpinner = false) {
  if (selectedAccount.value === 'none') { logs.value = []; totalCount.value = 0; return }
  if (showSpinner) loading.value = true
  try {
    const { data } = await messageLogsApi.list(selectedAccount.value, buildParams())
    logs.value       = data.results ?? []
    totalCount.value = data.count   ?? 0
    // Auto-expand + scroll to highlighted entry after load
    if (highlightId.value) {
      const hit = logs.value.find(l => l.provider_message_id === highlightId.value)
      if (hit) {
        expandedId.value = hit.provider_message_id
        setTimeout(() => {
          document.getElementById(`msglog-${hit.provider_message_id}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' })
        }, 100)
      }
    }
  } catch {}
  finally { loading.value = false }
}

async function fetchAccounts() {
  try {
    const { data } = await accountsApi.list()
    accounts.value = data.results ?? data
  } catch {}
}

watch([filterDirection, filterStatus, filterMessageId, pageSize], () => {
  page.value = 1
  fetchLogs()
})
watch(page,            () => fetchLogs())
watch(selectedAccount, () => { page.value = 1; filterMessageId.value = ''; highlightId.value = null; fetchLogs(true) })

onMounted(async () => {
  await fetchAccounts()

  // Handle incoming cross-link: ?account_id=X&message_id=Y
  if (route.query.account_id) {
    selectedAccount.value = String(route.query.account_id)
  } else if (accounts.value.length) {
    selectedAccount.value = String(accounts.value[0].id)
  }
  if (route.query.message_id) {
    filterMessageId.value = route.query.message_id
    highlightId.value     = route.query.message_id
  }

  fetchLogs(true)
  pollTimer = setInterval(() => fetchLogs(), 10000)
})
onUnmounted(() => clearInterval(pollTimer))

async function clearLogs() {
  if (selectedAccount.value === 'none') return
  clearing.value = true
  try {
    await messageLogsApi.clear(selectedAccount.value)
    page.value = 1
    await fetchLogs()
  } finally {
    clearing.value  = false
    showClear.value = false
  }
}

function formatTime(ts) {
  if (!ts) return ''
  return new Date(ts).toLocaleString()
}

function relativeTime(ts) {
  const diff = Math.floor((Date.now() - new Date(ts)) / 1000)
  if (diff < 60)    return `${diff}s ago`
  if (diff < 3600)  return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  return `${Math.floor(diff / 86400)}d ago`
}

function toggleRow(id) {
  expandedId.value = expandedId.value === id ? null : id
}

async function copyPayload(log) {
  if (!log.raw_payload) return
  try {
    await navigator.clipboard.writeText(JSON.stringify(log.raw_payload, null, 2))
    copiedId.value = log.provider_message_id
    setTimeout(() => { copiedId.value = null }, 1500)
  } catch {}
}

function goToActivityLog(log) {
  router.push({
    name: 'activity',
    query: { account_id: log.session_id, message_id: log.provider_message_id },
  })
}

const directionStyle = {
  inbound:  'bg-blue-100 text-blue-700',
  outbound: 'bg-orange-100 text-orange-700',
}
const fwdStyle = {
  success: 'bg-green-100 text-green-700',
  error:   'bg-red-100 text-red-700',
}

// Client-side direction filter (worker doesn't support it as a query param)
const displayedLogs = computed(() => {
  if (filterDirection.value === 'all' && filterStatus.value === 'all') return logs.value
  return logs.value.filter(l => {
    if (filterDirection.value !== 'all' && l.direction !== filterDirection.value) return false
    if (filterStatus.value    !== 'all' && l.forward_status !== filterStatus.value) return false
    return true
  })
})
</script>

<template>
  <div class="h-full w-full overflow-y-auto bg-gray-50">
  <div class="max-w-7xl mx-auto px-6 py-6">

    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-2xl font-bold text-gray-900">Message Logs</h1>
        <p class="text-sm text-gray-500 mt-1">Node.js level — captured before forwarding to Django</p>
      </div>
      <button
        @click="showClear = true"
        :disabled="selectedAccount === 'none'"
        class="flex items-center gap-1.5 px-3 py-1.5 text-sm text-red-600 border border-red-200 rounded-lg hover:bg-red-50 transition-colors disabled:opacity-40"
      >
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
        </svg>
        Clear Logs
      </button>
    </div>

    <!-- Filters -->
    <div class="flex items-center gap-3 mb-4 flex-wrap">

      <!-- Account selector -->
      <select
        v-model="selectedAccount"
        class="border border-gray-200 rounded-lg px-3 py-1.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-green-500 min-w-[180px]"
      >
        <option value="none">Select account…</option>
        <option v-for="acc in accounts" :key="acc.id" :value="acc.id">
          {{ acc.display_name || acc.phone_number || `Account #${acc.id}` }}
        </option>
      </select>

      <select v-model="filterDirection" class="border border-gray-200 rounded-lg px-3 py-1.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-green-500">
        <option value="all">All directions</option>
        <option value="inbound">Inbound</option>
        <option value="outbound">Outbound</option>
      </select>

      <select v-model="filterStatus" class="border border-gray-200 rounded-lg px-3 py-1.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-green-500">
        <option value="all">All statuses</option>
        <option value="success">Forwarded OK</option>
        <option value="error">Forward failed</option>
      </select>

      <!-- Message ID search -->
      <div class="relative">
        <input
          v-model="filterMessageId"
          placeholder="Filter by message ID…"
          class="border border-gray-200 rounded-lg pl-3 pr-7 py-1.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-green-500 w-52"
        />
        <button
          v-if="filterMessageId"
          @click="filterMessageId = ''; highlightId = null"
          class="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
        >✕</button>
      </div>

      <span class="text-sm text-gray-400 flex-1">
        {{ totalCount.toLocaleString() }} entries
      </span>

      <!-- Page size -->
      <div class="flex items-center gap-2 text-sm text-gray-500">
        <span>Rows:</span>
        <div class="flex border border-gray-200 rounded-lg overflow-hidden">
          <button
            v-for="n in pageSizeOptions" :key="n"
            @click="pageSize = n"
            :class="['px-2.5 py-1 text-xs transition-colors', pageSize === n ? 'bg-green-600 text-white' : 'hover:bg-gray-50 text-gray-600']"
          >{{ n }}</button>
        </div>
      </div>
    </div>

    <!-- Table -->
    <div class="bg-white rounded-xl border border-gray-200 overflow-hidden shadow-sm">
      <div v-if="selectedAccount === 'none'" class="text-center text-gray-400 py-12 text-sm">
        Select an account to view its message logs
      </div>
      <div v-else-if="loading" class="text-center text-gray-400 py-12 text-sm">Loading…</div>
      <div v-else-if="displayedLogs.length === 0" class="text-center text-gray-400 py-12 text-sm">
        No message logs yet
      </div>

      <table v-else class="w-full text-sm">
        <thead>
          <tr class="bg-gray-50 border-b border-gray-100 text-xs text-gray-500 uppercase tracking-wide">
            <th class="text-left px-4 py-3 w-28">Time</th>
            <th class="text-left px-4 py-3 w-24">Direction</th>
            <th class="text-left px-4 py-3 w-24">Type</th>
            <th class="text-left px-4 py-3 w-36">Sender</th>
            <th class="text-left px-4 py-3 w-36">Name</th>
            <th class="text-left px-4 py-3">Message</th>
            <th class="text-left px-4 py-3 w-24">Status</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-gray-50">
          <template v-for="log in displayedLogs" :key="log.provider_message_id">
            <tr
              :id="`msglog-${log.provider_message_id}`"
              @click="toggleRow(log.provider_message_id)"
              :class="[
                'cursor-pointer transition-colors',
                expandedId === log.provider_message_id
                  ? 'bg-gray-100'
                  : log.provider_message_id === highlightId
                    ? 'bg-yellow-50 ring-1 ring-inset ring-yellow-300'
                    : log.forward_status === 'error'
                      ? 'bg-red-50/40 hover:bg-red-50'
                      : 'hover:bg-gray-50',
              ]"
            >
              <td class="px-4 py-2.5">
                <span class="text-xs text-gray-500" :title="formatTime(log.ts)">{{ relativeTime(log.ts) }}</span>
              </td>
              <td class="px-4 py-2.5">
                <span :class="['text-xs font-medium px-2 py-0.5 rounded-full', directionStyle[log.direction] || 'bg-gray-100 text-gray-600']">
                  {{ log.direction }}
                </span>
              </td>
              <td class="px-4 py-2.5">
                <span class="text-xs text-gray-600 capitalize">{{ log.message_type }}</span>
              </td>
              <td class="px-4 py-2.5">
                <span class="text-xs font-mono text-gray-700">{{ log.sender_number ? `+${log.sender_number}` : '—' }}</span>
              </td>
              <td class="px-4 py-2.5">
                <span class="text-xs text-gray-700 truncate block max-w-[140px]">{{ log.push_name || log.group_name || '—' }}</span>
              </td>
              <td class="px-4 py-2.5">
                <div class="flex items-center justify-between gap-2">
                  <span class="text-xs text-gray-600 truncate max-w-xs">
                    {{ log.message_text || (log.has_media ? `[${log.message_type}]` : '—') }}
                  </span>
                  <svg
                    :class="['w-3.5 h-3.5 text-gray-400 shrink-0 transition-transform', expandedId === log.provider_message_id ? 'rotate-180' : '']"
                    fill="none" stroke="currentColor" viewBox="0 0 24 24"
                  >
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/>
                  </svg>
                </div>
              </td>
              <td class="px-4 py-2.5">
                <span :class="['text-xs font-medium px-2 py-0.5 rounded-full', fwdStyle[log.forward_status] || 'bg-gray-100 text-gray-600']">
                  {{ log.forward_status === 'success' ? 'OK' : log.forward_status }}
                </span>
              </td>
            </tr>

            <!-- Expanded detail row -->
            <tr v-if="expandedId === log.provider_message_id" :key="`${log.provider_message_id}-detail`">
              <td colspan="7" class="px-6 py-4 bg-gray-50 border-t border-gray-100">

                <!-- Meta grid -->
                <div class="grid grid-cols-2 gap-x-8 gap-y-1.5 text-xs max-w-4xl mb-4">
                  <div class="col-span-2 flex items-center gap-3 pb-2 mb-1 border-b border-gray-200 flex-wrap">
                    <span class="text-gray-500 font-mono">{{ formatTime(log.ts) }}</span>
                    <span :class="['font-medium px-2 py-0.5 rounded-full', directionStyle[log.direction] || 'bg-gray-100 text-gray-600']">{{ log.direction }}</span>
                    <span :class="['font-medium px-2 py-0.5 rounded-full', fwdStyle[log.forward_status] || 'bg-gray-100 text-gray-600']">
                      forward: {{ log.forward_status }}
                    </span>
                    <!-- Cross-link → Activity Log -->
                    <button
                      @click.stop="goToActivityLog(log)"
                      class="ml-auto flex items-center gap-1 text-xs px-2.5 py-1 rounded-lg border border-blue-200 text-blue-600 hover:bg-blue-50 transition-colors"
                      title="View matching entry in Activity Log"
                    >
                      <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"/>
                      </svg>
                      Activity Log
                    </button>
                  </div>

                  <span class="text-gray-400 font-medium">Message ID</span>
                  <span class="font-mono text-gray-800 break-all">{{ log.provider_message_id }}</span>

                  <span class="text-gray-400 font-medium">Chat JID</span>
                  <span class="font-mono text-gray-800 break-all">{{ log.chat_id }}</span>

                  <span class="text-gray-400 font-medium">Chat type</span>
                  <span class="text-gray-800">{{ log.chat_type }}</span>

                  <span class="text-gray-400 font-medium">Sender</span>
                  <span class="font-mono text-gray-800">{{ log.sender_number ? `+${log.sender_number}` : '—' }}</span>

                  <span class="text-gray-400 font-medium">Push name</span>
                  <span class="text-gray-800">{{ log.push_name || '—' }}</span>

                  <template v-if="log.group_name">
                    <span class="text-gray-400 font-medium">Group</span>
                    <span class="text-gray-800">{{ log.group_name }}</span>
                  </template>

                  <span class="text-gray-400 font-medium">Msg type</span>
                  <span class="text-gray-800 capitalize">{{ log.message_type }}</span>

                  <template v-if="log.message_text">
                    <span class="text-gray-400 font-medium self-start">Text</span>
                    <span class="text-gray-800 whitespace-pre-wrap break-all">{{ log.message_text }}</span>
                  </template>

                  <template v-if="log.has_media">
                    <span class="text-gray-400 font-medium">Media type</span>
                    <span class="text-gray-800">{{ log.media_mime_type || '—' }}</span>
                  </template>

                  <template v-if="log.forward_error">
                    <span class="text-gray-400 font-medium">Error</span>
                    <span class="text-red-600 font-semibold">{{ log.forward_error }}</span>
                  </template>
                </div>

                <!-- Raw payload -->
                <div v-if="log.raw_payload">
                  <div class="flex items-center justify-between mb-2">
                    <span class="text-xs font-semibold text-gray-400 uppercase tracking-wide">Raw Payload</span>
                    <button
                      @click.stop="copyPayload(log)"
                      class="flex items-center gap-1 text-xs px-2 py-0.5 rounded border border-gray-200 hover:bg-white transition-colors text-gray-500"
                    >
                      <svg v-if="copiedId !== log.provider_message_id" class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"/>
                      </svg>
                      <svg v-else class="w-3 h-3 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
                      </svg>
                      {{ copiedId === log.provider_message_id ? 'Copied!' : 'Copy' }}
                    </button>
                  </div>
                  <pre class="bg-gray-900 text-green-400 text-xs rounded-lg p-3 overflow-x-auto max-h-80 leading-relaxed">{{ JSON.stringify(log.raw_payload, null, 2) }}</pre>
                </div>

              </td>
            </tr>
          </template>
        </tbody>
      </table>

      <!-- Pagination -->
      <div v-if="totalCount > 0" class="flex items-center justify-between px-4 py-3 border-t border-gray-100 bg-gray-50 text-sm text-gray-500">
        <span>Showing {{ pageStart.toLocaleString() }}–{{ pageEnd.toLocaleString() }} of {{ totalCount.toLocaleString() }}</span>
        <div class="flex items-center gap-1">
          <button @click="page--" :disabled="page === 1"
            class="px-3 py-1.5 rounded-lg border border-gray-200 text-xs disabled:opacity-40 hover:bg-white transition-colors"
          >← Prev</button>
          <span class="px-3 py-1.5 text-xs">Page {{ page }} of {{ totalPages }}</span>
          <button @click="page++" :disabled="page >= totalPages"
            class="px-3 py-1.5 rounded-lg border border-gray-200 text-xs disabled:opacity-40 hover:bg-white transition-colors"
          >Next →</button>
        </div>
      </div>
    </div>

  </div>
  </div>

  <!-- Clear confirmation -->
  <Teleport to="body">
    <div v-if="showClear" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" @click.self="showClear = false">
      <div class="bg-white rounded-xl shadow-xl w-full max-w-sm p-6 flex flex-col gap-4">
        <h2 class="text-lg font-semibold text-gray-900">Clear Message Logs</h2>
        <p class="text-sm text-gray-600">
          Permanently delete all {{ totalCount.toLocaleString() }} node-level log entries for
          <strong>{{ selectedAccountObj?.display_name || selectedAccountObj?.phone_number || 'this account' }}</strong>.
          This cannot be undone.
        </p>
        <div class="flex gap-3">
          <button @click="showClear = false" class="flex-1 border border-gray-200 text-gray-700 text-sm py-2 rounded-lg hover:bg-gray-50">Cancel</button>
          <button @click="clearLogs" :disabled="clearing" class="flex-1 bg-red-600 hover:bg-red-700 disabled:opacity-50 text-white text-sm py-2 rounded-lg">
            {{ clearing ? 'Clearing…' : 'Clear Logs' }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>
