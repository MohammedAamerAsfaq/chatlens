<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { stuckReceiptsApi, accountsApi } from '@/api'

const rows       = ref([])
const accounts    = ref([])
const loading     = ref(false)
const resolving   = ref(false)
const expandedId  = ref(null)

const filterAccount  = ref('all')
const filterResolved = ref('false')

const page            = ref(1)
const pageSize        = ref(25)
const totalCount      = ref(0)
const pageSizeOptions = [10, 25, 50, 100]

const totalPages = computed(() => Math.max(1, Math.ceil(totalCount.value / pageSize.value)))
const pageStart  = computed(() => totalCount.value === 0 ? 0 : (page.value - 1) * pageSize.value + 1)
const pageEnd    = computed(() => Math.min(page.value * pageSize.value, totalCount.value))

let pollTimer = null

function buildParams() {
  const p = { page: page.value, page_size: pageSize.value }
  if (filterAccount.value !== 'all')  p.account  = filterAccount.value
  if (filterResolved.value !== 'all') p.resolved = filterResolved.value
  return p
}

async function fetchRows(showSpinner = false) {
  if (showSpinner) loading.value = true
  try {
    const { data } = await stuckReceiptsApi.list(buildParams())
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

watch([filterAccount, filterResolved, pageSize], () => { page.value = 1; fetchRows() })
watch(page, () => fetchRows())

onMounted(() => {
  fetchAccounts()
  fetchRows(true)
  pollTimer = setInterval(() => fetchRows(), 8000)
})
onUnmounted(() => clearInterval(pollTimer))

async function resolveOne(row) {
  resolving.value = true
  try {
    await stuckReceiptsApi.resolve(row.id)
    await fetchRows()
  } finally {
    resolving.value = false
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
        <h1 class="text-2xl font-bold text-gray-900">Stuck Receipts</h1>
        <p class="text-sm text-gray-500 mt-1">
          Messages WhatsApp keeps asking us to resend that our own send path can't fulfill (Baileys
          crashes internally on them every time). Recorded here instead of letting every repeat hit
          WhatsApp's servers again — occurrence count and last-seen show whether it's still recurring.
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
        v-model="filterResolved"
        class="border border-gray-200 rounded-lg px-3 py-1.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-green-500"
      >
        <option value="false">Unresolved</option>
        <option value="true">Resolved</option>
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

      <div v-else-if="rows.length === 0" class="text-center text-gray-400 py-12 text-sm">
        No stuck receipts recorded
      </div>

      <table v-else class="w-full text-sm">
        <thead>
          <tr class="bg-gray-50 border-b border-gray-100 text-xs text-gray-500 uppercase tracking-wide">
            <th class="text-left px-4 py-3 w-28">Last Seen</th>
            <th class="text-left px-4 py-3 w-36">Account</th>
            <th class="text-left px-4 py-3">Remote JID / Participant</th>
            <th class="text-left px-4 py-3 w-24">Seen</th>
            <th class="text-left px-4 py-3 w-28"></th>
          </tr>
        </thead>
        <tbody class="divide-y divide-gray-50">
          <template v-for="row in rows" :key="row.id">
            <tr
              @click="toggleRow(row.id)"
              :class="[
                'cursor-pointer transition-colors',
                expandedId === row.id ? 'bg-gray-100' : 'hover:bg-gray-50',
              ]"
            >
              <td class="px-4 py-2.5">
                <span class="text-gray-500 text-xs" :title="formatTime(row.last_seen_at)">
                  {{ relativeTime(row.last_seen_at) }}
                </span>
              </td>
              <td class="px-4 py-2.5">
                <span class="text-xs text-gray-700 truncate block max-w-[130px]">{{ row.account_name || '—' }}</span>
              </td>
              <td class="px-4 py-2.5">
                <span class="text-xs text-gray-700 truncate block max-w-[420px]">
                  {{ row.remote_jid }}<span v-if="row.participant && row.participant !== row.remote_jid"> · {{ row.participant }}</span>
                </span>
              </td>
              <td class="px-4 py-2.5">
                <span
                  class="text-xs font-semibold px-2 py-0.5 rounded-full"
                  :class="row.occurrence_count >= 10 ? 'bg-red-100 text-red-800' : row.occurrence_count >= 3 ? 'bg-orange-100 text-orange-700' : 'bg-gray-100 text-gray-600'"
                >{{ row.occurrence_count }}×</span>
                <span
                  v-if="row.resolved_at"
                  class="text-xs font-medium px-2 py-0.5 rounded-full bg-green-100 text-green-700 ml-1"
                  :title="`Resolved ${formatTime(row.resolved_at)}`"
                >✓</span>
              </td>
              <td class="px-4 py-2.5 text-right">
                <button
                  v-if="!row.resolved_at"
                  @click.stop="resolveOne(row)"
                  :disabled="resolving"
                  class="text-xs px-2 py-0.5 rounded border border-gray-200 hover:bg-white transition-colors text-gray-500 disabled:opacity-40"
                >Resolve</button>
              </td>
            </tr>

            <!-- Expanded detail -->
            <tr v-if="expandedId === row.id" :key="`${row.id}-detail`">
              <td colspan="5" class="px-6 py-4 bg-gray-50 border-t border-gray-100">
                <div class="grid grid-cols-2 gap-x-8 gap-y-1.5 text-xs max-w-3xl">
                  <div class="col-span-2 flex items-center gap-4 pb-2 mb-1 border-b border-gray-200 flex-wrap">
                    <span class="text-gray-500">First seen {{ formatTime(row.first_seen_at) }}</span>
                    <span class="font-semibold text-gray-800">{{ row.account_name || 'No account context' }}</span>
                  </div>

                  <span class="text-gray-400 font-medium">Message ID</span>
                  <span class="text-gray-800 break-all">{{ row.message_id }}</span>

                  <span class="text-gray-400 font-medium">Remote JID</span>
                  <span class="text-gray-800 break-all">{{ row.remote_jid }}</span>

                  <span class="text-gray-400 font-medium">Participant</span>
                  <span class="text-gray-800 break-all">{{ row.participant || '—' }}</span>

                  <span class="text-gray-400 font-medium">From Me</span>
                  <span class="text-gray-800">{{ row.from_me ? 'yes' : 'no' }}</span>

                  <span class="text-gray-400 font-medium">Occurrences</span>
                  <span class="text-gray-800">{{ row.occurrence_count }} (first {{ formatTime(row.first_seen_at) }}, last {{ formatTime(row.last_seen_at) }})</span>

                  <span class="text-gray-400 font-medium">Resolved</span>
                  <span :class="row.resolved_at ? 'text-green-700' : 'text-gray-500'">
                    {{ row.resolved_at ? formatTime(row.resolved_at) : 'no' }}
                  </span>
                </div>

                <div v-if="row.context" class="mt-4">
                  <span class="text-xs font-semibold text-gray-400 uppercase tracking-wide">Context</span>
                  <pre class="bg-gray-900 text-green-400 text-xs rounded-lg p-3 mt-2 overflow-x-auto max-h-48 leading-relaxed">{{ JSON.stringify(row.context, null, 2) }}</pre>
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
