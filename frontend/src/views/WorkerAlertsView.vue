<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { workerAlertsApi, accountsApi } from '@/api'

const logs        = ref([])
const accounts     = ref([])
const loading      = ref(false)
const acknowledging = ref(false)
const expandedId   = ref(null)

const filterAccount     = ref('all')
const filterAlertType   = ref('all')
const filterAcknowledged = ref('false')

const page            = ref(1)
const pageSize        = ref(25)
const totalCount      = ref(0)
const pageSizeOptions = [10, 25, 50, 100]

const totalPages = computed(() => Math.max(1, Math.ceil(totalCount.value / pageSize.value)))
const pageStart  = computed(() => totalCount.value === 0 ? 0 : (page.value - 1) * pageSize.value + 1)
const pageEnd    = computed(() => Math.min(page.value * pageSize.value, totalCount.value))

let pollTimer = null

const ALERT_TYPE_LABELS = {
  decrypt_failure:       'Decrypt Failure',
  handshake_timeout:     'Handshake Timeout',
  history_build_failed:  'History Build Failed',
  batch_persist_failed:  'Batch Persist Failed',
  batch_partial_failure: 'Batch Partial Failure',
  drop_report_failed:    'Drop Report Failed',
  uncaught_exception:    'Uncaught Exception',
  other:                 'Other',
}

const ALERT_TYPE_STYLE = {
  decrypt_failure:       'bg-red-100 text-red-800 font-semibold',
  handshake_timeout:     'bg-orange-100 text-orange-700 font-semibold',
  history_build_failed:  'bg-yellow-100 text-yellow-700',
  batch_persist_failed:  'bg-red-100 text-red-800 font-semibold',
  batch_partial_failure: 'bg-yellow-100 text-yellow-700',
  drop_report_failed:    'bg-purple-100 text-purple-700 font-semibold',
  uncaught_exception:    'bg-red-100 text-red-800 font-semibold',
  other:                 'bg-gray-100 text-gray-600',
}

function typeLabel(t) { return ALERT_TYPE_LABELS[t] || t }
function typeStyle(t) { return ALERT_TYPE_STYLE[t] || 'bg-gray-100 text-gray-600' }

function buildParams() {
  const p = { page: page.value, page_size: pageSize.value }
  if (filterAccount.value !== 'all')      p.account       = filterAccount.value
  if (filterAlertType.value !== 'all')    p.alert_type    = filterAlertType.value
  if (filterAcknowledged.value !== 'all') p.acknowledged  = filterAcknowledged.value
  return p
}

async function fetchLogs(showSpinner = false) {
  if (showSpinner) loading.value = true
  try {
    const { data } = await workerAlertsApi.list(buildParams())
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

watch([filterAccount, filterAlertType, filterAcknowledged, pageSize], () => { page.value = 1; fetchLogs() })
watch(page, () => fetchLogs())

onMounted(() => {
  fetchAccounts()
  fetchLogs(true)
  pollTimer = setInterval(() => fetchLogs(), 8000)
})
onUnmounted(() => clearInterval(pollTimer))

async function acknowledgeOne(alert) {
  try {
    await workerAlertsApi.acknowledge(alert.id)
    await fetchLogs()
  } catch {}
}

async function acknowledgeAll() {
  acknowledging.value = true
  try {
    const params = filterAccount.value !== 'all' ? { account: filterAccount.value } : {}
    await workerAlertsApi.acknowledgeAll(params)
    page.value = 1
    await fetchLogs()
  } finally {
    acknowledging.value = false
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
</script>

<template>
  <div class="h-full w-full overflow-y-auto bg-gray-50">
  <div class="max-w-7xl mx-auto px-6 py-6">

    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-2xl font-bold text-gray-900">Worker Alerts</h1>
        <p class="text-sm text-gray-500 mt-1">
          Structured record of worker-side failures — decrypt errors, handshake timeouts, batch
          persistence failures, uncaught exceptions — that would otherwise only exist in a raw log file.
        </p>
      </div>
      <button
        @click="acknowledgeAll"
        :disabled="acknowledging || totalCount === 0"
        class="flex items-center gap-1.5 px-3 py-1.5 text-sm text-green-700 border border-green-200 rounded-lg hover:bg-green-50 disabled:opacity-40 transition-colors"
      >
        {{ acknowledging ? 'Acknowledging…' : (filterAccount !== 'all' ? 'Acknowledge Account' : 'Acknowledge All') }}
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
        v-model="filterAlertType"
        class="border border-gray-200 rounded-lg px-3 py-1.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-green-500"
      >
        <option value="all">All types</option>
        <option v-for="(label, key) in ALERT_TYPE_LABELS" :key="key" :value="key">{{ label }}</option>
      </select>

      <select
        v-model="filterAcknowledged"
        class="border border-gray-200 rounded-lg px-3 py-1.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-green-500"
      >
        <option value="false">Unacknowledged</option>
        <option value="true">Acknowledged</option>
        <option value="all">All</option>
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
        No worker alerts recorded
      </div>

      <table v-else class="w-full text-sm">
        <thead>
          <tr class="bg-gray-50 border-b border-gray-100 text-xs text-gray-500 uppercase tracking-wide">
            <th class="text-left px-4 py-3 w-28">Time</th>
            <th class="text-left px-4 py-3 w-36">Account</th>
            <th class="text-left px-4 py-3 w-44">Type</th>
            <th class="text-left px-4 py-3">Message</th>
            <th class="text-left px-4 py-3 w-28"></th>
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
                <span class="text-xs text-gray-700 truncate block max-w-[130px]">{{ log.account_name || '—' }}</span>
              </td>
              <td class="px-4 py-2.5">
                <span :class="['text-xs font-medium px-2 py-0.5 rounded-full', typeStyle(log.alert_type)]">
                  {{ typeLabel(log.alert_type) }}
                </span>
                <span
                  v-if="log.acknowledged_at"
                  class="text-xs font-medium px-2 py-0.5 rounded-full bg-green-100 text-green-700 ml-1"
                  :title="`Acknowledged ${formatTime(log.acknowledged_at)}`"
                >✓</span>
              </td>
              <td class="px-4 py-2.5">
                <span class="text-xs text-gray-700 truncate block max-w-[420px]">{{ log.message }}</span>
              </td>
              <td class="px-4 py-2.5 text-right">
                <button
                  v-if="!log.acknowledged_at"
                  @click.stop="acknowledgeOne(log)"
                  class="text-xs px-2 py-0.5 rounded border border-gray-200 hover:bg-white transition-colors text-gray-500"
                >Acknowledge</button>
              </td>
            </tr>

            <!-- Expanded detail -->
            <tr v-if="expandedId === log.id" :key="`${log.id}-detail`">
              <td colspan="5" class="px-6 py-4 bg-gray-50 border-t border-gray-100">
                <div class="grid grid-cols-2 gap-x-8 gap-y-1.5 text-xs max-w-3xl">
                  <div class="col-span-2 flex items-center gap-4 pb-2 mb-1 border-b border-gray-200 flex-wrap">
                    <span class="text-gray-500">{{ formatTime(log.created_at) }}</span>
                    <span class="font-semibold text-gray-800">{{ log.account_name || 'No account context' }}</span>
                    <span :class="['font-medium px-2 py-0.5 rounded-full', typeStyle(log.alert_type)]">{{ typeLabel(log.alert_type) }}</span>
                  </div>

                  <span class="text-gray-400 font-medium">Severity</span>
                  <span class="text-gray-800">{{ log.severity }}</span>

                  <span class="text-gray-400 font-medium">Message</span>
                  <span class="text-gray-800 break-all">{{ log.message }}</span>

                  <span class="text-gray-400 font-medium">Acknowledged</span>
                  <span :class="log.acknowledged_at ? 'text-green-700' : 'text-gray-500'">
                    {{ log.acknowledged_at ? formatTime(log.acknowledged_at) : 'no' }}
                  </span>
                </div>

                <div v-if="log.context" class="mt-4">
                  <span class="text-xs font-semibold text-gray-400 uppercase tracking-wide">Context</span>
                  <pre class="bg-gray-900 text-green-400 text-xs rounded-lg p-3 mt-2 overflow-x-auto max-h-48 leading-relaxed">{{ JSON.stringify(log.context, null, 2) }}</pre>
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
