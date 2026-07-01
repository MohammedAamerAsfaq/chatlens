<template>
  <div class="trading-view">
    <!-- Header -->
    <div class="trading-header">
      <div class="header-left">
        <h2>Trading Dashboard</h2>
        <span class="live-dot"></span>
        <span class="live-label">Live</span>
        <span class="last-update">Updated {{ lastUpdateLabel }}</span>
      </div>
      <div class="header-right">
        <select v-model="selectedAccount" @change="refresh" class="account-select">
          <option value="">All accounts</option>
          <option v-for="a in accounts" :key="a.id" :value="a.id">{{ a.display_name }}</option>
        </select>
        <button class="btn-ghost sm" @click="refresh">Refresh</button>
      </div>
    </div>

    <!-- Stat chips -->
    <div class="stat-row">
      <div class="stat-chip wtb">
        <div class="chip-value">{{ stats.today?.wtb_total ?? '—' }}</div>
        <div class="chip-label">WTB Today</div>
      </div>
      <div class="stat-chip wts">
        <div class="chip-value">{{ stats.today?.wts_total ?? '—' }}</div>
        <div class="chip-label">WTS Today</div>
      </div>
      <div class="stat-chip open">
        <div class="chip-value">{{ stats.today?.open ?? '—' }}</div>
        <div class="chip-label">Open</div>
      </div>
      <div class="stat-chip closed">
        <div class="chip-value">{{ stats.today?.closed ?? '—' }}</div>
        <div class="chip-label">Closed</div>
      </div>
      <div class="stat-chip deal">
        <div class="chip-value">{{ stats.today?.deal_done ?? '—' }}</div>
        <div class="chip-label">Deals Done</div>
      </div>
      <div class="stat-chip missed">
        <div class="chip-value">{{ stats.today?.missed ?? '—' }}</div>
        <div class="chip-label">Missed (&gt;60m)</div>
      </div>
      <div class="stat-chip neutral" v-if="stats.avg_response_minutes != null">
        <div class="chip-value">{{ stats.avg_response_minutes }}m</div>
        <div class="chip-label">Avg Response</div>
      </div>
      <div class="stat-chip neutral" v-if="stats.avg_deal_minutes != null">
        <div class="chip-value">{{ stats.avg_deal_minutes }}m</div>
        <div class="chip-label">Avg Deal Time</div>
      </div>
    </div>

    <!-- Live feed + analytics -->
    <div class="main-grid">
      <!-- WTB feed -->
      <div class="feed-col">
        <div class="feed-header wtb-header">
          <span class="feed-title">BUYING (WTB)</span>
          <span class="feed-count">{{ buyFeed.length }}</span>
        </div>
        <div class="feed-list">
          <div
            v-for="inq in buyFeed" :key="inq.id"
            class="feed-card"
            :class="{ urgent: inq.age_seconds < 60 }"
          >
            <div class="card-top">
              <span class="card-contact">{{ inq.contact_name || inq.contact_phone || 'Unknown' }}</span>
              <span class="card-age" :class="{ red: inq.age_seconds > 60 }">
                {{ formatAge(inq.age_seconds) }}
              </span>
            </div>
            <div class="card-summary">{{ inq.summary }}</div>
            <div class="card-products" v-if="inq.products.length">
              <span v-for="p in inq.products" :key="p.canonical_name" class="product-chip">
                {{ p.canonical_name }}{{ p.quantity ? ` ×${p.quantity}` : '' }}
              </span>
            </div>
            <div class="card-meta">
              <span class="source-label">{{ inq.source_type }}</span>
            </div>
            <div class="card-actions">
              <button class="act-btn close" @click="act(inq, 'closed')">Close</button>
              <button class="act-btn deal" @click="act(inq, 'deal_done')">Deal Done</button>
              <button v-if="inq.source_chat_id" class="act-btn chat" @click="viewChat(inq.source_chat_id)" title="Open conversation">Chat →</button>
            </div>
          </div>
          <div v-if="buyFeed.length === 0" class="feed-empty">No open buying inquiries</div>
        </div>
      </div>

      <!-- WTS feed -->
      <div class="feed-col">
        <div class="feed-header wts-header">
          <span class="feed-title">SELLING (WTS)</span>
          <span class="feed-count">{{ sellFeed.length }}</span>
        </div>
        <div class="feed-list">
          <div
            v-for="inq in sellFeed" :key="inq.id"
            class="feed-card"
            :class="{ urgent: inq.age_seconds < 60 }"
          >
            <div class="card-top">
              <span class="card-contact">{{ inq.contact_name || inq.contact_phone || 'Unknown' }}</span>
              <span class="card-age" :class="{ red: inq.age_seconds > 60 }">
                {{ formatAge(inq.age_seconds) }}
              </span>
            </div>
            <div class="card-summary">{{ inq.summary }}</div>
            <div class="card-products" v-if="inq.products.length">
              <span v-for="p in inq.products" :key="p.canonical_name" class="product-chip">
                {{ p.canonical_name }}{{ p.quantity ? ` ×${p.quantity}` : '' }}
              </span>
            </div>
            <div class="card-meta">
              <span class="source-label">{{ inq.source_type }}</span>
            </div>
            <div class="card-actions">
              <button class="act-btn close" @click="act(inq, 'closed')">Close</button>
              <button class="act-btn deal" @click="act(inq, 'deal_done')">Deal Done</button>
              <button v-if="inq.source_chat_id" class="act-btn chat" @click="viewChat(inq.source_chat_id)" title="Open conversation">Chat →</button>
            </div>
          </div>
          <div v-if="sellFeed.length === 0" class="feed-empty">No open selling offers</div>
        </div>
      </div>

      <!-- Analytics sidebar -->
      <div class="analytics-col">
        <!-- AI Classification Activity -->
        <div class="analytics-card">
          <div class="analytics-title" style="display:flex;justify-content:space-between;align-items:center;">
            <span>AI Pipeline (Today)</span>
            <div style="display:flex;gap:4px;">
              <button class="btn-ghost sm" @click="runBackfill" title="Classify recent unclassified messages">Backfill</button>
              <button
                v-if="classifyActivity?.today?.pending > 0"
                class="btn-retry sm"
                @click="runRetry"
                title="Re-run inquiry creation for classified messages with no Inquiry record"
              >Retry ({{ classifyActivity.today.pending }})</button>
            </div>
          </div>
          <div v-if="backfillStatus" class="backfill-msg">{{ backfillStatus }}</div>
          <pre v-if="retryError" class="retry-error">{{ retryError }}</pre>
          <div v-if="classifyActivity" class="classify-row">
            <span class="classify-chip total">{{ classifyActivity.today.total }} classified</span>
            <span class="classify-chip inquiry">{{ classifyActivity.today.as_inquiry }} inquiries</span>
            <span v-if="classifyActivity.today.pending > 0" class="classify-chip warn">
              {{ classifyActivity.today.pending }} pending
            </span>
            <span v-if="classifyActivity.today.type_missing > 0" class="classify-chip error">
              {{ classifyActivity.today.type_missing }} no type
            </span>
          </div>
          <div v-if="classifyActivity?.recent?.length" class="recent-classifications">
            <div
              v-for="mc in classifyActivity.recent" :key="mc.id"
              class="mc-row"
              :class="{ 'mc-inquiry': mc.is_inquiry }"
            >
              <span class="mc-badge" :class="mc.is_inquiry ? 'badge-yes' : 'badge-no'">
                {{ mc.is_inquiry ? (mc.inquiry_type || '?') : 'skip' }}
              </span>
              <span class="mc-summary">{{ mc.summary || mc.tags?.join(', ') }}</span>
            </div>
          </div>
          <div v-else-if="classifyActivity" class="feed-empty" style="padding:10px">No classifications today</div>
        </div>

        <!-- Source breakdown -->
        <div class="analytics-card">
          <div class="analytics-title">Source Breakdown</div>
          <table class="mini-table">
            <thead><tr><th>Source</th><th>WTB</th><th>WTS</th></tr></thead>
            <tbody>
              <tr v-for="src in ['direct','group','community']" :key="src">
                <td class="cap">{{ src }}</td>
                <td>{{ stats.by_source?.[src]?.wtb ?? 0 }}</td>
                <td>{{ stats.by_source?.[src]?.wts ?? 0 }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Top products -->
        <div class="analytics-card" v-if="productStats.length">
          <div class="analytics-title">Product Activity (Today)</div>
          <table class="mini-table">
            <thead><tr><th>Product</th><th>WTB</th><th>WTS</th><th>Deals</th></tr></thead>
            <tbody>
              <tr v-for="p in productStats" :key="p.product_id">
                <td>{{ p.name }}</td>
                <td>{{ p.wtb }}</td>
                <td>{{ p.wts }}</td>
                <td>{{ p.deals }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Hourly chart -->
        <div class="analytics-card" v-if="stats.timeline?.length">
          <div class="analytics-title">Hourly Activity</div>
          <div class="chart-wrap">
            <div
              v-for="slot in stats.timeline" :key="slot.hour"
              class="chart-slot"
              :title="`${slot.hour} — WTB: ${slot.wtb}, WTS: ${slot.wts}`"
            >
              <div class="bar-group">
                <div class="bar wtb-bar" :style="{ height: barHeight(slot.wtb) + 'px' }"></div>
                <div class="bar wts-bar" :style="{ height: barHeight(slot.wts) + 'px' }"></div>
              </div>
              <div class="slot-label">{{ slot.hour.split(':')[0] }}</div>
            </div>
          </div>
          <div class="chart-legend">
            <span class="legend-dot wtb"></span> WTB &nbsp;
            <span class="legend-dot wts"></span> WTS
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useConversationsStore } from '@/stores/conversations'
import { accountsApi, tradingApi } from '../api/index.js'

const router = useRouter()
const convStore = useConversationsStore()

async function viewChat(chatId) {
  if (!chatId) return
  await router.push({ name: 'conversations' })
  await convStore.selectChat(chatId)
}

const accounts           = ref([])
const selectedAccount    = ref('')
const stats              = ref({})
const feed               = ref([])
const productStats       = ref([])
const classifyActivity   = ref(null)
const backfillStatus     = ref('')
const retryError         = ref('')
const lastUpdate         = ref(null)
let   pollTimer          = null

const buyFeed  = computed(() => feed.value.filter(i => i.inquiry_type === 'buy'))
const sellFeed = computed(() => feed.value.filter(i => i.inquiry_type === 'sell'))

const lastUpdateLabel = computed(() => {
  if (!lastUpdate.value) return '—'
  const secs = Math.floor((Date.now() - lastUpdate.value) / 1000)
  if (secs < 10) return 'just now'
  return `${secs}s ago`
})

const maxBar = computed(() => {
  const vals = (stats.value.timeline || []).flatMap(s => [s.wtb, s.wts])
  return Math.max(...vals, 1)
})

function barHeight(val) {
  return Math.round((val / maxBar.value) * 60)
}

function formatAge(secs) {
  if (secs < 60)   return `${secs}s`
  if (secs < 3600) return `${Math.floor(secs / 60)}m`
  return `${Math.floor(secs / 3600)}h`
}

async function refresh() {
  const accountParam = selectedAccount.value || undefined
  const params = accountParam ? { account: accountParam } : {}
  const [statsRes, feedRes, prodRes, actRes] = await Promise.all([
    tradingApi.getStats(params),
    tradingApi.getOpenFeed(params),
    tradingApi.getProductStats(params),
    tradingApi.getClassificationActivity(params),
  ])
  stats.value            = statsRes.data
  feed.value             = feedRes.data
  productStats.value     = prodRes.data
  classifyActivity.value = actRes.data
  lastUpdate.value       = Date.now()
}

async function act(inq, status) {
  await tradingApi.updateInquiry(inq.id, { status })
  await refresh()
}

async function runBackfill() {
  backfillStatus.value = 'Queuing…'
  try {
    const accountParam = selectedAccount.value || undefined
    const { data } = await tradingApi.backfillClassify(
      accountParam ? { account: accountParam, limit: 20 } : { limit: 20 }
    )
    backfillStatus.value = `Queued ${data.queued} message(s) — check logs in ~30s`
    setTimeout(() => { backfillStatus.value = '' }, 15000)
    setTimeout(refresh, 8000)
  } catch (e) {
    backfillStatus.value = 'Failed: ' + (e.response?.data?.detail || e.message)
  }
}

async function runRetry() {
  backfillStatus.value = 'Retrying inquiry creation…'
  try {
    const accountParam = selectedAccount.value || undefined
    const { data } = await tradingApi.retryInquiries(
      accountParam ? { account: accountParam } : {}
    )
    if (data.errors && data.first_error) {
      backfillStatus.value = `Created ${data.created}, ${data.errors} errors — see below`
      retryError.value = data.first_error
    } else {
      backfillStatus.value = `Created ${data.created} inquiries`
      retryError.value = ''
      setTimeout(() => { backfillStatus.value = '' }, 10000)
    }
    await refresh()
  } catch (e) {
    backfillStatus.value = 'Failed: ' + (e.response?.data?.detail || e.message)
  }
}

onMounted(async () => {
  const { data } = await accountsApi.list()
  accounts.value = data
  await refresh()
  pollTimer = setInterval(refresh, 15000)
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
})
</script>

<style scoped>
.trading-view { display: flex; flex-direction: column; height: 100%; overflow: hidden; background: #f9fafb; }
.trading-header { display: flex; justify-content: space-between; align-items: center; padding: 14px 20px; background: #fff; border-bottom: 1px solid #e5e7eb; }
.header-left { display: flex; align-items: center; gap: 10px; }
.header-left h2 { margin: 0; font-size: 1.15rem; }
.live-dot { width: 8px; height: 8px; border-radius: 50%; background: #22c55e; animation: blink 1.5s ease-in-out infinite; }
@keyframes blink { 0%,100% { opacity: 1; } 50% { opacity: 0.3; } }
.live-label { font-size: 0.8rem; color: #22c55e; font-weight: 600; }
.last-update { font-size: 0.78rem; color: #9ca3af; }
.header-right { display: flex; gap: 10px; align-items: center; }
.account-select { padding: 5px 10px; border: 1px solid #d1d5db; border-radius: 6px; font-size: 0.85rem; }
/* Stat row */
.stat-row { display: flex; gap: 10px; padding: 12px 20px; background: #fff; border-bottom: 1px solid #e5e7eb; flex-wrap: wrap; }
.stat-chip { padding: 10px 18px; border-radius: 8px; text-align: center; min-width: 90px; }
.stat-chip.wtb      { background: #dcfce7; }
.stat-chip.wts      { background: #fff7ed; }
.stat-chip.open     { background: #fef9c3; }
.stat-chip.closed   { background: #f3f4f6; }
.stat-chip.deal     { background: #dbeafe; }
.stat-chip.missed   { background: #fee2e2; }
.stat-chip.neutral  { background: #f3f4f6; }
.chip-value { font-size: 1.5rem; font-weight: 700; line-height: 1.2; }
.chip-label { font-size: 0.72rem; color: #6b7280; font-weight: 500; margin-top: 2px; }
/* Main grid */
.main-grid { flex: 1; display: grid; grid-template-columns: 1fr 1fr 280px; gap: 0; overflow: hidden; }
.feed-col { display: flex; flex-direction: column; border-right: 1px solid #e5e7eb; overflow: hidden; }
.feed-header { display: flex; align-items: center; gap: 10px; padding: 10px 14px; border-bottom: 1px solid #e5e7eb; }
.wtb-header { background: #f0fdf4; }
.wts-header { background: #fff7ed; }
.feed-title { font-weight: 700; font-size: 0.85rem; letter-spacing: 0.05em; }
.feed-count { background: #e5e7eb; border-radius: 999px; padding: 1px 8px; font-size: 0.78rem; }
.feed-list { flex: 1; overflow-y: auto; padding: 10px; display: flex; flex-direction: column; gap: 8px; }
.feed-card { background: #fff; border: 1px solid #e5e7eb; border-radius: 8px; padding: 12px; }
.feed-card.urgent { border-left: 3px solid #f59e0b; }
.card-top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; }
.card-contact { font-weight: 600; font-size: 0.88rem; }
.card-age { font-size: 0.78rem; color: #6b7280; }
.card-age.red { color: #dc2626; font-weight: 700; }
.card-summary { font-size: 0.83rem; color: #374151; margin-bottom: 6px; }
.card-products { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 6px; }
.product-chip { background: #eff6ff; color: #1d4ed8; padding: 1px 7px; border-radius: 4px; font-size: 0.75rem; }
.card-meta { margin-bottom: 8px; }
.source-label { font-size: 0.73rem; color: #9ca3af; text-transform: capitalize; }
.card-actions { display: flex; gap: 6px; }
.act-btn { padding: 4px 12px; border: none; border-radius: 5px; cursor: pointer; font-size: 0.8rem; font-weight: 500; }
.act-btn.close { background: #f3f4f6; color: #374151; }
.act-btn.deal  { background: #16a34a; color: #fff; }
.act-btn.chat  { background: #eff6ff; color: #1d4ed8; margin-left: auto; }
.feed-empty { text-align: center; color: #9ca3af; font-size: 0.85rem; padding: 30px; }
/* Analytics */
.analytics-col { overflow-y: auto; padding: 12px; display: flex; flex-direction: column; gap: 12px; background: #fff; }
.analytics-card { border: 1px solid #e5e7eb; border-radius: 8px; padding: 12px; }
.analytics-title { font-size: 0.78rem; font-weight: 600; color: #6b7280; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 10px; }
.mini-table { width: 100%; border-collapse: collapse; font-size: 0.82rem; }
.mini-table th { color: #9ca3af; font-weight: 500; padding: 3px 6px; text-align: left; border-bottom: 1px solid #f3f4f6; }
.mini-table td { padding: 4px 6px; border-bottom: 1px solid #f9fafb; }
.mini-table td.cap { text-transform: capitalize; }
/* Chart */
.chart-wrap { display: flex; align-items: flex-end; gap: 3px; height: 80px; padding-top: 10px; }
.chart-slot { display: flex; flex-direction: column; align-items: center; flex: 1; }
.bar-group { display: flex; align-items: flex-end; gap: 1px; }
.bar { width: 6px; border-radius: 2px 2px 0 0; min-height: 2px; transition: height 0.3s; }
.wtb-bar { background: #22c55e; }
.wts-bar { background: #f97316; }
.slot-label { font-size: 0.62rem; color: #9ca3af; margin-top: 2px; }
.chart-legend { display: flex; align-items: center; gap: 4px; font-size: 0.75rem; color: #6b7280; margin-top: 8px; }
.legend-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
.legend-dot.wtb { background: #22c55e; }
.legend-dot.wts { background: #f97316; }
.btn-ghost { padding: 6px 14px; border: 1px solid #d1d5db; border-radius: 6px; background: transparent; cursor: pointer; font-size: 0.85rem; }
.btn-ghost.sm { padding: 4px 10px; font-size: 0.8rem; }
/* Classification activity */
.backfill-msg { font-size: 0.75rem; color: #6b7280; margin-bottom: 6px; }
.classify-row { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 8px; }
.classify-chip { padding: 2px 8px; border-radius: 999px; font-size: 0.73rem; font-weight: 600; }
.classify-chip.total   { background: #f3f4f6; color: #374151; }
.classify-chip.inquiry { background: #dcfce7; color: #15803d; }
.classify-chip.warn    { background: #fef9c3; color: #92400e; }
.classify-chip.error   { background: #fee2e2; color: #b91c1c; }
.btn-retry { padding: 4px 10px; font-size: 0.8rem; border: 1px solid #f59e0b; border-radius: 6px; background: #fffbeb; color: #92400e; cursor: pointer; font-weight: 600; }
.recent-classifications { display: flex; flex-direction: column; gap: 3px; }
.mc-row { display: flex; align-items: flex-start; gap: 6px; padding: 3px 0; border-bottom: 1px solid #f3f4f6; }
.mc-badge { flex-shrink: 0; padding: 1px 6px; border-radius: 4px; font-size: 0.68rem; font-weight: 700; text-transform: uppercase; }
.badge-yes { background: #dcfce7; color: #15803d; }
.badge-no  { background: #f3f4f6; color: #9ca3af; }
.mc-summary { font-size: 0.75rem; color: #374151; line-height: 1.3; }
.retry-error { font-size: 0.7rem; color: #b91c1c; background: #fef2f2; border: 1px solid #fecaca; border-radius: 4px; padding: 6px 8px; white-space: pre-wrap; word-break: break-all; margin-top: 6px; max-height: 200px; overflow-y: auto; }
</style>
