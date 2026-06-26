<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { activityApi } from '@/api'

const logs = ref([])
const loading = ref(false)
const filterStatus = ref('all')
const filterEvent = ref('all')
const expandedId = ref(null)
let pollTimer = null

const filtered = computed(() => {
  let list = logs.value
  if (filterStatus.value !== 'all') list = list.filter(l => l.status === filterStatus.value)
  if (filterEvent.value !== 'all') list = list.filter(l => l.event_type === filterEvent.value)
  return list
})

const counts = computed(() => ({
  total: logs.value.length,
  errors: logs.value.filter(l => l.status === 'error').length,
  ingest: logs.value.filter(l => l.event_type === 'message_ingest').length,
  session: logs.value.filter(l => l.event_type === 'session_status').length,
}))

async function fetchLogs() {
  try {
    const { data } = await activityApi.list()
    logs.value = data
  } catch {}
}

async function fetchInitial() {
  loading.value = true
  await fetchLogs()
  loading.value = false
}

onMounted(() => {
  fetchInitial()
  pollTimer = setInterval(fetchLogs, 4000)
})
onUnmounted(() => clearInterval(pollTimer))

function formatTime(dt) {
  if (!dt) return ''
  return new Date(dt).toLocaleString()
}

function relativeTime(dt) {
  const diff = Math.floor((Date.now() - new Date(dt)) / 1000)
  if (diff < 60) return `${diff}s ago`
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  return `${Math.floor(diff / 3600)}h ago`
}

const statusStyle = {
  success: 'bg-green-100 text-green-700',
  error:   'bg-red-100 text-red-700',
  warning: 'bg-yellow-100 text-yellow-700',
}

const eventStyle = {
  message_ingest: 'bg-blue-100 text-blue-700',
  session_status: 'bg-purple-100 text-purple-700',
}

function metaSummary(log) {
  const m = log.metadata || {}
  if (log.event_type === 'message_ingest') {
    const parts = []
    if (m.provider_message_id) parts.push(`msg: ${m.provider_message_id.slice(0, 12)}…`)
    if (m.chat_id) parts.push(`chat: ${String(m.chat_id).split('@')[0].slice(-8)}`)
    if (m.error) parts.push(`❌ ${m.error}`)
    return parts.join(' · ')
  }
  if (log.event_type === 'session_status') {
    return m.status || log.status
  }
  return log.message || ''
}

function toggleRow(id) {
  expandedId.value = expandedId.value === id ? null : id
}

function metaRows(log) {
  const m = log.metadata || {}
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
  if (m.error)               rows.push({ key: 'Error',      val: m.error, isError: true })
  // catch-all for any extra keys
  const known = new Set(['provider_message_id','chat_id','sender_jid','push_name','message_type','message_text','direction','status','phone_number','error'])
  for (const k of Object.keys(m)) {
    if (!known.has(k)) rows.push({ key: k, val: typeof m[k] === 'object' ? JSON.stringify(m[k], null, 2) : String(m[k]) })
  }
  return rows
}
</script>

<template>
  <div class="max-w-6xl mx-auto">
    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-2xl font-bold text-gray-900">Activity Log</h1>
        <p class="text-sm text-gray-500 mt-1">Inbound message ingestion and session events — auto-refreshes every 4s</p>
      </div>
      <div class="flex gap-2 text-xs">
        <span class="bg-gray-100 text-gray-600 px-3 py-1.5 rounded-full font-medium">{{ counts.total }} total</span>
        <span class="bg-red-100 text-red-600 px-3 py-1.5 rounded-full font-medium">{{ counts.errors }} errors</span>
        <span class="bg-blue-100 text-blue-600 px-3 py-1.5 rounded-full font-medium">{{ counts.ingest }} ingests</span>
        <span class="bg-purple-100 text-purple-600 px-3 py-1.5 rounded-full font-medium">{{ counts.session }} sessions</span>
      </div>
    </div>

    <!-- Filters -->
    <div class="flex gap-3 mb-4">
      <select v-model="filterStatus" class="border border-gray-200 rounded-lg px-3 py-1.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-green-500">
        <option value="all">All statuses</option>
        <option value="success">Success</option>
        <option value="error">Error</option>
      </select>
      <select v-model="filterEvent" class="border border-gray-200 rounded-lg px-3 py-1.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-green-500">
        <option value="all">All events</option>
        <option value="message_ingest">Message Ingest</option>
        <option value="session_status">Session Status</option>
      </select>
      <span class="text-sm text-gray-400 self-center">{{ filtered.length }} entries</span>
    </div>

    <!-- Log table -->
    <div class="bg-white rounded-xl border border-gray-200 overflow-hidden shadow-sm">
      <div v-if="loading" class="text-center text-gray-400 py-12 text-sm">Loading...</div>

      <div v-else-if="filtered.length === 0" class="text-center text-gray-400 py-12 text-sm">
        No activity yet
      </div>

      <table v-else class="w-full text-sm">
        <thead>
          <tr class="bg-gray-50 border-b border-gray-100 text-xs text-gray-500 uppercase tracking-wide">
            <th class="text-left px-4 py-3 w-36">Time</th>
            <th class="text-left px-4 py-3 w-28">Account</th>
            <th class="text-left px-4 py-3 w-32">Event</th>
            <th class="text-left px-4 py-3 w-24">Status</th>
            <th class="text-left px-4 py-3">Details</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-gray-50">
          <template v-for="log in filtered" :key="log.id">
            <!-- Main row -->
            <tr
              @click="toggleRow(log.id)"
              :class="[
                'cursor-pointer transition-colors',
                expandedId === log.id ? 'bg-gray-100' : log.status === 'error' ? 'bg-red-50/40 hover:bg-red-50' : 'hover:bg-gray-50',
              ]"
            >
              <!-- Time -->
              <td class="px-4 py-2.5">
                <span class="text-gray-500" :title="formatTime(log.created_at)">
                  {{ relativeTime(log.created_at) }}
                </span>
              </td>

              <!-- Account -->
              <td class="px-4 py-2.5">
                <span class="text-gray-700 font-medium truncate block max-w-[112px]">{{ log.account_name }}</span>
              </td>

              <!-- Event type -->
              <td class="px-4 py-2.5">
                <span :class="['text-xs font-medium px-2 py-0.5 rounded-full', eventStyle[log.event_type] || 'bg-gray-100 text-gray-600']">
                  {{ log.event_type === 'message_ingest' ? 'Ingest' : log.event_type === 'session_status' ? 'Session' : log.event_type }}
                </span>
              </td>

              <!-- Status -->
              <td class="px-4 py-2.5">
                <span :class="['text-xs font-medium px-2 py-0.5 rounded-full', statusStyle[log.status] || 'bg-gray-100 text-gray-600']">
                  {{ log.status }}
                </span>
              </td>

              <!-- Details + expand chevron -->
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
              <td colspan="5" class="px-6 py-4 bg-gray-50 border-t border-gray-100">
                <div class="grid grid-cols-2 gap-x-8 gap-y-1.5 text-xs max-w-4xl">

                  <!-- Fixed fields -->
                  <div class="col-span-2 flex items-center gap-4 pb-2 mb-1 border-b border-gray-200">
                    <span class="text-gray-500">{{ formatTime(log.created_at) }}</span>
                    <span class="font-semibold text-gray-800">{{ log.account_name }}</span>
                    <span :class="['font-medium px-2 py-0.5 rounded-full', eventStyle[log.event_type] || 'bg-gray-100 text-gray-600']">
                      {{ log.event_type }}
                    </span>
                    <span :class="['font-medium px-2 py-0.5 rounded-full', statusStyle[log.status] || 'bg-gray-100 text-gray-600']">
                      {{ log.status }}
                    </span>
                  </div>

                  <!-- Metadata key-value rows -->
                  <template v-if="metaRows(log).length">
                    <div
                      v-for="row in metaRows(log)"
                      :key="row.key"
                      class="contents"
                    >
                      <span class="text-gray-400 font-medium py-0.5 self-start">{{ row.key }}</span>
                      <span
                        :class="['font-mono break-all py-0.5', row.isError ? 'text-red-600 font-semibold' : 'text-gray-800']"
                      >{{ row.val }}</span>
                    </div>
                  </template>

                  <!-- Raw JSON fallback if no structured rows -->
                  <div v-else class="col-span-2 text-gray-400 italic">No metadata</div>

                  <!-- Message field if present -->
                  <template v-if="log.message">
                    <span class="text-gray-400 font-medium py-0.5">Message</span>
                    <span class="text-gray-700 py-0.5">{{ log.message }}</span>
                  </template>

                </div>
              </td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>
  </div>
</template>
