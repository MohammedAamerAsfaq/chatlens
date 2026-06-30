<template>
  <div class="inquiries-view">
    <!-- Filter bar -->
    <div class="filter-bar">
      <div class="filter-group">
        <label>Account</label>
        <select v-model="filters.account" @change="load">
          <option value="">All accounts</option>
          <option v-for="a in accounts" :key="a.id" :value="a.id">{{ a.display_name }}</option>
        </select>
      </div>
      <div class="filter-group">
        <label>Type</label>
        <select v-model="filters.type" @change="load">
          <option value="">All</option>
          <option value="buy">WTB</option>
          <option value="sell">WTS</option>
        </select>
      </div>
      <div class="filter-group">
        <label>Status</label>
        <select v-model="filters.status" @change="load">
          <option value="">All</option>
          <option value="open">Open</option>
          <option value="closed">Closed</option>
          <option value="deal_done">Deal Done</option>
        </select>
      </div>
      <div class="filter-group">
        <label>Source</label>
        <select v-model="filters.source" @change="load">
          <option value="">All</option>
          <option value="direct">Direct</option>
          <option value="group">Group</option>
          <option value="community">Community</option>
        </select>
      </div>
      <div class="filter-group">
        <label>Date</label>
        <input type="date" v-model="filters.date" @change="load" />
      </div>
      <button class="btn-ghost sm" @click="resetFilters">Reset</button>
    </div>

    <div class="split-panel">
      <!-- Left: list -->
      <div class="list-panel">
        <div class="list-header">
          <span class="count">{{ inquiries.length }} inquiries</span>
          <button class="btn-ghost sm" @click="load">Refresh</button>
        </div>

        <div class="inquiry-list">
          <div
            v-for="inq in inquiries" :key="inq.id"
            class="inquiry-row"
            :class="[
              inq.inquiry_type,
              inq.status,
              selected?.id === inq.id && 'selected',
              inq.age_seconds < 60 && inq.status === 'open' && 'urgent',
            ]"
            @click="select(inq)"
          >
            <div class="row-top">
              <span :class="['type-badge', inq.inquiry_type]">
                {{ inq.inquiry_type === 'buy' ? 'WTB' : 'WTS' }}
              </span>
              <span class="contact-name">{{ inq.contact_name || inq.contact_phone || '—' }}</span>
              <span class="age" :class="{ red: inq.age_seconds > 60 && inq.status === 'open' }">
                {{ formatAge(inq.age_seconds) }}
              </span>
            </div>
            <div class="row-summary">{{ inq.summary }}</div>
            <div class="row-meta">
              <span class="source-badge">{{ inq.source_type }}</span>
              <span :class="['status-badge', inq.status]">{{ statusLabel(inq.status) }}</span>
              <span v-if="inq.products.length" class="product-count">
                {{ inq.products.length }} product{{ inq.products.length > 1 ? 's' : '' }}
              </span>
            </div>
          </div>

          <div v-if="inquiries.length === 0" class="empty-state">
            No inquiries match the current filters.
          </div>
        </div>
      </div>

      <!-- Right: detail panel -->
      <div class="detail-panel" v-if="selected">
        <div class="detail-header">
          <div class="detail-title">
            <span :class="['type-badge', selected.inquiry_type, 'lg']">
              {{ selected.inquiry_type === 'buy' ? 'WTB' : 'WTS' }}
            </span>
            <span class="detail-contact">
              {{ selected.contact_name || selected.contact_phone || 'Unknown' }}
            </span>
          </div>
          <div class="detail-meta">
            <span :class="['status-badge', selected.status]">{{ statusLabel(selected.status) }}</span>
            <span class="source-badge">{{ selected.source_type }}</span>
            <span class="time-label">{{ formatDatetime(selected.first_seen_at) }}</span>
          </div>
        </div>

        <div class="detail-summary">{{ selected.summary }}</div>

        <!-- Products -->
        <div v-if="selected.products.length" class="section">
          <div class="section-title">Products</div>
          <div class="product-list">
            <div v-for="p in selected.products" :key="p.canonical_name" class="product-item">
              <span class="product-name">{{ p.canonical_name }}</span>
              <span v-if="p.quantity" class="product-detail">×{{ p.quantity }}</span>
              <span v-if="p.price" class="product-detail">
                {{ p.currency || '' }} {{ p.price }}
              </span>
            </div>
          </div>
        </div>

        <!-- Linked messages -->
        <div class="section" v-if="detail?.messages?.length">
          <div class="section-title">Messages ({{ detail.messages.length }})</div>
          <div class="messages-list">
            <div v-for="m in detail.messages" :key="m.id" class="message-item">
              <div class="msg-header">
                <span class="msg-source">{{ m.chat_name }}</span>
                <span class="msg-type-tag">{{ m.chat_type }}</span>
                <span class="msg-time">{{ formatDatetime(m.message_time) }}</span>
              </div>
              <div class="msg-sender">{{ m.push_name || m.sender_number }}</div>
              <div class="msg-text">{{ m.message_text }}</div>
            </div>
          </div>
        </div>

        <!-- Remarks -->
        <div class="section">
          <div class="section-title">Remarks</div>
          <textarea
            v-model="remarksText"
            class="remarks-input"
            rows="3"
            placeholder="Add notes about this inquiry…"
            @blur="saveRemarks"
          />
        </div>

        <!-- Actions -->
        <div v-if="selected.status === 'open'" class="action-bar">
          <button class="btn-action close" @click="updateStatus('closed')">
            Mark Closed
          </button>
          <button class="btn-action deal" @click="updateStatus('deal_done')">
            Mark Deal Done
          </button>
        </div>
        <div v-else class="action-bar">
          <button class="btn-ghost sm" @click="updateStatus('open')">Reopen</button>
        </div>
      </div>

      <div v-else class="detail-empty">
        <span>Select an inquiry to view details</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import { accountsApi, tradingApi } from '../api/index.js'

const accounts  = ref([])
const inquiries = ref([])
const selected  = ref(null)
const detail    = ref(null)
const remarksText = ref('')

const filters = ref({
  account: '', type: '', status: '', source: '', date: '',
})

async function load() {
  const params = {}
  if (filters.value.account) params.account = filters.value.account
  if (filters.value.type)    params.type    = filters.value.type
  if (filters.value.status)  params.status  = filters.value.status
  if (filters.value.source)  params.source  = filters.value.source
  if (filters.value.date)    params.date    = filters.value.date
  const { data } = await tradingApi.listInquiries(params)
  inquiries.value = data
  if (selected.value) {
    const updated = data.find(i => i.id === selected.value.id)
    if (updated) selected.value = updated
  }
}

async function select(inq) {
  selected.value  = inq
  remarksText.value = inq.remarks || ''
  const { data } = await tradingApi.getInquiry(inq.id)
  detail.value = data
}

async function updateStatus(status) {
  await tradingApi.updateInquiry(selected.value.id, { status, remarks: remarksText.value })
  await load()
  if (selected.value) {
    const { data } = await tradingApi.getInquiry(selected.value.id)
    detail.value   = data
    selected.value = inquiries.value.find(i => i.id === selected.value.id) || selected.value
  }
}

async function saveRemarks() {
  if (!selected.value) return
  if (remarksText.value === (selected.value.remarks || '')) return
  await tradingApi.updateInquiry(selected.value.id, { remarks: remarksText.value })
}

function resetFilters() {
  filters.value = { account: '', type: '', status: '', source: '', date: '' }
  load()
}

function formatAge(secs) {
  if (secs < 60)   return `${secs}s`
  if (secs < 3600) return `${Math.floor(secs / 60)}m`
  return `${Math.floor(secs / 3600)}h`
}

function formatDatetime(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

function statusLabel(s) {
  return { open: 'Open', closed: 'Closed', deal_done: 'Deal Done' }[s] || s
}

onMounted(async () => {
  const { data } = await accountsApi.list()
  accounts.value = data
  await load()
})
</script>

<style scoped>
.inquiries-view { display: flex; flex-direction: column; height: 100%; overflow: hidden; }
.filter-bar { display: flex; gap: 10px; align-items: flex-end; padding: 12px 16px; background: #f9fafb; border-bottom: 1px solid #e5e7eb; flex-wrap: wrap; }
.filter-group { display: flex; flex-direction: column; gap: 2px; }
.filter-group label { font-size: 0.75rem; color: #6b7280; font-weight: 500; }
.filter-group select, .filter-group input { padding: 5px 8px; border: 1px solid #d1d5db; border-radius: 5px; font-size: 0.85rem; background: #fff; }
.split-panel { display: flex; flex: 1; overflow: hidden; }
.list-panel { width: 380px; flex-shrink: 0; display: flex; flex-direction: column; border-right: 1px solid #e5e7eb; }
.list-header { display: flex; justify-content: space-between; align-items: center; padding: 8px 14px; border-bottom: 1px solid #f3f4f6; }
.count { font-size: 0.83rem; color: #6b7280; }
.inquiry-list { flex: 1; overflow-y: auto; }
.inquiry-row { padding: 12px 14px; border-bottom: 1px solid #f3f4f6; cursor: pointer; transition: background 0.1s; }
.inquiry-row:hover { background: #f9fafb; }
.inquiry-row.selected { background: #eff6ff; border-left: 3px solid #2563eb; }
.inquiry-row.urgent { border-left: 3px solid #f59e0b; animation: pulse-border 1.5s ease-in-out infinite; }
@keyframes pulse-border { 0%,100% { border-left-color: #f59e0b; } 50% { border-left-color: #fbbf24; } }
.row-top { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
.contact-name { flex: 1; font-weight: 500; font-size: 0.9rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.age { font-size: 0.78rem; color: #6b7280; white-space: nowrap; }
.age.red { color: #dc2626; font-weight: 600; }
.row-summary { font-size: 0.83rem; color: #374151; margin-bottom: 6px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.row-meta { display: flex; gap: 6px; align-items: center; }
.type-badge { padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 700; }
.type-badge.buy { background: #dcfce7; color: #166534; }
.type-badge.sell { background: #fff7ed; color: #9a3412; }
.type-badge.lg { font-size: 0.85rem; padding: 3px 10px; }
.source-badge { background: #f3f4f6; color: #6b7280; padding: 1px 6px; border-radius: 4px; font-size: 0.73rem; text-transform: capitalize; }
.status-badge { padding: 1px 7px; border-radius: 4px; font-size: 0.73rem; font-weight: 600; }
.status-badge.open { background: #fef9c3; color: #854d0e; }
.status-badge.closed { background: #f3f4f6; color: #6b7280; }
.status-badge.deal_done { background: #dcfce7; color: #166534; }
.product-count { font-size: 0.73rem; color: #6b7280; }
.empty-state { padding: 40px; text-align: center; color: #9ca3af; font-size: 0.9rem; }
/* Detail panel */
.detail-panel { flex: 1; overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 16px; }
.detail-empty { flex: 1; display: flex; align-items: center; justify-content: center; color: #9ca3af; font-size: 0.9rem; }
.detail-header { display: flex; flex-direction: column; gap: 6px; }
.detail-title { display: flex; align-items: center; gap: 10px; }
.detail-contact { font-size: 1.1rem; font-weight: 600; }
.detail-meta { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.time-label { font-size: 0.8rem; color: #6b7280; }
.detail-summary { color: #374151; font-size: 0.95rem; line-height: 1.5; }
.section { display: flex; flex-direction: column; gap: 8px; }
.section-title { font-size: 0.78rem; font-weight: 600; color: #6b7280; text-transform: uppercase; letter-spacing: 0.05em; }
.product-list { display: flex; flex-direction: column; gap: 4px; }
.product-item { display: flex; gap: 8px; align-items: center; font-size: 0.9rem; }
.product-name { font-weight: 500; }
.product-detail { color: #6b7280; font-size: 0.85rem; }
.messages-list { display: flex; flex-direction: column; gap: 8px; max-height: 280px; overflow-y: auto; }
.message-item { background: #f9fafb; border-radius: 6px; padding: 10px 12px; border: 1px solid #e5e7eb; }
.msg-header { display: flex; gap: 8px; align-items: center; margin-bottom: 3px; }
.msg-source { font-weight: 500; font-size: 0.83rem; }
.msg-type-tag { background: #e5e7eb; color: #374151; padding: 1px 5px; border-radius: 3px; font-size: 0.72rem; text-transform: capitalize; }
.msg-time { font-size: 0.75rem; color: #9ca3af; margin-left: auto; }
.msg-sender { font-size: 0.78rem; color: #6b7280; margin-bottom: 3px; }
.msg-text { font-size: 0.88rem; color: #111827; line-height: 1.45; }
.remarks-input { width: 100%; padding: 8px 10px; border: 1px solid #d1d5db; border-radius: 6px; font-size: 0.9rem; resize: vertical; box-sizing: border-box; }
.action-bar { display: flex; gap: 10px; padding-top: 4px; }
.btn-action { padding: 9px 20px; border: none; border-radius: 7px; cursor: pointer; font-weight: 600; font-size: 0.9rem; }
.btn-action.close { background: #f3f4f6; color: #374151; }
.btn-action.deal { background: #16a34a; color: #fff; }
.btn-ghost { padding: 6px 14px; border: 1px solid #d1d5db; border-radius: 6px; background: transparent; cursor: pointer; font-size: 0.85rem; }
.btn-ghost.sm { padding: 4px 10px; font-size: 0.8rem; }
</style>
