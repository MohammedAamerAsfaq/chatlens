<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { unresolvedMessagesApi, accountsApi, contactsApi } from '@/api'

const rows       = ref([])
const accounts    = ref([])
const loading     = ref(false)
const expandedId  = ref(null)
const counts      = ref({ pending: 0, resolved: 0, failed: 0 })
const actionBusy  = ref({})
const actionError = ref({})
const contactQuery = ref({})
const contactOptions = ref({})
const newContactName = ref({})
const newContactPhone = ref({})
const rawPayloadOpen = ref({})

const filterAccount = ref('all')
const filterStatus  = ref('pending')

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
  if (filterAccount.value !== 'all') p.account = filterAccount.value
  if (filterStatus.value !== 'all')  p.resolution_status = filterStatus.value
  return p
}

async function fetchRows(showSpinner = false) {
  if (showSpinner) loading.value = true
  try {
    const { data } = await unresolvedMessagesApi.list(buildParams())
    rows.value       = data.results
    totalCount.value = data.count
  } catch {}
  finally { loading.value = false }
}

async function fetchCounts() {
  try {
    const params = filterAccount.value !== 'all' ? { account: filterAccount.value } : {}
    const { data } = await unresolvedMessagesApi.counts(params)
    counts.value = data
  } catch {}
}

async function fetchAccounts() {
  try {
    const { data } = await accountsApi.list()
    accounts.value = data.results ?? data
  } catch {}
}

function refreshAll() {
  fetchRows()
  fetchCounts()
}

function setActionError(id, message) {
  actionError.value = { ...actionError.value, [id]: message || '' }
}

function setActionBusy(id, busy) {
  actionBusy.value = { ...actionBusy.value, [id]: busy }
}

function applyUpdatedRow(updated) {
  const next = updated?.row || updated
  if (!next?.id) return
  const idx = rows.value.findIndex(r => r.id === next.id)
  if (idx !== -1) rows.value[idx] = next
}

async function retryResolution(row) {
  setActionBusy(row.id, true)
  setActionError(row.id, '')
  try {
    const { data } = await unresolvedMessagesApi.retryResolution(row.id)
    applyUpdatedRow(data)
    await fetchCounts()
  } catch (e) {
    setActionError(row.id, e.response?.data?.detail || 'Retry failed')
  } finally {
    setActionBusy(row.id, false)
  }
}

async function dismissRow(row) {
  const reason = window.prompt('Reason for dismissing this unresolved message?', 'Dismissed manually by user.')
  if (reason === null) return
  setActionBusy(row.id, true)
  setActionError(row.id, '')
  try {
    const { data } = await unresolvedMessagesApi.dismiss(row.id, reason)
    applyUpdatedRow(data)
    await fetchCounts()
  } catch (e) {
    setActionError(row.id, e.response?.data?.detail || 'Dismiss failed')
  } finally {
    setActionBusy(row.id, false)
  }
}

async function searchContacts(row) {
  const q = (contactQuery.value[row.id] || '').trim()
  contactOptions.value = { ...contactOptions.value, [row.id]: [] }
  if (q.length < 2) return
  setActionError(row.id, '')
  try {
    const { data } = await contactsApi.list({
      account: row.account,
      type: 'phone',
      search: q,
      page_size: 8,
    })
    contactOptions.value = { ...contactOptions.value, [row.id]: data.results ?? data }
  } catch (e) {
    setActionError(row.id, e.response?.data?.detail || 'Contact search failed')
  }
}

async function resolveWithContact(row, contact) {
  setActionBusy(row.id, true)
  setActionError(row.id, '')
  try {
    const { data } = await unresolvedMessagesApi.resolveWithContact(row.id, contact.id)
    applyUpdatedRow(data)
    contactOptions.value = { ...contactOptions.value, [row.id]: [] }
    contactQuery.value = { ...contactQuery.value, [row.id]: contact.display_name || contact.push_name || contact.phone_number || contact.wa_contact_id }
    await fetchCounts()
  } catch (e) {
    setActionError(row.id, e.response?.data?.detail || 'Manual resolution failed')
  } finally {
    setActionBusy(row.id, false)
  }
}

async function createContactAndResolve(row) {
  const phoneNumber = (newContactPhone.value[row.id] || '').trim()
  const displayName = (newContactName.value[row.id] || '').trim()
  if (!phoneNumber) {
    setActionError(row.id, 'Phone number is required to create a contact.')
    return
  }

  setActionBusy(row.id, true)
  setActionError(row.id, '')
  try {
    const { data } = await unresolvedMessagesApi.createContactAndResolve(row.id, {
      phone_number: phoneNumber,
      display_name: displayName,
    })
    applyUpdatedRow(data)
    newContactName.value = { ...newContactName.value, [row.id]: '' }
    newContactPhone.value = { ...newContactPhone.value, [row.id]: '' }
    await fetchCounts()
  } catch (e) {
    setActionError(row.id, e.response?.data?.detail || 'Create contact and resolve failed')
  } finally {
    setActionBusy(row.id, false)
  }
}

watch([filterAccount, filterStatus, pageSize], () => { page.value = 1; refreshAll() })
watch(page, () => fetchRows())

onMounted(() => {
  fetchAccounts()
  fetchRows(true)
  fetchCounts()
  pollTimer = setInterval(refreshAll, 8000)
})
onUnmounted(() => clearInterval(pollTimer))

function formatTime(dt) {
  if (!dt) return ''
  return new Date(dt).toLocaleString()
}

function relativeTime(dt) {
  if (!dt) return '—'
  const diff = Math.floor((Date.now() - new Date(dt)) / 1000)
  if (diff < 60)    return `${diff}s ago`
  if (diff < 3600)  return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  return `${Math.floor(diff / 86400)}d ago`
}

function toggleRow(id) {
  expandedId.value = expandedId.value === id ? null : id
}

function statusBadgeClass(status) {
  if (status === 'resolved') return 'bg-green-100 text-green-700'
  if (status === 'failed')   return 'bg-red-100 text-red-800'
  return 'bg-amber-100 text-amber-700'
}

function toggleRawPayload(id) {
  rawPayloadOpen.value = { ...rawPayloadOpen.value, [id]: !rawPayloadOpen.value[id] }
}

function formatJson(value) {
  if (!value) return ''
  return JSON.stringify(value, null, 2)
}
</script>

<template>
  <div class="h-full w-full overflow-y-auto bg-gray-50">
  <div class="max-w-7xl mx-auto px-6 py-6">

    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-2xl font-bold text-gray-900">Unresolved Messages</h1>
        <p class="text-sm text-gray-500 mt-1">
          Messages with real content whose chat-level LID couldn't be resolved to a phone
          number at ingestion time. Preserved here instead of discarded — resolution happens
          automatically once ChatLens learns the LID's phone mapping (from a contact update),
          and each row then becomes a normal message with no content lost.
        </p>
      </div>
    </div>

    <!-- Counts summary -->
    <div class="grid grid-cols-3 gap-3 mb-4 max-w-xl">
      <div class="bg-white rounded-xl border border-gray-200 px-4 py-3">
        <div class="text-xs text-gray-400 uppercase tracking-wide">Pending</div>
        <div class="text-xl font-bold text-amber-600">{{ counts.pending.toLocaleString() }}</div>
      </div>
      <div class="bg-white rounded-xl border border-gray-200 px-4 py-3">
        <div class="text-xs text-gray-400 uppercase tracking-wide">Resolved</div>
        <div class="text-xl font-bold text-green-600">{{ counts.resolved.toLocaleString() }}</div>
      </div>
      <div class="bg-white rounded-xl border border-gray-200 px-4 py-3">
        <div class="text-xs text-gray-400 uppercase tracking-wide">Failed</div>
        <div class="text-xl font-bold text-red-600">{{ counts.failed.toLocaleString() }}</div>
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
        <option value="pending">Pending</option>
        <option value="resolved">Resolved</option>
        <option value="failed">Failed</option>
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
        No unresolved messages recorded
      </div>

      <table v-else class="w-full text-sm">
        <thead>
          <tr class="bg-gray-50 border-b border-gray-100 text-xs text-gray-500 uppercase tracking-wide">
            <th class="text-left px-4 py-3 w-28">Created</th>
            <th class="text-left px-4 py-3 w-36">Account</th>
            <th class="text-left px-4 py-3 w-44">LID / Raw JID</th>
            <th class="text-left px-4 py-3 w-20">Dir</th>
            <th class="text-left px-4 py-3">Preview</th>
            <th class="text-left px-4 py-3 w-24">Status</th>
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
                <span class="text-gray-500 text-xs" :title="formatTime(row.created_at)">
                  {{ relativeTime(row.created_at) }}
                </span>
              </td>
              <td class="px-4 py-2.5">
                <span class="text-xs text-gray-700 truncate block max-w-[130px]">{{ row.account_name || '—' }}</span>
              </td>
              <td class="px-4 py-2.5">
                <span class="text-xs text-gray-700 truncate block max-w-[220px]">{{ row.lid_jid || row.raw_jid }}</span>
              </td>
              <td class="px-4 py-2.5">
                <span class="text-xs text-gray-500">{{ row.direction || (row.from_me ? 'outbound' : 'inbound') }}</span>
              </td>
              <td class="px-4 py-2.5">
                <span class="text-xs text-gray-700 truncate block max-w-[420px]">
                  {{ row.message_preview || (row.has_media ? `[${row.message_type}]` : '—') }}
                </span>
              </td>
              <td class="px-4 py-2.5">
                <span class="text-xs font-semibold px-2 py-0.5 rounded-full" :class="statusBadgeClass(row.resolution_status)">
                  {{ row.resolution_status }}
                </span>
                <span v-if="row.is_history" class="text-xs text-gray-400 ml-1" title="From history sync">H</span>
              </td>
            </tr>

            <!-- Expanded detail -->
            <tr v-if="expandedId === row.id" :key="`${row.id}-detail`">
              <td colspan="6" class="px-6 py-4 bg-gray-50 border-t border-gray-100">
                <div class="grid grid-cols-2 gap-x-8 gap-y-1.5 text-xs max-w-3xl">
                  <div class="col-span-2 flex items-center gap-4 pb-2 mb-1 border-b border-gray-200 flex-wrap">
                    <span class="font-semibold text-gray-800">{{ row.account_name || 'No account context' }}</span>
                    <span class="text-gray-500">Created {{ formatTime(row.created_at) }}</span>
                  </div>

                  <span class="text-gray-400 font-medium">Raw JID</span>
                  <span class="text-gray-800 break-all">{{ row.raw_jid || '—' }}</span>

                  <span class="text-gray-400 font-medium">LID</span>
                  <span class="text-gray-800 break-all">{{ row.lid_jid || '—' }}</span>

                  <span class="text-gray-400 font-medium">Participant</span>
                  <span class="text-gray-800 break-all">{{ row.participant_jid || '—' }}</span>

                  <span class="text-gray-400 font-medium">Push Name</span>
                  <span class="text-gray-800">{{ row.push_name || '—' }}</span>

                  <span class="text-gray-400 font-medium">Message Type</span>
                  <span class="text-gray-800">{{ row.message_type }}<span v-if="row.has_media"> (media)</span></span>

                  <span class="text-gray-400 font-medium">Message Time</span>
                  <span class="text-gray-800">{{ formatTime(row.message_time) || '—' }}</span>

                  <span class="text-gray-400 font-medium">Reason</span>
                  <span class="text-gray-800">{{ row.reason }}</span>

                  <span class="text-gray-400 font-medium">Source</span>
                  <span class="text-gray-800">{{ row.is_history ? 'History sync' : 'Live' }}</span>

                  <span class="text-gray-400 font-medium">Resolution</span>
                  <span :class="row.resolution_status === 'resolved' ? 'text-green-700' : row.resolution_status === 'failed' ? 'text-red-700' : 'text-amber-700'">
                    {{ row.resolution_status }}{{ row.resolved_at ? ` — ${formatTime(row.resolved_at)}` : '' }}
                  </span>

                  <template v-if="row.resolved_message">
                    <span class="text-gray-400 font-medium">Resolved Message</span>
                    <span class="text-gray-800">#{{ row.resolved_message }}</span>
                  </template>
                </div>

                <div v-if="row.message_preview" class="mt-4">
                  <span class="text-xs font-semibold text-gray-400 uppercase tracking-wide">Message Text</span>
                  <pre class="bg-gray-900 text-green-400 text-xs rounded-lg p-3 mt-2 overflow-x-auto max-h-48 leading-relaxed whitespace-pre-wrap">{{ row.message_preview }}</pre>
                </div>

                <div class="mt-4 rounded-xl border border-gray-200 bg-white p-4">
                  <div class="flex items-center justify-between gap-3">
                    <div>
                      <div class="text-xs font-semibold text-gray-500 uppercase tracking-wide">Raw Payload</div>
                      <p class="text-xs text-gray-500 mt-1">
                        Inspect preserved WhatsApp key/payload fields for identity clues before resolving manually.
                      </p>
                    </div>
                    <button
                      @click.stop="toggleRawPayload(row.id)"
                      class="px-3 py-1.5 rounded-lg border border-gray-200 text-xs font-semibold text-gray-700 hover:bg-gray-50"
                    >
                      {{ rawPayloadOpen[row.id] ? 'Hide Raw' : 'Inspect Raw' }}
                    </button>
                  </div>
                  <div v-if="rawPayloadOpen[row.id]" class="mt-3 grid grid-cols-1 lg:grid-cols-2 gap-3">
                    <div>
                      <span class="text-xs font-semibold text-gray-400 uppercase tracking-wide">Raw Key</span>
                      <pre class="bg-gray-900 text-cyan-300 text-xs rounded-lg p-3 mt-2 overflow-x-auto max-h-80 leading-relaxed">{{ formatJson(row.raw_key) || 'null' }}</pre>
                    </div>
                    <div>
                      <span class="text-xs font-semibold text-gray-400 uppercase tracking-wide">Raw Payload</span>
                      <pre class="bg-gray-900 text-cyan-300 text-xs rounded-lg p-3 mt-2 overflow-x-auto max-h-80 leading-relaxed">{{ formatJson(row.raw_payload) || 'null' }}</pre>
                    </div>
                  </div>
                </div>

                <div v-if="row.resolution_status === 'pending'" class="mt-4 rounded-xl border border-gray-200 bg-white p-4">
                  <div class="flex items-start justify-between gap-4 flex-wrap">
                    <div>
                      <div class="text-xs font-semibold text-gray-500 uppercase tracking-wide">Actions</div>
                      <p class="text-xs text-gray-500 mt-1">
                        Retry uses any known LID mapping. Manual resolve links this LID to an existing phone contact, then reprocesses the preserved message.
                      </p>
                    </div>
                    <div class="flex items-center gap-2">
                      <button
                        @click.stop="retryResolution(row)"
                        :disabled="actionBusy[row.id]"
                        class="px-3 py-1.5 rounded-lg border border-gray-200 text-xs font-semibold text-gray-700 hover:bg-gray-50 disabled:opacity-50"
                      >
                        Retry Resolution
                      </button>
                      <button
                        @click.stop="dismissRow(row)"
                        :disabled="actionBusy[row.id]"
                        class="px-3 py-1.5 rounded-lg border border-red-200 text-xs font-semibold text-red-700 hover:bg-red-50 disabled:opacity-50"
                      >
                        Dismiss
                      </button>
                    </div>
                  </div>

                  <div class="mt-3 relative max-w-xl">
                    <label class="text-xs font-medium text-gray-500">Resolve manually with contact</label>
                    <input
                      v-model="contactQuery[row.id]"
                      @input.stop="searchContacts(row)"
                      @click.stop
                      class="mt-1 w-full border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-green-500"
                      placeholder="Search contact name or phone..."
                    />
                    <div
                      v-if="(contactOptions[row.id] || []).length"
                      class="absolute z-10 left-0 right-0 mt-1 bg-white border border-gray-200 rounded-lg shadow-lg max-h-56 overflow-y-auto"
                    >
                      <button
                        v-for="contact in contactOptions[row.id]"
                        :key="contact.id"
                        @click.stop="resolveWithContact(row, contact)"
                        :disabled="actionBusy[row.id]"
                        class="w-full text-left px-3 py-2 hover:bg-gray-50 disabled:opacity-50"
                      >
                        <span class="block text-xs font-semibold text-gray-800">
                          {{ contact.display_name || contact.push_name || contact.phone_number || contact.wa_contact_id }}
                        </span>
                        <span class="block text-[11px] text-gray-400">{{ contact.phone_number || contact.wa_contact_id }}</span>
                      </button>
                    </div>
                  </div>

                  <div class="mt-4 border-t border-gray-100 pt-4 max-w-2xl">
                    <div class="text-xs font-medium text-gray-500">Create new contact and resolve</div>
                    <div class="grid grid-cols-1 md:grid-cols-[1fr_1fr_auto] gap-2 mt-2">
                      <input
                        v-model="newContactName[row.id]"
                        @click.stop
                        class="border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-green-500"
                        placeholder="Display name"
                      />
                      <input
                        v-model="newContactPhone[row.id]"
                        @click.stop
                        class="border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-green-500"
                        placeholder="Phone number, e.g. 9715..."
                      />
                      <button
                        @click.stop="createContactAndResolve(row)"
                        :disabled="actionBusy[row.id]"
                        class="px-3 py-2 rounded-lg bg-green-600 text-white text-xs font-semibold hover:bg-green-700 disabled:opacity-50"
                      >
                        Create + Resolve
                      </button>
                    </div>
                    <p class="text-[11px] text-gray-400 mt-2">
                      This creates a phone contact in {{ row.account_name || 'this account' }}, maps {{ row.lid_jid || row.raw_jid }} to it, then reprocesses the preserved message.
                    </p>
                  </div>

                  <div v-if="actionError[row.id]" class="mt-3 text-xs text-red-700 bg-red-50 border border-red-100 rounded-lg px-3 py-2">
                    {{ actionError[row.id] }}
                  </div>
                </div>

                <div v-if="row.resolution_error" class="mt-4">
                  <span class="text-xs font-semibold text-red-400 uppercase tracking-wide">Resolution Error</span>
                  <pre class="bg-gray-900 text-red-400 text-xs rounded-lg p-3 mt-2 overflow-x-auto max-h-48 leading-relaxed whitespace-pre-wrap">{{ row.resolution_error }}</pre>
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
