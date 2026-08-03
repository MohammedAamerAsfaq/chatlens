<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { accountsApi, tradingApi } from '@/api'

const logs = ref([])
const accounts = ref([])
const loading = ref(false)
const expandedId = ref(null)
const filterAccount = ref('all')
const filterStatus = ref('all')
const page = ref(1)
const pageSize = ref(25)
const totalCount = ref(0)
const pageSizeOptions = [10, 25, 50, 100]

const totalPages = computed(() => Math.max(1, Math.ceil(totalCount.value / pageSize.value)))
const pageStart = computed(() => totalCount.value === 0 ? 0 : (page.value - 1) * pageSize.value + 1)
const pageEnd = computed(() => Math.min(page.value * pageSize.value, totalCount.value))

const STATUS_LABELS = {
  pass1_started: 'Pass 1 Started',
  pass1_done: 'Pass 1 Done',
  pass2_started: 'Pass 2 Started',
  complete: 'Complete',
  error: 'Error',
}

function statusLabel(status) {
  return STATUS_LABELS[status] || status
}

function statusClass(status) {
  if (status === 'complete') return 'status-complete'
  if (status === 'error') return 'status-error'
  if (status === 'pass2_started') return 'status-pass2'
  return 'status-pending'
}

function buildParams() {
  const params = { page: page.value, page_size: pageSize.value }
  if (filterAccount.value !== 'all') params.account = filterAccount.value
  if (filterStatus.value !== 'all') params.status = filterStatus.value
  return params
}

async function fetchLogs(showSpinner = false) {
  if (showSpinner) loading.value = true
  try {
    const { data } = await tradingApi.listAiParseV2Logs(buildParams())
    logs.value = data.results
    totalCount.value = data.count
  } finally {
    loading.value = false
  }
}

async function fetchAccounts() {
  const { data } = await accountsApi.list()
  accounts.value = data.results ?? data
}

watch([filterAccount, filterStatus, pageSize], () => {
  page.value = 1
  fetchLogs()
})
watch(page, () => fetchLogs())

onMounted(() => {
  fetchAccounts()
  fetchLogs(true)
})

function toggleRow(id) {
  expandedId.value = expandedId.value === id ? null : id
}

function formatTime(value) {
  if (!value) return ''
  return new Date(value).toLocaleString()
}

function relativeTime(value) {
  const diff = Math.floor((Date.now() - new Date(value)) / 1000)
  if (diff < 60) return `${diff}s ago`
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  return `${Math.floor(diff / 86400)}d ago`
}

function jsonText(value) {
  if (value == null || value === '') return ''
  if (typeof value === 'string') return value
  return JSON.stringify(value, null, 2)
}
</script>

<template>
  <div class="v2-log-view">
    <div class="page-head">
      <div>
        <h1>AI Parse V2 Logs</h1>
        <p>Pass 1 and batched pass 2 request/response audit trail.</p>
      </div>
      <button class="refresh-btn" @click="fetchLogs(true)">Refresh</button>
    </div>

    <div class="filters">
      <select v-model="filterAccount">
        <option value="all">All accounts</option>
        <option v-for="account in accounts" :key="account.id" :value="account.id">
          {{ account.display_name || account.phone_number || `Account #${account.id}` }}
        </option>
      </select>
      <select v-model="filterStatus">
        <option value="all">All statuses</option>
        <option value="pass1_started">Pass 1 Started</option>
        <option value="pass1_done">Pass 1 Done</option>
        <option value="pass2_started">Pass 2 Started</option>
        <option value="complete">Complete</option>
        <option value="error">Error</option>
      </select>
      <span class="count">{{ totalCount.toLocaleString() }} entries</span>
      <div class="page-size">
        <span>Rows:</span>
        <button
          v-for="size in pageSizeOptions"
          :key="size"
          :class="{ active: pageSize === size }"
          @click="pageSize = size"
        >{{ size }}</button>
      </div>
    </div>

    <div class="table-card">
      <div v-if="loading" class="empty">Loading...</div>
      <div v-else-if="!logs.length" class="empty">No V2 parse logs found.</div>
      <table v-else>
        <thead>
          <tr>
            <th>Time</th>
            <th>Account</th>
            <th>Status</th>
            <th>Message</th>
            <th>Inquiry IDs</th>
          </tr>
        </thead>
        <tbody>
          <template v-for="log in logs" :key="log.id">
            <tr class="row" :class="{ expanded: expandedId === log.id }" @click="toggleRow(log.id)">
              <td :title="formatTime(log.created_at)">{{ relativeTime(log.created_at) }}</td>
              <td>{{ log.account_name }}</td>
              <td><span class="status" :class="statusClass(log.status)">{{ statusLabel(log.status) }}</span></td>
              <td class="message-cell">{{ log.message_text || '(no text)' }}</td>
              <td>{{ (log.inquiry_ids || []).join(', ') || '-' }}</td>
            </tr>
            <tr v-if="expandedId === log.id">
              <td colspan="5" class="detail-cell">
                <div class="detail-grid">
                  <section>
                    <h2>Pass 1 Request</h2>
                    <pre>{{ jsonText(log.pass1_request) || 'Not recorded' }}</pre>
                  </section>
                  <section>
                    <h2>Pass 1 Response</h2>
                    <pre>{{ jsonText(log.pass1_response) || 'Not recorded' }}</pre>
                  </section>
                  <section>
                    <h2>Pass 1 Parsed</h2>
                    <pre>{{ jsonText(log.pass1_parsed) || 'Not recorded' }}</pre>
                  </section>
                  <section>
                    <h2>Pass 2 Request</h2>
                    <pre>{{ jsonText(log.pass2_request) || 'Not recorded' }}</pre>
                  </section>
                  <section>
                    <h2>Pass 2 Response</h2>
                    <pre>{{ jsonText(log.pass2_response) || 'Not recorded' }}</pre>
                  </section>
                  <section>
                    <h2>Pass 2 Parsed</h2>
                    <pre>{{ jsonText(log.pass2_parsed) || 'Not recorded' }}</pre>
                  </section>
                  <section v-if="log.error" class="error-section">
                    <h2>Error</h2>
                    <pre>{{ log.error }}</pre>
                  </section>
                </div>
              </td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>

    <div v-if="totalCount > 0" class="pagination">
      <span>Showing {{ pageStart.toLocaleString() }}-{{ pageEnd.toLocaleString() }} of {{ totalCount.toLocaleString() }}</span>
      <div>
        <button :disabled="page === 1" @click="page--">Prev</button>
        <span>Page {{ page }} of {{ totalPages }}</span>
        <button :disabled="page >= totalPages" @click="page++">Next</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.v2-log-view { height: 100%; overflow-y: auto; padding: 24px; background: #f8fafc; color: #111827; }
.page-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; margin-bottom: 20px; }
.page-head h1 { margin: 0; font-size: 1.55rem; }
.page-head p { margin: 6px 0 0; color: #64748b; }
.refresh-btn, .pagination button, .page-size button {
  border: 1px solid #dbe3ef;
  background: #fff;
  border-radius: 8px;
  padding: 7px 11px;
  cursor: pointer;
}
.filters { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; margin-bottom: 14px; }
.filters select { border: 1px solid #dbe3ef; border-radius: 8px; padding: 8px 10px; background: #fff; }
.count { color: #64748b; font-size: 0.88rem; flex: 1; }
.page-size { display: flex; align-items: center; gap: 6px; color: #64748b; font-size: 0.84rem; }
.page-size button { padding: 5px 9px; font-size: 0.78rem; }
.page-size button.active { background: #16a34a; color: #fff; border-color: #16a34a; }
.table-card { background: #fff; border: 1px solid #e2e8f0; border-radius: 14px; overflow: hidden; box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04); }
.empty { padding: 42px; text-align: center; color: #94a3b8; }
table { width: 100%; border-collapse: collapse; font-size: 0.88rem; }
th { text-align: left; background: #f8fafc; color: #64748b; font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.06em; padding: 12px 14px; border-bottom: 1px solid #e2e8f0; }
td { padding: 11px 14px; border-bottom: 1px solid #f1f5f9; vertical-align: top; }
.row { cursor: pointer; }
.row:hover, .row.expanded { background: #f8fafc; }
.message-cell { max-width: 520px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #475569; }
.status { display: inline-flex; border-radius: 999px; padding: 3px 8px; font-size: 0.74rem; font-weight: 700; }
.status-complete { background: #dcfce7; color: #166534; }
.status-error { background: #fee2e2; color: #b91c1c; }
.status-pass2 { background: #dbeafe; color: #1d4ed8; }
.status-pending { background: #fef3c7; color: #92400e; }
.detail-cell { background: #f8fafc; }
.detail-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.detail-grid section { border: 1px solid #e2e8f0; border-radius: 10px; background: #fff; overflow: hidden; }
.detail-grid h2 { margin: 0; padding: 9px 12px; border-bottom: 1px solid #e2e8f0; font-size: 0.78rem; color: #334155; background: #f8fafc; }
pre { margin: 0; padding: 12px; max-height: 340px; overflow: auto; font-size: 0.76rem; line-height: 1.45; color: #d1fae5; background: #0f172a; white-space: pre-wrap; word-break: break-word; }
.error-section { grid-column: 1 / -1; }
.pagination { display: flex; justify-content: space-between; align-items: center; gap: 12px; padding: 14px 4px; color: #64748b; font-size: 0.86rem; }
.pagination div { display: flex; align-items: center; gap: 10px; }
.pagination button:disabled { opacity: 0.45; cursor: not-allowed; }
@media (max-width: 980px) {
  .detail-grid { grid-template-columns: 1fr; }
}
</style>
