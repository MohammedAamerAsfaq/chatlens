<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { activityApi, accountsApi } from '@/api'

const route  = useRoute()
const router = useRouter()

const logs        = ref([])
const accounts    = ref([])
const loading     = ref(false)
const clearing    = ref(false)
const showClearConfirm = ref(false)
const expandedId  = ref(null)
const copiedId    = ref(null)

// Filters
const filterAccount = ref('all')
const filterStatus  = ref('all')
const filterEvent   = ref('all')

// Pagination
const page            = ref(1)
const pageSize        = ref(25)
const totalCount      = ref(0)
const pageSizeOptions = [10, 25, 50, 100]

const totalPages = computed(() => Math.max(1, Math.ceil(totalCount.value / pageSize.value)))
const pageStart  = computed(() => totalCount.value === 0 ? 0 : (page.value - 1) * pageSize.value + 1)
const pageEnd    = computed(() => Math.min(page.value * pageSize.value, totalCount.value))

let pollTimer = null

// message_id filter — set by incoming cross-link from Message Logs page
const filterMessageId = ref(route.query.message_id || '')

function buildParams() {
  const p = { page: page.value, page_size: pageSize.value }
  if (filterAccount.value  !== 'all') p.account     = filterAccount.value
  if (filterStatus.value   !== 'all') p.status       = filterStatus.value
  if (filterEvent.value    !== 'all') p.event_type   = filterEvent.value
  if (filterMessageId.value)          p.message_id   = filterMessageId.value
  return p
}

function goToMessageLogs(log) {
  router.push({
    name: 'message-logs',
    query: { account_id: log.account_id, message_id: (log.metadata || {}).provider_message_id },
  })
}

async function fetchLogs(showSpinner = false) {
  if (showSpinner) loading.value = true
  try {
    const { data } = await activityApi.list(buildParams())
    logs.value       = data.results
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

watch([filterAccount, filterStatus, filterEvent, filterMessageId, pageSize], () => {
  page.value = 1
  fetchLogs()
})
watch(page, () => fetchLogs())

onMounted(() => {
  fetchAccounts()
  fetchLogs(true)
  pollTimer = setInterval(() => fetchLogs(), 8000)
})
onUnmounted(() => clearInterval(pollTimer))

async function clearLogs() {
  clearing.value = true
  try {
    const params = filterAccount.value !== 'all' ? { account: filterAccount.value } : {}
    await activityApi.clearAll(params)
    page.value = 1
    await fetchLogs()
  } finally {
    clearing.value = false
    showClearConfirm.value = false
  }
}

function formatTime(dt) {
  if (!dt) return ''
  return new Date(dt).toLocaleString()
}

function relativeTime(dt) {
  const diff = Math.floor((Date.now() - new Date(dt)) / 1000)
  if (diff < 60)    return `${diff}s ago`
  if (diff < 3600)  return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  return `${Math.floor(diff / 86400)}d ago`
}

const statusStyle = {
  success: 'bg-green-100 text-green-700',
  error:   'bg-red-100 text-red-700',
  warning: 'bg-yellow-100 text-yellow-700',
}
const eventStyle = {
  message_ingest: 'bg-blue-100 text-blue-700',
  session_status: 'bg-purple-100 text-purple-700',
  history_sync:   'bg-orange-100 text-orange-700',
}

function senderDisplay(log) {
  const m = log.metadata || {}
  // sender_jid is stored as the raw phone number (digits only, no @suffix)
  if (!m.sender_jid) return '—'
  const local = String(m.sender_jid).split('@')[0]
  return `+${local}`
}

function senderName(log) {
  return (log.metadata || {}).push_name || '—'
}

function metaSummary(log) {
  const m = log.metadata || {}
  if (log.event_type === 'message_ingest') {
    const parts = []
    if (m.provider_message_id) parts.push(`msg: ${m.provider_message_id.slice(0, 12)}…`)
    if (m.chat_id) parts.push(`chat: ${String(m.chat_id).split('@')[0].slice(-8)}`)
    if (m.direction) parts.push(m.direction)
    if (m.embedded !== undefined) parts.push(m.embedded ? '⬡ embedded' : '○ not embedded')
    if (m.error) parts.push(`❌ ${m.error}`)
    return parts.join(' · ')
  }
  if (log.event_type === 'history_sync') {
    const parts = [`${m.created ?? 0} new / ${m.skipped ?? 0} skipped`]
    if (m.embedded !== undefined) parts.push(`${m.embedded} embedded${m.embed_errors ? `, ${m.embed_errors} err` : ''}`)
    return parts.join(' · ')
  }
  if (log.event_type === 'session_status') return m.status || log.status
  return log.message || ''
}

function toggleRow(id) {
  expandedId.value = expandedId.value === id ? null : id
}

async function copyPayload(log) {
  const payload = (log.metadata || {}).raw_payload
  if (!payload) return
  try {
    await navigator.clipboard.writeText(JSON.stringify(payload, null, 2))
    copiedId.value = log.id
    setTimeout(() => { copiedId.value = null }, 1500)
  } catch {}
}

function metaRows(log) {
  const m = log.metadata || {}
  const known = new Set([
    'provider_message_id','chat_id','sender_jid','push_name',
    'message_type','message_text','direction','status',
    'phone_number','error','raw_payload','group_name',
    'embedded','embed_errors','total','created','skipped','errors',
  ])
  const rows = []
  if (m.provider_message_id) rows.push({ key: 'Message ID', val: m.provider_message_id })
  if (m.chat_id)             rows.push({ key: 'Chat JID',   val: m.chat_id })
  if (m.sender_jid)          rows.push({ key: 'Sender JID', val: m.sender_jid })
  if (m.push_name)           rows.push({ key: 'Push Name',  val: m.push_name })
  if (m.message_type)        rows.push({ key: 'Msg Type',   val: m.message_type })
  if (m.message_text)        rows.push({ key: 'Text',       val: m.message_text })
  if (m.direction)           rows.push({ key: 'Direction',  val: m.direction })
  if (m.status)              rows.push({ key: 'Status',     val: m.status })
  if (m.phone_number)        rows.push({ key: 'Phone',      val: m.phone_number })
  if (m.group_name)          rows.push({ key: 'Group',      val: m.group_name })
  if (m.total      !== undefined) rows.push({ key: 'Total msgs',    val: String(m.total) })
  if (m.created    !== undefined) rows.push({ key: 'Created',       val: String(m.created) })
  if (m.skipped    !== undefined) rows.push({ key: 'Skipped',       val: String(m.skipped) })
  if (m.errors     !== undefined) rows.push({ key: 'Ingest errors', val: String(m.errors), isError: m.errors > 0 })
  if (m.embedded   !== undefined) rows.push({ key: 'Embedded',      val: m.embedded === true ? 'yes' : m.embedded === false ? 'no' : String(m.embedded) })
  if (m.embed_errors !== undefined) rows.push({ key: 'Embed errors', val: String(m.embed_errors), isError: m.embed_errors > 0 })
  if (m.error)               rows.push({ key: 'Error',      val: m.error, isError: true })
  for (const k of Object.keys(m)) {
    if (!known.has(k)) rows.push({ key: k, val: typeof m[k] === 'object' ? JSON.stringify(m[k], null, 2) : String(m[k]) })
  }
  return rows
}
</script>

<template>
  <div class="h-full w-full overflow-y-auto bg-gray-50">
  <div class="max-w-7xl mx-auto px-6 py-6">

    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-2xl font-bold text-gray-900">Activity Log</h1>
        <p class="text-sm text-gray-500 mt-1">Message ingestion and session events</p>
      </div>
      <button
        @click="showClearConfirm = true"
        class="flex items-center gap-1.5 px-3 py-1.5 text-sm text-red-600 border border-red-200 rounded-lg hover:bg-red-50 transition-colors"
      >
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
        </svg>
        {{ filterAccount !== 'all' ? 'Clear Account Logs' : 'Clear All Logs' }}
      </button>
    </div>

    <!-- Filters + page size -->
    <div class="flex items-center gap-3 mb-4 flex-wrap">

      <!-- Account selector -->
      <select
        v-model="filterAccount"
        class="border border-gray-200 rounded-lg px-3 py-1.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-green-500 min-w-[160px]"
      >
        <option value="all">All accounts</option>
        <option v-for="acc in accounts" :key="acc.id" :value="acc.id">
          {{ acc.display_name || acc.phone_number || `Account #${acc.id}` }}
        </option>
      </select>

      <select v-model="filterStatus" class="border border-gray-200 rounded-lg px-3 py-1.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-green-500">
        <option value="all">All statuses</option>
        <option value="success">Success</option>
        <option value="error">Error</option>
      </select>

      <select v-model="filterEvent" class="border border-gray-200 rounded-lg px-3 py-1.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-green-500">
        <option value="all">All events</option>
        <option value="message_ingest">Message Ingest</option>
        <option value="history_sync">History Sync</option>
        <option value="session_status">Session Status</option>
      </select>

      <span class="text-sm text-gray-400 flex-1">
        {{ totalCount.toLocaleString() }} entries
      </span>

      <!-- Page size -->
      <div class="flex items-center gap-2 text-sm text-gray-500">
        <span>Rows:</span>
        <div class="flex border border-gray-200 rounded-lg overflow-hidden">
          <button
            v-for="n in pageSizeOptions"
            :key="n"
            @click="pageSize = n"
            :class="[
              'px-2.5 py-1 text-xs transition-colors',
              pageSize === n ? 'bg-green-600 text-white' : 'hover:bg-gray-50 text-gray-600',
            ]"
          >{{ n }}</button>
        </div>
      </div>
    </div>

    <!-- Log table -->
    <div class="bg-white rounded-xl border border-gray-200 overflow-hidden shadow-sm">
      <div v-if="loading" class="text-center text-gray-400 py-12 text-sm">Loading…</div>

      <div v-else-if="logs.length === 0" class="text-center text-gray-400 py-12 text-sm">
        No activity yet
      </div>

      <table v-else class="w-full text-sm">
        <thead>
          <tr class="bg-gray-50 border-b border-gray-100 text-xs text-gray-500 uppercase tracking-wide">
            <th class="text-left px-4 py-3 w-28">Time</th>
            <th class="text-left px-4 py-3 w-28">Event</th>
            <th class="text-left px-4 py-3 w-24">Status</th>
            <th class="text-left px-4 py-3 w-36">Sender ID</th>
            <th class="text-left px-4 py-3 w-36">Sender Name</th>
            <th class="text-left px-4 py-3">Details</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-gray-50">
          <template v-for="log in logs" :key="log.id">
            <tr
              @click="toggleRow(log.id)"
              :class="[
                'cursor-pointer transition-colors',
                expandedId === log.id
                  ? 'bg-gray-100'
                  : log.status === 'error'
                    ? 'bg-red-50/40 hover:bg-red-50'
                    : 'hover:bg-gray-50',
              ]"
            >
              <td class="px-4 py-2.5">
                <span class="text-gray-500 text-xs" :title="formatTime(log.created_at)">
                  {{ relativeTime(log.created_at) }}
                </span>
              </td>
              <td class="px-4 py-2.5">
                <span :class="['text-xs font-medium px-2 py-0.5 rounded-full', eventStyle[log.event_type] || 'bg-gray-100 text-gray-600']">
                  {{ log.event_type === 'message_ingest' ? 'Ingest' : log.event_type === 'history_sync' ? 'History' : log.event_type === 'session_status' ? 'Session' : log.event_type }}
                </span>
              </td>
              <td class="px-4 py-2.5">
                <span :class="['text-xs font-medium px-2 py-0.5 rounded-full', statusStyle[log.status] || 'bg-gray-100 text-gray-600']">
                  {{ log.status }}
                </span>
              </td>
              <td class="px-4 py-2.5">
                <span class="text-xs font-mono text-gray-700">{{ senderDisplay(log) }}</span>
              </td>
              <td class="px-4 py-2.5">
                <span class="text-xs text-gray-700 truncate block max-w-[140px]">{{ senderName(log) }}</span>
              </td>
              <td class="px-4 py-2.5">
                <div class="flex items-center justify-between gap-2">
                  <span class="text-gray-500 font-mono text-xs truncate">{{ metaSummary(log) }}</span>
                  <svg
                    :class="['w-3.5 h-3.5 text-gray-400 shrink-0 transition-transform', expandedId === log.id ? 'rotate-180' : '']"
                    fill="none" stroke="currentColor" viewBox="0 0 24 24"
                  >
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/>
                  </svg>
                </div>
              </td>
            </tr>

            <!-- Expanded detail row -->
            <tr v-if="expandedId === log.id" :key="`${log.id}-detail`">
              <td colspan="6" class="px-6 py-4 bg-gray-50 border-t border-gray-100">
                <div class="grid grid-cols-2 gap-x-8 gap-y-1.5 text-xs max-w-4xl">
                  <div class="col-span-2 flex items-center gap-4 pb-2 mb-1 border-b border-gray-200 flex-wrap">
                    <span class="text-gray-500">{{ formatTime(log.created_at) }}</span>
                    <span class="font-semibold text-gray-800">{{ log.account_name }}</span>
                    <span :class="['font-medium px-2 py-0.5 rounded-full', eventStyle[log.event_type] || 'bg-gray-100 text-gray-600']">{{ log.event_type }}</span>
                    <span :class="['font-medium px-2 py-0.5 rounded-full', statusStyle[log.status] || 'bg-gray-100 text-gray-600']">{{ log.status }}</span>
                    <!-- Cross-link → Message Logs (only for message_ingest events with a message ID) -->
                    <button
                      v-if="log.event_type === 'message_ingest' && log.metadata?.provider_message_id"
                      @click.stop="goToMessageLogs(log)"
                      class="ml-auto flex items-center gap-1 text-xs px-2.5 py-1 rounded-lg border border-green-200 text-green-700 hover:bg-green-50 transition-colors"
                      title="View in Message Logs"
                    >
                      <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"/>
                      </svg>
                      Message Logs
                    </button>
                  </div>
                  <template v-if="metaRows(log).length">
                    <div v-for="row in metaRows(log)" :key="row.key" class="contents">
                      <span class="text-gray-400 font-medium py-0.5 self-start">{{ row.key }}</span>
                      <span :class="['font-mono break-all py-0.5', row.isError ? 'text-red-600 font-semibold' : 'text-gray-800']">{{ row.val }}</span>
                    </div>
                  </template>
                  <div v-else class="col-span-2 text-gray-400 italic">No metadata</div>
                  <template v-if="log.message">
                    <span class="text-gray-400 font-medium py-0.5">Message</span>
                    <span class="text-gray-700 py-0.5">{{ log.message }}</span>
                  </template>
                </div>

                <!-- Raw payload -->
                <div v-if="log.metadata?.raw_payload" class="mt-4">
                  <div class="flex items-center justify-between mb-2">
                    <span class="text-xs font-semibold text-gray-400 uppercase tracking-wide">Raw Payload</span>
                    <button
                      @click.stop="copyPayload(log)"
                      class="flex items-center gap-1 text-xs px-2 py-0.5 rounded border border-gray-200 hover:bg-white transition-colors text-gray-500"
                    >
                      <svg v-if="copiedId !== log.id" class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"/>
                      </svg>
                      <svg v-else class="w-3 h-3 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
                      </svg>
                      {{ copiedId === log.id ? 'Copied!' : 'Copy' }}
                    </button>
                  </div>
                  <pre class="bg-gray-900 text-green-400 text-xs rounded-lg p-3 overflow-x-auto max-h-80 leading-relaxed">{{ JSON.stringify(log.metadata.raw_payload, null, 2) }}</pre>
                </div>
              </td>
            </tr>
          </template>
        </tbody>
      </table>

      <!-- Pagination footer -->
      <div v-if="totalCount > 0" class="flex items-center justify-between px-4 py-3 border-t border-gray-100 bg-gray-50 text-sm text-gray-500">
        <span>Showing {{ pageStart.toLocaleString() }}–{{ pageEnd.toLocaleString() }} of {{ totalCount.toLocaleString() }}</span>
        <div class="flex items-center gap-1">
          <button
            @click="page--"
            :disabled="page === 1"
            class="px-3 py-1.5 rounded-lg border border-gray-200 text-xs disabled:opacity-40 hover:bg-white transition-colors"
          >
            ← Prev
          </button>
          <span class="px-3 py-1.5 text-xs">Page {{ page }} of {{ totalPages }}</span>
          <button
            @click="page++"
            :disabled="page >= totalPages"
            class="px-3 py-1.5 rounded-lg border border-gray-200 text-xs disabled:opacity-40 hover:bg-white transition-colors"
          >
            Next →
          </button>
        </div>
      </div>
    </div>
  </div>
  </div>

  <!-- Clear confirmation dialog -->
  <Teleport to="body">
    <div
      v-if="showClearConfirm"
      class="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
      @click.self="showClearConfirm = false"
    >
      <div class="bg-white rounded-xl shadow-xl w-full max-w-sm p-6 flex flex-col gap-4">
        <h2 class="text-lg font-semibold text-gray-900">Clear Activity Logs</h2>
        <p class="text-sm text-gray-600">
          <template v-if="filterAccount !== 'all'">
            This will permanently delete all {{ totalCount.toLocaleString() }} log entries for
            <strong>{{ accounts.find(a => a.id == filterAccount)?.display_name || accounts.find(a => a.id == filterAccount)?.phone_number || 'this account' }}</strong>.
          </template>
          <template v-else>
            This will permanently delete all {{ totalCount.toLocaleString() }} log entries across all accounts.
          </template>
          This cannot be undone.
        </p>
        <div class="flex gap-3">
          <button
            @click="showClearConfirm = false"
            class="flex-1 border border-gray-200 text-gray-700 text-sm py-2 rounded-lg hover:bg-gray-50 transition-colors"
          >
            Cancel
          </button>
          <button
            @click="clearLogs"
            :disabled="clearing"
            class="flex-1 bg-red-600 hover:bg-red-700 disabled:opacity-50 text-white text-sm py-2 rounded-lg transition-colors"
          >
            {{ clearing ? 'Clearing…' : 'Clear Logs' }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>
