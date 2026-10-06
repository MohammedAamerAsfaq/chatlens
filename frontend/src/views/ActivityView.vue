<script setup>
import { onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { accountsApi, activityApi } from '@/api'
import UiDataTable from '@/components/ui/UiDataTable.vue'
import ActivityLogDetail from '@/features/activity/components/ActivityLogDetail.vue'

const route = useRoute()
const router = useRouter()
const logs = ref([])
const accounts = ref([])
const loading = ref(false)
const error = ref('')
const clearing = ref(false)
const showClearConfirm = ref(false)
const filterAccount = ref('all')
const filterStatus = ref('all')
const filterEvent = ref('all')
const filterMessageId = ref(route.query.message_id || '')
const searchText = ref('')
const sortKey = ref('created_at')
const sortDirection = ref('desc')
const page = ref(1)
const pageSize = ref(25)
const totalCount = ref(0)
let pollTimer

function formatTime(value) {
  return value ? new Date(value).toLocaleString() : ''
}

function relativeTime(value) {
  const seconds = Math.max(0, Math.floor((Date.now() - new Date(value)) / 1000))
  if (seconds < 60) return `${seconds}s ago`
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`
  return `${Math.floor(seconds / 86400)}d ago`
}

function senderDisplay(log) {
  const sender = log.metadata?.sender_jid
  return sender ? `+${String(sender).split('@')[0]}` : '-'
}

function senderName(log) {
  return log.metadata?.push_name || '-'
}

function eventLabel(value) {
  return { message_ingest: 'Ingest', history_sync: 'History', session_status: 'Session' }[value] || value
}

function metaSummary(log) {
  const metadata = log.metadata || {}
  if (log.event_type === 'message_ingest') {
    const parts = []
    if (metadata.provider_message_id) parts.push(`msg: ${metadata.provider_message_id.slice(0, 12)}...`)
    if (metadata.chat_id) parts.push(`chat: ${String(metadata.chat_id).split('@')[0].slice(-8)}`)
    if (metadata.direction) parts.push(metadata.direction)
    if (metadata.embedded !== undefined) parts.push(metadata.embedded ? 'embedded' : 'not embedded')
    if (metadata.error) parts.push(metadata.error)
    return parts.join(' | ')
  }
  if (log.event_type === 'history_sync') {
    const parts = [`${metadata.created ?? 0} new / ${metadata.skipped ?? 0} skipped`]
    if (metadata.embedded !== undefined) parts.push(`${metadata.embedded} embedded${metadata.embed_errors ? `, ${metadata.embed_errors} errors` : ''}`)
    return parts.join(' | ')
  }
  if (log.event_type === 'session_status') return metadata.status || log.status
  return log.message || ''
}

const columns = [
  { key: 'created_at', label: 'Time', width: '7rem', sortable: true, exportValue: row => formatTime(row.created_at) },
  { key: 'event_type', label: 'Event', width: '8rem', sortable: true, exportValue: row => eventLabel(row.event_type) },
  { key: 'status', label: 'Status', width: '7rem', sortable: true },
  { key: 'sender_id', label: 'Sender ID', width: '10rem', exportValue: senderDisplay },
  { key: 'sender_name', label: 'Sender Name', width: '10rem', exportValue: senderName },
  { key: 'details', label: 'Details', exportValue: metaSummary },
]

function buildParams() {
  const params = { page: page.value, page_size: pageSize.value, ordering: `${sortDirection.value === 'desc' ? '-' : ''}${sortKey.value}` }
  if (filterAccount.value !== 'all') params.account = filterAccount.value
  if (filterStatus.value !== 'all') params.status = filterStatus.value
  if (filterEvent.value !== 'all') params.event_type = filterEvent.value
  if (filterMessageId.value) params.message_id = filterMessageId.value
  if (searchText.value) params.search = searchText.value
  return params
}

async function fetchLogs(showSpinner = false) {
  if (showSpinner) loading.value = true
  error.value = ''
  try {
    const { data } = await activityApi.list(buildParams())
    logs.value = data.results
    totalCount.value = data.count
  } catch { error.value = 'Activity records could not be loaded.' }
  finally { loading.value = false }
}

async function fetchAccounts() {
  try {
    const { data } = await accountsApi.list()
    accounts.value = data.results ?? data
  } catch { accounts.value = [] }
}

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

function openMessageLogs(log) {
  router.push({ name: 'message-logs', query: { account_id: log.account_id, message_id: log.metadata?.provider_message_id } })
}

watch([filterAccount, filterStatus, filterEvent, filterMessageId, pageSize, searchText, sortKey, sortDirection], () => {
  if (page.value !== 1) page.value = 1
  else fetchLogs()
})
watch(page, () => fetchLogs())

onMounted(() => {
  fetchAccounts()
  fetchLogs(true)
  pollTimer = setInterval(() => fetchLogs(), 8000)
})
onUnmounted(() => clearInterval(pollTimer))
</script>

<template>
  <main class="ui-page">
    <div class="ui-page__inner ui-page__inner--wide">
      <header class="ui-page-header">
        <div><p class="ui-eyebrow">System activity</p><h1>Activity Log</h1><p class="ui-page-header__description">Message ingestion and session events</p></div>
        <div class="ui-page-header__actions"><button class="ui-button ui-button--danger" @click="showClearConfirm = true">{{ filterAccount !== 'all' ? 'Clear account logs' : 'Clear all logs' }}</button></div>
      </header>

      <div v-if="filterMessageId" class="activity-query"><span>Message ID: {{ filterMessageId }}</span><button @click="filterMessageId = ''">Clear</button></div>
      <div v-if="error" class="ui-notice ui-notice--danger">{{ error }}</div>

      <UiDataTable
        v-model:page="page" v-model:page-size="pageSize" v-model:search="searchText"
        v-model:sort-key="sortKey" v-model:sort-direction="sortDirection"
        :columns="columns" :rows="logs" :loading="loading" :total="totalCount"
        :row-class="row => row.status === 'error' ? 'is-error' : ''"
        persist-key="activity-log" export-filename="chatlens-activity-page.csv"
        search-placeholder="Search message, sender, account..."
        empty-title="No activity matches these filters" expandable @refresh="fetchLogs(true)"
      >
        <template #filters>
          <select v-model="filterAccount" aria-label="Communication account"><option value="all">All accounts</option><option v-for="account in accounts" :key="account.id" :value="account.id">{{ account.display_name || account.phone_number || `Account #${account.id}` }}</option></select>
          <select v-model="filterStatus" aria-label="Activity status"><option value="all">All statuses</option><option value="success">Success</option><option value="warning">Warning</option><option value="error">Error</option></select>
          <select v-model="filterEvent" aria-label="Event type"><option value="all">All events</option><option value="message_ingest">Message ingest</option><option value="history_sync">History sync</option><option value="session_status">Session status</option></select>
          <span class="activity-total">{{ totalCount.toLocaleString() }} entries</span>
        </template>
        <template #cell-created_at="{ row }"><span class="activity-time" :title="formatTime(row.created_at)">{{ relativeTime(row.created_at) }}</span></template>
        <template #cell-event_type="{ row }"><span :class="['activity-badge', `event-${row.event_type}`]">{{ eventLabel(row.event_type) }}</span></template>
        <template #cell-status="{ row }"><span :class="['activity-badge', `status-${row.status}`]">{{ row.status }}</span></template>
        <template #cell-sender_id="{ row }"><code>{{ senderDisplay(row) }}</code></template>
        <template #cell-sender_name="{ row }"><span class="activity-sender">{{ senderName(row) }}</span></template>
        <template #cell-details="{ row }"><span class="activity-summary">{{ metaSummary(row) }}</span></template>
        <template #expanded="{ row }"><ActivityLogDetail :log="row" @open-message="openMessageLogs" /></template>
      </UiDataTable>
    </div>
  </main>

  <Teleport to="#ui-teleport-host">
    <div v-if="showClearConfirm" class="ui-modal-backdrop" @click.self="showClearConfirm = false">
      <section class="ui-modal activity-confirm">
        <header><h2>Clear Activity Logs</h2><button aria-label="Close" @click="showClearConfirm = false">&times;</button></header>
        <div class="ui-modal__body"><p class="ui-confirm-copy">This permanently deletes all activity logs{{ filterAccount !== 'all' ? ' for the selected account' : ' across every visible account' }}. This cannot be undone.</p></div>
        <footer><button class="ui-button" @click="showClearConfirm = false">Cancel</button><button class="ui-button ui-button--danger" :disabled="clearing" @click="clearLogs">{{ clearing ? 'Clearing...' : 'Clear logs' }}</button></footer>
      </section>
    </div>
  </Teleport>
</template>

<style scoped>
.activity-query { display:flex; align-items:center; justify-content:space-between; gap:12px; margin-bottom:12px; padding:9px 12px; border:1px solid var(--ui-info); border-radius:var(--ui-radius-sm); background:var(--ui-info-soft); color:var(--ui-info); font-size:.78rem; }
.activity-query button { border:0; background:transparent; color:inherit; font-weight:800; cursor:pointer; }
.activity-total,.activity-time { color:var(--ui-text-subtle); font-size:.72rem; }
.activity-badge { display:inline-flex; padding:3px 8px; border-radius:var(--ui-radius-pill); background:var(--ui-surface-muted); color:var(--ui-text-muted); font-size:.67rem; font-weight:800; text-transform:capitalize; }
.status-success { background:var(--ui-success-soft); color:var(--ui-success); }
.status-warning,.event-history_sync { background:var(--ui-warning-soft); color:var(--ui-warning); }
.status-error { background:var(--ui-danger-soft); color:var(--ui-danger); }
.event-message_ingest { background:var(--ui-info-soft); color:var(--ui-info); }
.event-session_status { background:var(--ui-primary-soft); color:var(--ui-primary); }
code,.activity-summary { color:var(--ui-text-muted); font-size:.72rem; }
.activity-summary,.activity-sender { display:block; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.activity-confirm { max-width:430px; }
.ui-modal__body { padding:18px; }
</style>
