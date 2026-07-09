<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { tradingApi, accountsApi } from '@/api'

const logs      = ref([])
const accounts  = ref([])
const loading   = ref(false)
const expandedId = ref(null)

const filterAccount = ref('all')
const filterStatus  = ref('all')
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
  no_text:            'No text content',
  outbound:           'Outbound message',
  too_old:            'Older than 24h',
  chat_disabled:      'AI off for chat',
  account_disabled:   'AI off for account',
  duplicate_broadcast: 'Duplicate group broadcast',
}

const REASON_STYLE = {
  no_text:            'bg-gray-100 text-gray-500',
  outbound:           'bg-gray-100 text-gray-500',
  too_old:            'bg-gray-100 text-gray-500',
  chat_disabled:      'bg-purple-100 text-purple-700 font-semibold',
  account_disabled:   'bg-purple-100 text-purple-700 font-semibold',
  duplicate_broadcast: 'bg-amber-100 text-amber-700 font-semibold',
}

function reasonLabel(r) { return REASON_LABELS[r] || r }
function reasonStyle(r) { return REASON_STYLE[r] || 'bg-gray-100 text-gray-600' }

function buildParams() {
  const p = { page: page.value, page_size: pageSize.value }
  if (filterAccount.value !== 'all') p.account     = filterAccount.value
  if (filterStatus.value  !== 'all') p.status      = filterStatus.value
  if (filterReason.value  !== 'all') p.skip_reason = filterReason.value
  return p
}

async function fetchLogs(showSpinner = false) {
  if (showSpinner) loading.value = true
  try {
    const { data } = await tradingApi.listAiParsingLogs(buildParams())
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

watch([filterAccount, filterStatus, filterReason, pageSize], () => { page.value = 1; fetchLogs() })
watch(page, () => fetchLogs())

onMounted(() => {
  fetchAccounts()
  fetchLogs(true)
  pollTimer = setInterval(() => fetchLogs(), 8000)
})
onUnmounted(() => clearInterval(pollTimer))

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
</script>

<template>
  <div class="h-full w-full overflow-y-auto bg-gray-50">
  <div class="max-w-7xl mx-auto px-6 py-6">

    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-2xl font-bold text-gray-900">AI Parsing Log</h1>
        <p class="text-sm text-gray-500 mt-1">
          Every inbound message and whether it was sent for AI classification or skipped, and why
        </p>
      </div>
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
        v-model="filterStatus"
        class="border border-gray-200 rounded-lg px-3 py-1.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-green-500"
      >
        <option value="all">All statuses</option>
        <option value="sent">Sent for AI Parsing</option>
        <option value="skipped">Skipped</option>
      </select>

      <select
        v-model="filterReason"
        class="border border-gray-200 rounded-lg px-3 py-1.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-green-500"
      >
        <option value="all">All skip reasons</option>
        <option value="no_text">No text content</option>
        <option value="outbound">Outbound message</option>
        <option value="too_old">Older than 24h</option>
        <option value="chat_disabled">AI off for chat</option>
        <option value="account_disabled">AI off for account</option>
        <option value="duplicate_broadcast">Duplicate group broadcast</option>
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
        No AI parsing activity recorded
      </div>

      <table v-else class="w-full text-sm">
        <thead>
          <tr class="bg-gray-50 border-b border-gray-100 text-xs text-gray-500 uppercase tracking-wide">
            <th class="text-left px-4 py-3 w-28">Time</th>
            <th class="text-left px-4 py-3 w-36">Account</th>
            <th class="text-left px-4 py-3 w-32">Status</th>
            <th class="text-left px-4 py-3 w-40">Reason</th>
            <th class="text-left px-4 py-3 w-36">Chat</th>
            <th class="text-left px-4 py-3">Message</th>
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
                <span
                  class="text-xs font-medium px-2 py-0.5 rounded-full"
                  :class="log.status === 'sent' ? 'bg-green-100 text-green-700' : 'bg-yellow-100 text-yellow-700'"
                >{{ log.status === 'sent' ? 'Sent' : 'Skipped' }}</span>
              </td>
              <td class="px-4 py-2.5">
                <span v-if="log.skip_reason" :class="['text-xs font-medium px-2 py-0.5 rounded-full', reasonStyle(log.skip_reason)]">
                  {{ reasonLabel(log.skip_reason) }}
                </span>
                <span v-else class="text-xs text-gray-300">—</span>
              </td>
              <td class="px-4 py-2.5">
                <span class="text-xs text-gray-700 truncate block max-w-[130px]">{{ log.chat_name || '—' }}</span>
              </td>
              <td class="px-4 py-2.5">
                <span class="text-gray-500 text-xs truncate block max-w-md">
                  {{ log.message_preview || '(no text)' }}
                </span>
              </td>
            </tr>

            <!-- Expanded detail -->
            <tr v-if="expandedId === log.id" :key="`${log.id}-detail`">
              <td colspan="6" class="px-6 py-4 bg-gray-50 border-t border-gray-100">
                <div class="grid grid-cols-2 gap-x-8 gap-y-1.5 text-xs max-w-3xl">
                  <div class="col-span-2 flex items-center gap-4 pb-2 mb-1 border-b border-gray-200 flex-wrap">
                    <span class="text-gray-500">{{ formatTime(log.created_at) }}</span>
                    <span class="font-semibold text-gray-800">{{ log.account_name }}</span>
                    <span
                      class="font-medium px-2 py-0.5 rounded-full"
                      :class="log.status === 'sent' ? 'bg-green-100 text-green-700' : 'bg-yellow-100 text-yellow-700'"
                    >{{ log.status === 'sent' ? 'Sent for AI Parsing' : 'Skipped' }}</span>
                    <span v-if="log.skip_reason" :class="['font-medium px-2 py-0.5 rounded-full', reasonStyle(log.skip_reason)]">
                      {{ reasonLabel(log.skip_reason) }}
                    </span>
                  </div>

                  <span class="text-gray-400 font-medium">Message ID</span>
                  <span class="font-mono text-gray-800">{{ log.message }}</span>

                  <span class="text-gray-400 font-medium">Chat</span>
                  <span class="text-gray-800">{{ log.chat_name || '—' }}</span>

                  <span class="text-gray-400 font-medium">Direction</span>
                  <span class="text-gray-800">{{ log.direction || '—' }}</span>

                  <span class="text-gray-400 font-medium">Message time</span>
                  <span class="text-gray-800">{{ formatTime(log.message_time) }}</span>

                  <span class="text-gray-400 font-medium col-span-2">Preview</span>
                  <span class="col-span-2 text-gray-800 whitespace-pre-wrap break-words">{{ log.message_preview || '(no text)' }}</span>
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
</template>
