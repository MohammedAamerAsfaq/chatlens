<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { droppedApi, accountsApi } from '@/api'

const logs        = ref([])
const accounts    = ref([])
const loading     = ref(false)
const clearing    = ref(false)
const showClearConfirm = ref(false)
const expandedId  = ref(null)
const copiedId    = ref(null)

const filterAccount = ref('all')
const filterReason  = ref('all')

const page            = ref(1)
const pageSize        = ref(25)
const totalCount      = ref(0)
const pageSizeOptions = [10, 25, 50, 100]

const totalPages = computed(() => Math.max(1, Math.ceil(totalCount.value / pageSize.value)))
const pageStart  = computed(() => totalCount.value === 0 ? 0 : (page.value - 1) * pageSize.value + 1)
const pageEnd    = computed(() => Math.min(page.value * pageSize.value, totalCount.value))

let pollTimer = null

const REASON_LABELS = {
  no_remote_jid:                'No JID',
  no_message_content:           'No Content',
  prepend_no_content:           'Prepend: No Content',
  forward_failed:               'Forward Failed',
  build_error:                  'Build Error',
  protocolMessage:              'Protocol Msg',
  senderKeyDistributionMessage: 'Key Distribution',
  unresolvable_lid:             'Unresolvable LID',
  'status@broadcast':           'Status Broadcast',
}

const REASON_STYLE = {
  no_remote_jid:                'bg-red-100 text-red-700',
  no_message_content:           'bg-yellow-100 text-yellow-700',
  prepend_no_content:           'bg-orange-100 text-orange-700',
  forward_failed:               'bg-red-100 text-red-800 font-semibold',
  build_error:                  'bg-red-100 text-red-800 font-semibold',
  protocolMessage:              'bg-gray-100 text-gray-500',
  senderKeyDistributionMessage: 'bg-gray-100 text-gray-500',
  unresolvable_lid:             'bg-purple-100 text-purple-700 font-semibold',
  'status@broadcast':           'bg-gray-100 text-gray-400',
}

// messageStubType reasons are dynamic (e.g. "messageStubType:10")
function reasonLabel(r) {
  if (REASON_LABELS[r]) return REASON_LABELS[r]
  if (r?.startsWith('messageStubType:')) return `Stub #${r.split(':')[1]}`
  return r
}
function reasonStyle(r) { return REASON_STYLE[r] || 'bg-gray-100 text-gray-600' }

function buildParams() {
  const p = { page: page.value, page_size: pageSize.value }
  if (filterAccount.value !== 'all') p.account = filterAccount.value
  if (filterReason.value  !== 'all') p.reason  = filterReason.value
  return p
}

async function fetchLogs(showSpinner = false) {
  if (showSpinner) loading.value = true
  try {
    const { data } = await droppedApi.list(buildParams())
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

watch([filterAccount, filterReason, pageSize], () => { page.value = 1; fetchLogs() })
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
    await droppedApi.clearAll(params)
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

function toggleRow(id) {
  expandedId.value = expandedId.value === id ? null : id
}

async function copyKey(log) {
  if (!log.raw_key) return
  try {
    await navigator.clipboard.writeText(JSON.stringify(log.raw_key, null, 2))
    copiedId.value = log.id
    setTimeout(() => { copiedId.value = null }, 1500)
  } catch {}
}

function jidDisplay(raw_jid) {
  if (!raw_jid) return '—'
  const local = String(raw_jid).split('@')[0]
  return `+${local}`
}
</script>

<template>
  <div class="h-full w-full overflow-y-auto bg-gray-50">
  <div class="max-w-7xl mx-auto px-6 py-6">

    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-2xl font-bold text-gray-900">Dropped Messages Log</h1>
        <p class="text-sm text-gray-500 mt-1">
          Messages dropped by the WhatsApp worker before reaching Django
        </p>
      </div>
      <button
        @click="showClearConfirm = true"
        class="flex items-center gap-1.5 px-3 py-1.5 text-sm text-red-600 border border-red-200 rounded-lg hover:bg-red-50 transition-colors"
      >
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
        </svg>
        {{ filterAccount !== 'all' ? 'Clear Account' : 'Clear All' }}
      </button>
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

      <select
        v-model="filterReason"
        class="border border-gray-200 rounded-lg px-3 py-1.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-green-500"
      >
        <option value="all">All reasons</option>
        <optgroup label="— Live message drops —">
          <option value="forward_failed">Forward Failed</option>
          <option value="build_error">Build Error</option>
          <option value="no_remote_jid">No JID</option>
          <option value="no_message_content">No Content</option>
        </optgroup>
        <optgroup label="— Filtered (expected) —">
          <option value="protocolMessage">Protocol Msg</option>
          <option value="senderKeyDistributionMessage">Key Distribution</option>
          <option value="status@broadcast">Status Broadcast</option>
          <option value="prepend_no_content">Prepend: No Content</option>
        </optgroup>
      </select>

      <span class="text-sm text-gray-400 flex-1">{{ totalCount.toLocaleString() }} entries</span>

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

    <!-- Table -->
    <div class="bg-white rounded-xl border border-gray-200 overflow-hidden shadow-sm">
      <div v-if="loading" class="text-center text-gray-400 py-12 text-sm">Loading…</div>

      <div v-else-if="logs.length === 0" class="text-center text-gray-400 py-12 text-sm">
        No dropped messages recorded
      </div>

      <table v-else class="w-full text-sm">
        <thead>
          <tr class="bg-gray-50 border-b border-gray-100 text-xs text-gray-500 uppercase tracking-wide">
            <th class="text-left px-4 py-3 w-28">Time</th>
            <th class="text-left px-4 py-3 w-36">Account</th>
            <th class="text-left px-4 py-3 w-40">Reason</th>
            <th class="text-left px-4 py-3 w-36">JID</th>
            <th class="text-left px-4 py-3 w-20">Dir</th>
            <th class="text-left px-4 py-3">Msg ID</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-gray-50">
          <template v-for="log in logs" :key="log.id">
            <tr
              @click="toggleRow(log.id)"
              :class="[
                'cursor-pointer transition-colors',
                expandedId === log.id ? 'bg-gray-100' : 'hover:bg-gray-50',
              ]"
            >
              <td class="px-4 py-2.5">
                <span class="text-gray-500 text-xs" :title="formatTime(log.created_at)">
                  {{ relativeTime(log.created_at) }}
                </span>
              </td>
              <td class="px-4 py-2.5">
                <span class="text-xs text-gray-700 truncate block max-w-[130px]">{{ log.account_name }}</span>
              </td>
              <td class="px-4 py-2.5">
                <span :class="['text-xs font-medium px-2 py-0.5 rounded-full', reasonStyle(log.reason)]">
                  {{ reasonLabel(log.reason) }}
                </span>
              </td>
              <td class="px-4 py-2.5">
                <span class="text-xs font-mono text-gray-700">{{ jidDisplay(log.raw_jid) }}</span>
              </td>
              <td class="px-4 py-2.5">
                <span class="text-xs text-gray-500">
                  {{ log.from_me === true ? 'out' : log.from_me === false ? 'in' : '—' }}
                </span>
              </td>
              <td class="px-4 py-2.5">
                <div class="flex items-center justify-between gap-2">
                  <span class="text-gray-400 font-mono text-xs truncate">
                    {{ log.msg_id ? log.msg_id.slice(0, 20) + '…' : '—' }}
                  </span>
                  <svg
                    :class="['w-3.5 h-3.5 text-gray-400 shrink-0 transition-transform', expandedId === log.id ? 'rotate-180' : '']"
                    fill="none" stroke="currentColor" viewBox="0 0 24 24"
                  >
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/>
                  </svg>
                </div>
              </td>
            </tr>

            <!-- Expanded detail -->
            <tr v-if="expandedId === log.id" :key="`${log.id}-detail`">
              <td colspan="6" class="px-6 py-4 bg-gray-50 border-t border-gray-100">
                <div class="grid grid-cols-2 gap-x-8 gap-y-1.5 text-xs max-w-3xl">
                  <div class="col-span-2 flex items-center gap-4 pb-2 mb-1 border-b border-gray-200 flex-wrap">
                    <span class="text-gray-500">{{ formatTime(log.created_at) }}</span>
                    <span class="font-semibold text-gray-800">{{ log.account_name }}</span>
                    <span :class="['font-medium px-2 py-0.5 rounded-full', reasonStyle(log.reason)]">{{ reasonLabel(log.reason) }}</span>
                  </div>

                  <span class="text-gray-400 font-medium">Msg ID</span>
                  <span class="font-mono text-gray-800 break-all">{{ log.msg_id || '—' }}</span>

                  <span class="text-gray-400 font-medium">Raw JID</span>
                  <span class="font-mono text-gray-800">{{ log.raw_jid || '—' }}</span>

                  <span class="text-gray-400 font-medium">Direction</span>
                  <span class="text-gray-800">{{ log.from_me === true ? 'outbound' : log.from_me === false ? 'inbound' : '—' }}</span>

                  <span class="text-gray-400 font-medium">Has message</span>
                  <span :class="log.has_message ? 'text-green-700' : 'text-red-600'">
                    {{ log.has_message ? 'yes' : 'no' }}
                  </span>
                </div>

                <!-- raw_key -->
                <div v-if="log.raw_key" class="mt-4">
                  <div class="flex items-center justify-between mb-2">
                    <span class="text-xs font-semibold text-gray-400 uppercase tracking-wide">Raw Key</span>
                    <button
                      @click.stop="copyKey(log)"
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
                  <pre class="bg-gray-900 text-green-400 text-xs rounded-lg p-3 overflow-x-auto max-h-48 leading-relaxed">{{ JSON.stringify(log.raw_key, null, 2) }}</pre>
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
          <button
            @click="page--"
            :disabled="page === 1"
            class="px-3 py-1.5 rounded-lg border border-gray-200 text-xs disabled:opacity-40 hover:bg-white transition-colors"
          >← Prev</button>
          <span class="px-3 py-1.5 text-xs">Page {{ page }} of {{ totalPages }}</span>
          <button
            @click="page++"
            :disabled="page >= totalPages"
            class="px-3 py-1.5 rounded-lg border border-gray-200 text-xs disabled:opacity-40 hover:bg-white transition-colors"
          >Next →</button>
        </div>
      </div>
    </div>
  </div>
  </div>

  <!-- Clear confirm dialog -->
  <Teleport to="body">
    <div
      v-if="showClearConfirm"
      class="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
      @click.self="showClearConfirm = false"
    >
      <div class="bg-white rounded-xl shadow-xl w-full max-w-sm p-6 flex flex-col gap-4">
        <h2 class="text-lg font-semibold text-gray-900">Clear Dropped Messages Log</h2>
        <p class="text-sm text-gray-600">
          <template v-if="filterAccount !== 'all'">
            Delete all {{ totalCount.toLocaleString() }} entries for
            <strong>{{ accounts.find(a => a.id == filterAccount)?.display_name || accounts.find(a => a.id == filterAccount)?.phone_number || 'this account' }}</strong>.
          </template>
          <template v-else>
            Delete all {{ totalCount.toLocaleString() }} entries across all accounts.
          </template>
          This cannot be undone.
        </p>
        <div class="flex gap-3">
          <button
            @click="showClearConfirm = false"
            class="flex-1 border border-gray-200 text-gray-700 text-sm py-2 rounded-lg hover:bg-gray-50 transition-colors"
          >Cancel</button>
          <button
            @click="clearLogs"
            :disabled="clearing"
            class="flex-1 bg-red-600 hover:bg-red-700 disabled:opacity-50 text-white text-sm py-2 rounded-lg transition-colors"
          >{{ clearing ? 'Clearing…' : 'Clear' }}</button>
        </div>
      </div>
    </div>
  </Teleport>
</template>
