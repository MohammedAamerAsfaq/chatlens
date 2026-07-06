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

    <!-- Status filter tabs -->
    <div class="status-filter-row">
      <button
        v-for="f in statusFilters" :key="f.value"
        @click="setStatusFilter(f.value)"
        :class="['sfilter-btn', selectedStatus === f.value ? 'sfilter-active' : '']"
      >{{ f.label }}</button>
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
              <span class="card-contact">
                {{ inq.contact_name || inq.contact_phone || 'Unknown' }}
                <span v-if="inq.contact_name && inq.contact_phone" class="card-phone">{{ inq.contact_phone }}</span>
              </span>
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
            <div class="card-stock-hints" v-if="getInventoryHints(inq).length">
              <div v-for="h in getInventoryHints(inq)" :key="h.name" class="stock-hint">
                <span class="stock-icon">✓</span>
                {{ h.product.name }} in stock
                <span v-if="h.product.sale_price"> · Sale: {{ h.product.currency || 'USD' }} {{ h.product.sale_price }}</span>
                <span> · Qty: {{ h.product.qty }}</span>
                <span v-if="h.product.cost_price"> · Cost: {{ h.product.currency || 'USD' }} {{ h.product.cost_price }}</span>
              </div>
            </div>
            <div class="card-meta">
              <span class="source-label">{{ inq.source_type }}</span>
              <span v-if="inq.account_name" class="account-badge">{{ inq.account_name }}</span>
            </div>
            <div class="card-actions">
              <select class="status-select-mini" @change="setStatus(inq, $event)">
                <option value="" disabled selected>Set status…</option>
                <option value="quoted_waiting">Quoted - Waiting</option>
                <option value="no_response">No Response</option>
                <option value="price_high">Price High</option>
                <option value="no_stock">No Stock</option>
                <option value="not_dealing">Not Dealing ATM</option>
                <option value="irrelevant">Irrelevant</option>
                <option value="closed">Close</option>
              </select>
              <button class="act-btn close" @click="act(inq, 'closed')">Close</button>
              <button class="act-btn deal" @click="act(inq, 'deal_done')">Deal Done</button>
              <button v-if="inq.source_chat_id" class="act-btn chat" @click="viewChat(inq.source_chat_id, inq.account, inq.source_message_id, inq.source_message_time)" title="Open conversation">Chat →</button>
              <a v-if="waLink(inq)" :href="waLink(inq)" class="act-btn wa" title="Open in WhatsApp">
                <svg viewBox="0 0 24 24" fill="currentColor" width="13" height="13"><path d="M12.04 2C6.58 2 2.13 6.45 2.13 11.91c0 1.75.46 3.45 1.32 4.95L2.05 22l5.25-1.38c1.45.79 3.08 1.21 4.74 1.21 5.46 0 9.91-4.45 9.91-9.91S17.5 2 12.04 2zm4.82 13.68c-.2.56-1.18 1.07-1.62 1.14-.44.07-.98.1-1.58-.1-.36-.12-.83-.28-1.42-.55-2.5-1.08-4.13-3.6-4.26-3.77-.13-.17-1.05-1.4-1.05-2.67 0-1.27.66-1.9.9-2.16.23-.26.5-.32.67-.32.17 0 .33 0 .48.01.15.01.36-.06.56.43.2.49.7 1.7.76 1.82.06.13.1.27.02.43-.08.17-.12.27-.23.41-.11.14-.24.31-.33.42-.11.13-.23.27-.1.53.13.26.59 1 1.27 1.63.87.8 1.61 1.04 1.87 1.16.26.12.41.1.57-.06.16-.16.66-.77.83-1.04.17-.26.34-.22.57-.13.23.09 1.44.68 1.69.8.25.12.41.18.47.28.07.1.07.56-.13 1.12z"/></svg>
                WA
              </a>
              <a v-if="waAskPriceLink(inq)" :href="waAskPriceLink(inq)" class="act-btn wa-ask" title="Ask price on WhatsApp">
                Ask Price
              </a>
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
              <span class="card-contact">
                {{ inq.contact_name || inq.contact_phone || 'Unknown' }}
                <span v-if="inq.contact_name && inq.contact_phone" class="card-phone">{{ inq.contact_phone }}</span>
              </span>
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
              <span v-if="inq.account_name" class="account-badge">{{ inq.account_name }}</span>
            </div>
            <div class="card-actions">
              <select class="status-select-mini" @change="setStatus(inq, $event)">
                <option value="" disabled selected>Set status…</option>
                <option value="quoted_waiting">Quoted - Waiting</option>
                <option value="no_response">No Response</option>
                <option value="price_high">Price High</option>
                <option value="no_stock">No Stock</option>
                <option value="not_dealing">Not Dealing ATM</option>
                <option value="irrelevant">Irrelevant</option>
                <option value="closed">Close</option>
              </select>
              <button class="act-btn close" @click="act(inq, 'closed')">Close</button>
              <button class="act-btn deal" @click="act(inq, 'deal_done')">Deal Done</button>
              <button v-if="inq.source_chat_id" class="act-btn chat" @click="viewChat(inq.source_chat_id, inq.account, inq.source_message_id, inq.source_message_time)" title="Open conversation">Chat →</button>
              <a v-if="waLink(inq)" :href="waLink(inq)" class="act-btn wa" title="Open in WhatsApp">
                <svg viewBox="0 0 24 24" fill="currentColor" width="13" height="13"><path d="M12.04 2C6.58 2 2.13 6.45 2.13 11.91c0 1.75.46 3.45 1.32 4.95L2.05 22l5.25-1.38c1.45.79 3.08 1.21 4.74 1.21 5.46 0 9.91-4.45 9.91-9.91S17.5 2 12.04 2zm4.82 13.68c-.2.56-1.18 1.07-1.62 1.14-.44.07-.98.1-1.58-.1-.36-.12-.83-.28-1.42-.55-2.5-1.08-4.13-3.6-4.26-3.77-.13-.17-1.05-1.4-1.05-2.67 0-1.27.66-1.9.9-2.16.23-.26.5-.32.67-.32.17 0 .33 0 .48.01.15.01.36-.06.56.43.2.49.7 1.7.76 1.82.06.13.1.27.02.43-.08.17-.12.27-.23.41-.11.14-.24.31-.33.42-.11.13-.23.27-.1.53.13.26.59 1 1.27 1.63.87.8 1.61 1.04 1.87 1.16.26.12.41.1.57-.06.16-.16.66-.77.83-1.04.17-.26.34-.22.57-.13.23.09 1.44.68 1.69.8.25.12.41.18.47.28.07.1.07.56-.13 1.12z"/></svg>
                WA
              </a>
              <a v-if="waAskPriceLink(inq)" :href="waAskPriceLink(inq)" class="act-btn wa-ask" title="Ask price on WhatsApp">
                Ask Price
              </a>
            </div>
          </div>
          <div v-if="sellFeed.length === 0" class="feed-empty">No open selling offers</div>
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

async function viewChat(chatId, accountId, messageId, messageTime) {
  if (!chatId) return
  if (accountId && convStore.selectedAccountId !== accountId) {
    await convStore.switchAccount(accountId)
  }
  convStore.selectChat(chatId, { messageId, messageTime })
  router.push({ name: 'conversations' })
}

const accounts         = ref([])
const selectedAccount  = ref('')
const selectedStatus   = ref('open')
const stats            = ref({})
const feed             = ref([])
const allProducts      = ref([])
const lastUpdate       = ref(null)
let   pollTimer        = null

const statusFilters = [
  { value: 'all',            label: 'All Today' },
  { value: 'open',           label: 'Open' },
  { value: 'quoted_waiting', label: 'Quoted - Waiting' },
  { value: 'no_response',    label: 'No Response' },
  { value: 'price_high',     label: 'Price High' },
  { value: 'no_stock',       label: 'No Stock' },
  { value: 'not_dealing',    label: 'Not Dealing' },
  { value: 'irrelevant',     label: 'Irrelevant' },
  { value: 'closed',         label: 'Closed' },
  { value: 'deal_done',      label: 'Deal Done' },
]

function setStatusFilter(val) {
  selectedStatus.value = val
  refresh()
}

const productMap = computed(() => {
  const m = {}
  for (const p of allProducts.value) m[p.id] = p
  return m
})

function matchInventory(p) {
  let match = p.product_id ? productMap.value[p.product_id] : null
  if (!match && p.canonical_name) {
    const needle = p.canonical_name.toLowerCase()
    match = allProducts.value.find(prod => {
      const hay = prod.name.toLowerCase()
      return hay === needle || hay.includes(needle) || needle.includes(hay)
    })
  }
  return match
}

function getInventoryHints(inq) {
  if (inq.inquiry_type !== 'buy') return []
  const hints = []
  for (const p of (inq.products || [])) {
    const match = matchInventory(p)
    if (match && (match.qty > 0 || match.sale_price != null)) {
      hints.push({ name: p.canonical_name, product: match })
    }
  }
  return hints
}

const buyFeed  = computed(() => feed.value.filter(i => i.inquiry_type === 'buy'))
const sellFeed = computed(() => feed.value.filter(i => i.inquiry_type === 'sell'))

const lastUpdateLabel = computed(() => {
  if (!lastUpdate.value) return '—'
  const secs = Math.floor((Date.now() - lastUpdate.value) / 1000)
  if (secs < 10) return 'just now'
  return `${secs}s ago`
})


function formatAge(secs) {
  if (secs < 60)   return `${secs}s`
  if (secs < 3600) return `${Math.floor(secs / 60)}m`
  return `${Math.floor(secs / 3600)}h`
}

async function refresh() {
  const accountParam = selectedAccount.value || undefined
  const params = accountParam ? { account: accountParam } : {}
  const feedParams = { ...params, status: selectedStatus.value }
  const [statsRes, feedRes, prodsRes] = await Promise.all([
    tradingApi.getStats(params),
    tradingApi.getOpenFeed(feedParams),
    tradingApi.listProducts({ page_size: 1000, is_active: true }),
  ])
  stats.value       = statsRes.data
  feed.value        = feedRes.data
  allProducts.value = prodsRes.data.results ?? prodsRes.data
  lastUpdate.value  = Date.now()
}

async function act(inq, status) {
  await tradingApi.updateInquiry(inq.id, { status })
  await refresh()
}

function setStatus(inq, e) {
  const val = e.target.value
  e.target.value = ''
  if (val) act(inq, val)
}

function waPrefillText(inq) {
  const lines = []
  for (const p of (inq.products || [])) {
    const match = matchInventory(p)
    let line = p.canonical_name || match?.name
    if (!line) continue
    line = line.replace(/^\[[^\]]*\]\s*/, '')
    if (p.quantity) line += ` x${p.quantity}`
    if (match?.sale_price != null) line += ` - ${match.sale_price}`
    lines.push(line)
  }
  return lines.join('\n')
}

function waLink(inq) {
  const phone = inq.contact_phone
  if (!phone) return null
  const clean = phone.split('@')[0].replace(/\D/g, '')
  if (!clean) return null
  const text = waPrefillText(inq)
  const params = new URLSearchParams({ phone: clean })
  if (text) params.set('text', text)
  return `whatsapp://send?${params.toString()}`
}

function waAskPriceText(inq) {
  const lines = []
  for (const p of (inq.products || [])) {
    let line = p.canonical_name
    if (!line) continue
    line = line.replace(/^\[[^\]]*\]\s*/, '')
    if (p.quantity) line += ` x${p.quantity}`
    lines.push(line)
  }
  return lines.length ? `${lines.join('\n')}\n\nPrice?` : 'Price?'
}

function waAskPriceLink(inq) {
  const phone = inq.contact_phone
  if (!phone) return null
  const clean = phone.split('@')[0].replace(/\D/g, '')
  if (!clean) return null
  const params = new URLSearchParams({ phone: clean, text: waAskPriceText(inq) })
  return `whatsapp://send?${params.toString()}`
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
/* Status filter row */
.status-filter-row { display: flex; gap: 6px; padding: 8px 16px; background: #fff; border-bottom: 1px solid #e5e7eb; flex-wrap: wrap; }
.sfilter-btn { padding: 4px 12px; border: 1px solid #d1d5db; border-radius: 999px; background: #fff; color: #6b7280; font-size: 0.78rem; font-weight: 500; cursor: pointer; transition: all 0.15s; white-space: nowrap; }
.sfilter-btn:hover { border-color: #9ca3af; color: #374151; }
.sfilter-active { background: #1d4ed8; border-color: #1d4ed8; color: #fff !important; }
/* Main grid */
.main-grid { flex: 1; display: grid; grid-template-columns: 1fr 1fr; gap: 0; overflow: hidden; }
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
.card-phone { font-weight: 400; font-size: 0.78rem; color: #6b7280; margin-left: 6px; }
.card-age { font-size: 0.78rem; color: #6b7280; }
.card-age.red { color: #dc2626; font-weight: 700; }
.card-summary { font-size: 0.83rem; color: #374151; margin-bottom: 6px; }
.card-products { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 6px; }
.product-chip { background: #eff6ff; color: #1d4ed8; padding: 1px 7px; border-radius: 4px; font-size: 0.75rem; }
.card-meta { display: flex; align-items: center; gap: 6px; margin-bottom: 8px; flex-wrap: wrap; }
.source-label { font-size: 0.73rem; color: #9ca3af; text-transform: capitalize; }
.account-badge { font-size: 0.7rem; background: #ede9fe; color: #6d28d9; padding: 1px 7px; border-radius: 999px; font-weight: 600; }
.card-actions { display: flex; gap: 6px; align-items: center; }
.act-btn { padding: 4px 12px; border: none; border-radius: 5px; cursor: pointer; font-size: 0.8rem; font-weight: 500; }
.act-btn.close { background: #f3f4f6; color: #374151; }
.act-btn.deal  { background: #16a34a; color: #fff; }
.act-btn.chat  { background: #eff6ff; color: #1d4ed8; margin-left: auto; }
.act-btn.wa    { background: #dcfce7; color: #16a34a; display: flex; align-items: center; gap: 3px; text-decoration: none; }
.act-btn.wa-ask { background: #fef9c3; color: #92400e; text-decoration: none; }
.status-select-mini { padding: 4px 8px; border: 1px solid #d1d5db; border-radius: 5px; font-size: 0.78rem; color: #374151; cursor: pointer; background: #fff; }
.feed-empty { text-align: center; color: #9ca3af; font-size: 0.85rem; padding: 30px; }
.btn-ghost { padding: 6px 14px; border: 1px solid #d1d5db; border-radius: 6px; background: transparent; cursor: pointer; font-size: 0.85rem; }
.btn-ghost.sm { padding: 4px 10px; font-size: 0.8rem; }
/* Inventory stock hints on WTB cards */
.card-stock-hints { display: flex; flex-direction: column; gap: 3px; margin-bottom: 6px; }
.stock-hint { background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 5px; padding: 4px 8px; font-size: 0.75rem; color: #166534; line-height: 1.4; }
.stock-icon { color: #16a34a; font-weight: 700; margin-right: 3px; }
</style>
