<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { baileysEventsApi, accountsApi } from '@/api'

const events = ref([])
const accounts = ref([])
const loading = ref(false)
const expandedId = ref(null)
const copiedId = ref(null)

const filterAccount = ref('all')
const filterStage = ref('all')
const filterStatus = ref('all')
const search = ref('')

const page = ref(1)
const pageSize = ref(25)
const totalCount = ref(0)
const pageSizeOptions = [10, 25, 50, 100]

const totalPages = computed(() => Math.max(1, Math.ceil(totalCount.value / pageSize.value)))
const pageStart = computed(() => totalCount.value === 0 ? 0 : (page.value - 1) * pageSize.value + 1)
const pageEnd = computed(() => Math.min(page.value * pageSize.value, totalCount.value))

let pollTimer = null
let searchTimer = null

function buildParams() {
  const p = { page: page.value, page_size: pageSize.value }
  if (filterAccount.value !== 'all') p.account = filterAccount.value
  if (filterStage.value !== 'all') p.event_stage = filterStage.value
  if (filterStatus.value !== 'all') p.status = filterStatus.value
  if (search.value.trim()) p.search = search.value.trim()
  return p
}

async function fetchEvents(showSpinner = false) {
  if (showSpinner) loading.value = true
  try {
    const { data } = await baileysEventsApi.list(buildParams())
    events.value = data.results
    totalCount.value = data.count
  } finally {
    loading.value = false
  }
}

async function fetchAccounts() {
  const { data } = await accountsApi.list()
  accounts.value = data.results ?? data
}

watch([filterAccount, filterStage, filterStatus, pageSize], () => {
  page.value = 1
  fetchEvents()
})
watch(search, () => {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    page.value = 1
    fetchEvents()
  }, 300)
})
watch(page, () => fetchEvents())

onMounted(() => {
  fetchAccounts()
  fetchEvents(true)
  pollTimer = setInterval(() => fetchEvents(), 8000)
})
onUnmounted(() => {
  clearInterval(pollTimer)
  clearTimeout(searchTimer)
})

function toggleRow(id) {
  expandedId.value = expandedId.value === id ? null : id
}

function formatTime(dt) {
  if (!dt) return ''
  return new Date(dt).toLocaleString()
}

function relativeTime(dt) {
  const diff = Math.floor((Date.now() - new Date(dt)) / 1000)
  if (diff < 60) return `${diff}s ago`
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  return `${Math.floor(diff / 86400)}d ago`
}

function statusClass(status) {
  if (status === 'success') return 'bg-green-100 text-green-700'
  if (status === 'failure') return 'bg-red-100 text-red-700'
  if (status === 'skipped') return 'bg-yellow-100 text-yellow-700'
  return 'bg-blue-100 text-blue-700'
}

function stageClass(stage) {
  if (stage === 'failed') return 'text-red-700'
  if (stage === 'forwarded') return 'text-green-700'
  if (stage === 'filtered') return 'text-yellow-700'
  return 'text-gray-700'
}

function displayJid(event) {
  return event.participant_pn || event.participant_jid || event.remote_jid || event.raw_jid || '-'
}

async function copyJson(event) {
  const payload = {
    raw_key: event.raw_key,
    raw_payload: event.raw_payload,
    metadata: event.metadata,
  }
  await navigator.clipboard.writeText(JSON.stringify(payload, null, 2))
  copiedId.value = event.id
  setTimeout(() => { copiedId.value = null }, 1500)
}
</script>

<template>
  <div class="h-full w-full overflow-y-auto bg-gray-50">
    <div class="max-w-7xl mx-auto px-6 py-6">
      <div class="flex items-center justify-between mb-6">
        <div>
          <h1 class="text-2xl font-bold text-gray-900">Baileys Event Log</h1>
          <p class="text-sm text-gray-500 mt-1">
            Per-message WhatsApp worker audit trail from Baileys receipt through Django ingest.
          </p>
        </div>
      </div>

      <div class="flex items-center gap-3 mb-4 flex-wrap">
        <select v-model="filterAccount" class="border border-gray-200 rounded-lg px-3 py-1.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-green-500 min-w-[160px]">
          <option value="all">All accounts</option>
          <option v-for="acc in accounts" :key="acc.id" :value="acc.id">
            {{ acc.display_name || acc.phone_number || `Account #${acc.id}` }}
          </option>
        </select>

        <select v-model="filterStage" class="border border-gray-200 rounded-lg px-3 py-1.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-green-500">
          <option value="all">All stages</option>
          <option value="received">Received</option>
          <option value="history">History</option>
          <option value="filtered">Filtered</option>
          <option value="forwarded">Forwarded</option>
          <option value="failed">Failed</option>
          <option value="internal">Internal</option>
        </select>

        <select v-model="filterStatus" class="border border-gray-200 rounded-lg px-3 py-1.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-green-500">
          <option value="all">All statuses</option>
          <option value="info">Info</option>
          <option value="success">Success</option>
          <option value="failure">Failure</option>
          <option value="skipped">Skipped</option>
        </select>

        <input
          v-model="search"
          class="border border-gray-200 rounded-lg px-3 py-1.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-green-500 min-w-[260px]"
          placeholder="Search message id, JID, phone, push name..."
        />

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

      <div class="bg-white rounded-xl border border-gray-200 overflow-hidden shadow-sm">
        <div v-if="loading" class="text-center text-gray-400 py-12 text-sm">Loading...</div>
        <div v-else-if="!events.length" class="text-center text-gray-400 py-12 text-sm">No Baileys events found.</div>
        <table v-else class="w-full text-sm">
          <thead class="bg-gray-50 text-xs uppercase text-gray-500 border-b border-gray-200">
            <tr>
              <th class="px-4 py-3 text-left font-semibold">Created</th>
              <th class="px-4 py-3 text-left font-semibold">Account</th>
              <th class="px-4 py-3 text-left font-semibold">Stage / Event</th>
              <th class="px-4 py-3 text-left font-semibold">Message ID</th>
              <th class="px-4 py-3 text-left font-semibold">JID / Sender</th>
              <th class="px-4 py-3 text-left font-semibold">Status</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-100">
            <template v-for="event in events" :key="event.id">
              <tr class="hover:bg-gray-50 cursor-pointer" @click="toggleRow(event.id)">
                <td class="px-4 py-3 text-gray-500 whitespace-nowrap">{{ relativeTime(event.created_at) }}</td>
                <td class="px-4 py-3">{{ event.account_name || '-' }}</td>
                <td class="px-4 py-3">
                  <div :class="['font-medium', stageClass(event.event_stage)]">{{ event.event_stage }}</div>
                  <div class="text-xs text-gray-500">{{ event.event_type }}</div>
                </td>
                <td class="px-4 py-3 font-mono text-xs max-w-[240px] truncate">{{ event.provider_message_id || '-' }}</td>
                <td class="px-4 py-3 max-w-[280px] truncate">
                  <div class="font-mono text-xs">{{ displayJid(event) }}</div>
                  <div v-if="event.push_name" class="text-xs text-gray-500 truncate">{{ event.push_name }}</div>
                </td>
                <td class="px-4 py-3">
                  <span :class="['px-2 py-1 rounded-full text-xs font-medium', statusClass(event.status)]">{{ event.status }}</span>
                  <div v-if="event.reason" class="text-xs text-gray-500 mt-1">{{ event.reason }}</div>
                </td>
              </tr>
              <tr v-if="expandedId === event.id" class="bg-gray-50">
                <td colspan="6" class="px-6 py-4">
                  <div class="grid grid-cols-2 gap-x-8 gap-y-2 text-sm mb-4">
                    <div><span class="text-gray-400">Created:</span> {{ formatTime(event.created_at) }}</div>
                    <div><span class="text-gray-400">Django Message:</span> {{ event.django_message_id || '-' }}</div>
                    <div><span class="text-gray-400">Remote JID:</span> {{ event.remote_jid || '-' }}</div>
                    <div><span class="text-gray-400">Participant:</span> {{ event.participant_jid || '-' }}</div>
                    <div><span class="text-gray-400">Participant PN:</span> {{ event.participant_pn || '-' }}</div>
                    <div><span class="text-gray-400">Direction:</span> {{ event.direction || '-' }}</div>
                    <div><span class="text-gray-400">Type:</span> {{ event.message_type || '-' }}</div>
                    <div><span class="text-gray-400">Upsert:</span> {{ event.upsert_type || '-' }}</div>
                  </div>
                  <div v-if="event.error_message" class="mb-4 p-3 rounded-lg bg-red-50 text-red-700 border border-red-100">
                    {{ event.error_message }}
                  </div>
                  <button
                    @click.stop="copyJson(event)"
                    class="mb-3 px-3 py-1.5 text-xs rounded-lg border border-gray-200 hover:bg-white"
                  >
                    {{ copiedId === event.id ? 'Copied' : 'Copy Raw JSON' }}
                  </button>
                  <pre class="bg-gray-900 text-green-400 rounded-lg p-4 overflow-auto max-h-72 text-xs">{{ JSON.stringify({ raw_key: event.raw_key, raw_payload: event.raw_payload, metadata: event.metadata }, null, 2) }}</pre>
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>

      <div class="flex items-center justify-between mt-4 text-sm text-gray-500">
        <span>Showing {{ pageStart }}-{{ pageEnd }} of {{ totalCount.toLocaleString() }}</span>
        <div class="flex items-center gap-2">
          <button :disabled="page <= 1" @click="page--" class="px-3 py-1.5 border border-gray-200 rounded-lg disabled:opacity-40 hover:bg-white">Previous</button>
          <span>Page {{ page }} of {{ totalPages }}</span>
          <button :disabled="page >= totalPages" @click="page++" class="px-3 py-1.5 border border-gray-200 rounded-lg disabled:opacity-40 hover:bg-white">Next</button>
        </div>
      </div>
    </div>
  </div>
</template>
