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

    <!-- Error banner -->
    <div v-if="categoryError" class="error-banner">
      {{ categoryError }}
      <button class="error-dismiss" @click="categoryError = ''">✕</button>
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
          <span class="feed-count">{{ buyFeed.length }}{{ buyFeed.length < buyTotal ? ` / ${buyTotal}` : '' }}</span>
        </div>
        <div class="feed-list" @scroll="onBuyScroll">
          <div
            v-for="inq in buyFeed" :key="inq.id"
            class="feed-card"
            :class="{ urgent: inq.age_seconds < 60 }"
          >
            <div class="card-header">
              <div class="card-top">
                <span class="card-contact">
                  {{ inq.contact_name || inq.contact_phone || 'Unknown' }}
                  <span v-if="inq.contact_name && inq.contact_phone" class="card-phone">{{ inq.contact_phone }}</span>
                </span>
                <select
                  v-if="inq.contact"
                  class="category-select-mini"
                  :class="{ 'category-select-suggested': hasSuggestion(inq) }"
                  :value="categoryDisplayValue(inq)"
                  @change="setContactCategory(inq, $event.target.value)"
                >
                  <option value="">Uncategorized</option>
                  <option value="supplier">Supplier</option>
                  <option value="customer">Customer</option>
                  <option value="both">Both</option>
                </select>
                <button
                  v-if="hasSuggestion(inq)"
                  class="category-suggestion-chip"
                  @click="setContactCategory(inq, inq.suggested_contact_category)"
                  :title="`AI suggests: ${categoryLabel(inq.suggested_contact_category)} — click to confirm`"
                >✓ Apply</button>
                <span class="source-label">{{ inq.source_type }}</span>
                <span v-if="inq.account_name" class="account-badge">{{ inq.account_name }}</span>
                <span class="card-age" :class="{ red: inq.age_seconds > 60 }">
                  {{ formatAge(inq.age_seconds) }}
                </span>
              </div>
            </div>
            <div class="card-body">
              <div
                class="body-row"
                :class="{ expanded: isRowExpanded(inq.id, 'summary') }"
                @click.stop="toggleBodyRow(inq.id, 'summary')"
              >
                <div class="body-row-label">Summary</div>
                <div class="body-row-content">{{ inq.summary || '—' }}</div>
              </div>
              <div
                class="body-row"
                :class="{ expanded: isRowExpanded(inq.id, 'message') }"
                @click.stop="toggleBodyRow(inq.id, 'message')"
              >
                <div class="body-row-label">Original Message</div>
                <div class="body-row-content">{{ inq.source_message_text || '—' }}</div>
              </div>
              <div
                class="body-row"
                :class="{ expanded: isRowExpanded(inq.id, 'stock') }"
                @click.stop="toggleBodyRow(inq.id, 'stock')"
              >
                <div class="body-row-label">Stock Suggestion</div>
                <div class="body-row-content">
                  <template v-if="getInventoryHints(inq).length">
                    <div v-for="h in getInventoryHints(inq)" :key="h.name" class="stock-hint" :class="{ 'stock-hint-mismatch': h.mismatch }">
                      <span class="stock-icon">{{ h.mismatch ? '⚠' : '✓' }}</span>
                      {{ h.product.name }} in stock
                      <span v-if="h.mismatch" class="mismatch-tag">— not "{{ h.name }}", closest match only</span>
                      <span v-if="h.product.sale_price"> · Sale: {{ h.product.currency || 'USD' }} {{ h.product.sale_price }}</span>
                      <span> · Qty: {{ h.product.qty }}</span>
                      <span v-if="h.product.cost_price">
                        ·
                        <span :class="{ 'cost-loss': h.product.sale_price != null && h.product.sale_price < h.product.cost_price }">
                          Cost: {{ h.product.currency || 'USD' }} {{ h.product.cost_price }}
                        </span>
                      </span>
                    </div>
                  </template>
                  <span v-else class="body-row-empty">No matching stock found</span>
                </div>
              </div>
            </div>
            <div class="card-footer">
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
                  <option value="incorrect_match">Incorrect Match</option>
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
                <a v-if="waPriceListLink(inq)" :href="waPriceListLink(inq)" class="act-btn wa-list" title="Send full price list on WhatsApp">
                  Price List
                </a>
              </div>
              <div v-if="incorrectMatchForms[inq.id]?.open" class="incorrect-match-form">
                <input
                  v-model="incorrectMatchForms[inq.id].reason"
                  placeholder="What's incorrect about this match?"
                  class="incorrect-match-input"
                  @keydown.enter="submitIncorrectMatch(inq)"
                />
                <button class="act-btn close" @click="submitIncorrectMatch(inq)">Save</button>
                <button class="act-btn chat" @click="cancelIncorrectMatch(inq)">Cancel</button>
              </div>
            </div>
          </div>
          <div v-if="buyFeed.length === 0" class="feed-empty">No open buying inquiries</div>
          <div v-if="buyLoadingMore" class="feed-loading-more">Loading more…</div>
        </div>
      </div>

      <!-- WTS feed -->
      <div class="feed-col">
        <div class="feed-header wts-header">
          <span class="feed-title">SELLING (WTS)</span>
          <span class="feed-count">{{ sellFeed.length }}{{ sellFeed.length < sellTotal ? ` / ${sellTotal}` : '' }}</span>
        </div>
        <div class="feed-list" @scroll="onSellScroll">
          <div
            v-for="inq in sellFeed" :key="inq.id"
            class="feed-card"
            :class="{ urgent: inq.age_seconds < 60 }"
          >
            <div class="card-header">
              <div class="card-top">
                <span class="card-contact">
                  {{ inq.contact_name || inq.contact_phone || 'Unknown' }}
                  <span v-if="inq.contact_name && inq.contact_phone" class="card-phone">{{ inq.contact_phone }}</span>
                </span>
                <select
                  v-if="inq.contact"
                  class="category-select-mini"
                  :class="{ 'category-select-suggested': hasSuggestion(inq) }"
                  :value="categoryDisplayValue(inq)"
                  @change="setContactCategory(inq, $event.target.value)"
                >
                  <option value="">Uncategorized</option>
                  <option value="supplier">Supplier</option>
                  <option value="customer">Customer</option>
                  <option value="both">Both</option>
                </select>
                <button
                  v-if="hasSuggestion(inq)"
                  class="category-suggestion-chip"
                  @click="setContactCategory(inq, inq.suggested_contact_category)"
                  :title="`AI suggests: ${categoryLabel(inq.suggested_contact_category)} — click to confirm`"
                >✓ Apply</button>
                <span class="source-label">{{ inq.source_type }}</span>
                <span v-if="inq.account_name" class="account-badge">{{ inq.account_name }}</span>
                <span class="card-age" :class="{ red: inq.age_seconds > 60 }">
                  {{ formatAge(inq.age_seconds) }}
                </span>
              </div>
            </div>
            <div class="card-body">
              <div
                class="body-row"
                :class="{ expanded: isRowExpanded(inq.id, 'summary') }"
                @click.stop="toggleBodyRow(inq.id, 'summary')"
              >
                <div class="body-row-label">Summary</div>
                <div class="body-row-content">{{ inq.summary || '—' }}</div>
              </div>
              <div
                class="body-row"
                :class="{ expanded: isRowExpanded(inq.id, 'message') }"
                @click.stop="toggleBodyRow(inq.id, 'message')"
              >
                <div class="body-row-label">Original Message</div>
                <div class="body-row-content">{{ inq.source_message_text || '—' }}</div>
              </div>
              <div
                class="body-row"
                :class="{ expanded: isRowExpanded(inq.id, 'stock') }"
                @click.stop="toggleBodyRow(inq.id, 'stock')"
              >
                <div class="body-row-label">Stock Suggestion</div>
                <div class="body-row-content">
                  <template v-if="getInventoryHints(inq).length">
                    <div v-for="h in getInventoryHints(inq)" :key="h.name" class="stock-hint" :class="{ 'stock-hint-mismatch': h.mismatch }">
                      <span class="stock-icon">{{ h.mismatch ? '⚠' : '✓' }}</span>
                      {{ h.product.name }} in stock
                      <span v-if="h.mismatch" class="mismatch-tag">— not "{{ h.name }}", closest match only</span>
                      <span v-if="h.product.sale_price"> · Sale: {{ h.product.currency || 'USD' }} {{ h.product.sale_price }}</span>
                      <span> · Qty: {{ h.product.qty }}</span>
                      <span v-if="h.product.cost_price">
                        ·
                        <span :class="{ 'cost-loss': h.product.sale_price != null && h.product.sale_price < h.product.cost_price }">
                          Cost: {{ h.product.currency || 'USD' }} {{ h.product.cost_price }}
                        </span>
                      </span>
                    </div>
                  </template>
                  <span v-else class="body-row-empty">No matching stock found</span>
                </div>
              </div>
            </div>
            <div class="card-footer">
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
                  <option value="incorrect_match">Incorrect Match</option>
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
              <div v-if="incorrectMatchForms[inq.id]?.open" class="incorrect-match-form">
                <input
                  v-model="incorrectMatchForms[inq.id].reason"
                  placeholder="What's incorrect about this match?"
                  class="incorrect-match-input"
                  @keydown.enter="submitIncorrectMatch(inq)"
                />
                <button class="act-btn close" @click="submitIncorrectMatch(inq)">Save</button>
                <button class="act-btn chat" @click="cancelIncorrectMatch(inq)">Cancel</button>
              </div>
            </div>
          </div>
          <div v-if="sellFeed.length === 0" class="feed-empty">No open selling offers</div>
          <div v-if="sellLoadingMore" class="feed-loading-more">Loading more…</div>
        </div>
      </div>

    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useConversationsStore } from '@/stores/conversations'
import { accountsApi, tradingApi, contactsApi } from '../api/index.js'

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

const accounts          = ref([])
const selectedAccount   = ref('')
const selectedStatus    = ref('open')
const stats             = ref({})
const allProducts       = ref([])
const formattedPriceList = ref('')
const lastUpdate        = ref(null)

// WTB/WTS feeds are paginated independently (each column scrolls on its own) rather than
// a single combined list silently capped at N — the open-feed endpoint returns a real
// `count` so we know when there's more to load as the user scrolls each column.
const buyFeed          = ref([])
const sellFeed         = ref([])
const buyTotal         = ref(0)
const sellTotal        = ref(0)
const buyLimit         = ref(50)
const sellLimit        = ref(50)
const buyLoadingMore   = ref(false)
const sellLoadingMore  = ref(false)
let   pollTimer        = null

// Expand/collapse state for card-body rows (Summary / Original Message / Stock Suggestion).
// Only one row across all cards can be expanded at a time; clicking the row again or
// anywhere outside it collapses it back to its fixed-height, clamped preview.
const expandedBodyRow = ref(null) // { inqId, row } | null

function isRowExpanded(inqId, row) {
  return expandedBodyRow.value?.inqId === inqId && expandedBodyRow.value?.row === row
}

function toggleBodyRow(inqId, row) {
  expandedBodyRow.value = isRowExpanded(inqId, row) ? null : { inqId, row }
}

function collapseBodyRow() {
  expandedBodyRow.value = null
}

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
  { value: 'incorrect_match', label: 'Incorrect Match' },
]

function setStatusFilter(val) {
  selectedStatus.value = val
  buyLimit.value = 50
  sellLimit.value = 50
  refresh()
}

const productMap = computed(() => {
  const m = {}
  for (const p of allProducts.value) m[p.id] = p
  return m
})

// product_id is the agent's own match verdict — null means it deliberately declined to link a
// catalog entry (ambiguous color/region, garbled message, etc). Falling back to a substring
// search over canonical_name here would silently override that "no confident match" decision
// with a weaker frontend guess, and has produced real false positives (e.g. a message the agent
// correctly left unmatched still showing a confident ✓ in-stock suggestion). Trust product_id.
function matchInventory(p) {
  return p.product_id ? productMap.value[p.product_id] : null
}

// A matched inventory record is only trustworthy for pricing/prefill purposes when
// it's actually the SAME product the customer asked for — not just close enough that
// product_id resolved to something. Two independent checks, either one can veto:
//  1. The AI itself flagged this as a near (not exact) match.
//  2. The matched product's own name doesn't equal what was requested — this catches
//     the AI mismarking something "exact" when it demonstrably isn't (e.g. matching
//     "iPhone 17 Pro Max" to a catalog entry actually named "iPhone 17 Pro"), and also
//     protects older inquiries stored before match_type existed.
// Whether product_id was correctly matched is the AI's judgment call to make (that's what
// match_type is for — exact/near/null), not ours to re-derive here. Re-verifying it with
// our own string comparison duplicates a fuzzy-matching problem we already pay the agent
// to solve, with a strictly worse tool (exact-string-equality can't handle aliases, tier
// suffixes, brand formatting, or regional synonyms the way the agent can) — and it already
// produced a false positive the first time a brand prefix showed up. Trust match_type.
// Only "near" is untrustworthy for pricing; missing match_type (older inquiries, predating
// this field) falls back to trusted, same as before this field existed.
function isReliableMatch(p, match) {
  if (!match) return false
  return p.match_type !== 'near'
}

// Product.name in the catalog never includes the brand (brand is a separate field), but
// canonical_name from the AI sometimes does — either bracketed "[Apple] iPhone..." or a
// bare "Apple iPhone..." prefix. Purely cosmetic cleanup for outgoing WhatsApp text.
function stripBrandPrefix(name, brand) {
  let s = (name || '').replace(/^\[[^\]]*\]\s*/, '')
  if (brand) {
    s = s.replace(new RegExp('^' + brand.trim().replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '\\s+', 'i'), '')
  }
  return s.trim()
}

function getInventoryHints(inq) {
  if (inq.inquiry_type !== 'buy') return []
  const hints = []
  for (const p of (inq.products || [])) {
    const match = matchInventory(p)
    // A hint claims "in stock" — never show that for qty 0, even if a sale_price is
    // saved on the record (price can be set ahead of restock without meaning it's available now).
    if (match && match.qty > 0) {
      hints.push({ name: p.canonical_name, product: match, mismatch: !isReliableMatch(p, match) })
    }
  }
  return hints
}

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

function feedParams(type, limit) {
  const accountParam = selectedAccount.value || undefined
  return {
    ...(accountParam ? { account: accountParam } : {}),
    status: selectedStatus.value,
    type,
    limit,
  }
}

async function refresh() {
  const accountParam = selectedAccount.value || undefined
  const params = accountParam ? { account: accountParam } : {}
  const [statsRes, buyRes, sellRes, prodsRes] = await Promise.all([
    tradingApi.getStats(params),
    tradingApi.getOpenFeed(feedParams('buy', buyLimit.value)),
    tradingApi.getOpenFeed(feedParams('sell', sellLimit.value)),
    tradingApi.listProducts({ page_size: 1000, is_active: true }),
  ])
  stats.value       = statsRes.data
  buyFeed.value      = buyRes.data.results
  buyTotal.value     = buyRes.data.count
  sellFeed.value     = sellRes.data.results
  sellTotal.value    = sellRes.data.count
  allProducts.value = prodsRes.data.results ?? prodsRes.data
  lastUpdate.value  = Date.now()
}

// Each column loads its own next page independently on scroll — doesn't touch the other
// column, stats, or products, so scrolling one list stays cheap and doesn't disturb the other.
async function loadMoreBuy() {
  if (buyLoadingMore.value || buyFeed.value.length >= buyTotal.value) return
  buyLoadingMore.value = true
  try {
    buyLimit.value += 50
    const { data } = await tradingApi.getOpenFeed(feedParams('buy', buyLimit.value))
    buyFeed.value  = data.results
    buyTotal.value = data.count
  } finally {
    buyLoadingMore.value = false
  }
}

async function loadMoreSell() {
  if (sellLoadingMore.value || sellFeed.value.length >= sellTotal.value) return
  sellLoadingMore.value = true
  try {
    sellLimit.value += 50
    const { data } = await tradingApi.getOpenFeed(feedParams('sell', sellLimit.value))
    sellFeed.value  = data.results
    sellTotal.value = data.count
  } finally {
    sellLoadingMore.value = false
  }
}

function onBuyScroll(e) {
  const el = e.target
  if (el.scrollTop + el.clientHeight >= el.scrollHeight - 100) loadMoreBuy()
}

function onSellScroll(e) {
  const el = e.target
  if (el.scrollTop + el.clientHeight >= el.scrollHeight - 100) loadMoreSell()
}

async function act(inq, status) {
  await tradingApi.updateInquiry(inq.id, { status })
  await refresh()
}

// ── Quick contact categorization (supplier/customer/both) ────────────────────────

const categoryError = ref('')

const CATEGORY_LABELS = { supplier: 'Supplier', customer: 'Customer', both: 'Both' }
function categoryLabel(val) {
  return CATEGORY_LABELS[val] || val
}

function hasSuggestion(inq) {
  return !!(inq.suggested_contact_category && inq.suggested_contact_category !== inq.contact_category)
}

// Pre-fill the dropdown with the AI's suggestion when one is pending, instead of the
// currently-saved category — the select still only persists on an explicit change/apply.
function categoryDisplayValue(inq) {
  return hasSuggestion(inq) ? inq.suggested_contact_category : (inq.contact_category || '')
}

async function setContactCategory(inq, value) {
  if (!inq.contact) return
  try {
    await contactsApi.update(inq.contact, { category: value })
    inq.contact_category = value
    categoryError.value = ''
  } catch (err) {
    categoryError.value = `Failed to update contact category: ${err.response?.data?.detail || err.message}`
  }
}

// Inline "Incorrect Match" reason form, keyed by inquiry id
const incorrectMatchForms = ref({})

function setStatus(inq, e) {
  const val = e.target.value
  e.target.value = ''
  if (!val) return
  if (val === 'incorrect_match') {
    incorrectMatchForms.value[inq.id] = { open: true, reason: '' }
    return
  }
  act(inq, val)
}

async function submitIncorrectMatch(inq) {
  const form = incorrectMatchForms.value[inq.id]
  if (!form) return
  await tradingApi.updateInquiry(inq.id, { status: 'incorrect_match', remarks: form.reason.trim() })
  form.open = false
  await refresh()
}

function cancelIncorrectMatch(inq) {
  const form = incorrectMatchForms.value[inq.id]
  if (form) form.open = false
}

function waPrefillText(inq) {
  const lines = []
  for (const p of (inq.products || [])) {
    const match = matchInventory(p)
    let line = p.canonical_name || match?.name
    if (!line) continue
    line = stripBrandPrefix(line, match?.brand)
    // Only attach the matched price when it's actually the same product requested —
    // never quote a price that belongs to a different model/color/region than the line says.
    // Also never quote a price for something we have zero units of.
    if (match?.sale_price != null && match.qty > 0 && isReliableMatch(p, match)) line += ` - ${match.sale_price}`
    lines.push(line)
  }
  const offer    = lines.join('\n')
  const original = inq.source_message_text || ''
  if (!offer) return original
  if (!original) return `Please check price below:\n${offer}`
  // Quote the sender's own message back to them, then two blank lines, then our offer —
  // gives them the context of what they asked for before they hit the price.
  return `${original}\n\n\nPlease check price below:\n${offer}`
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

// The AI-formatted price list (Products → Price List → Regenerate) — sent verbatim,
// never built ad hoc here, so it always matches what was actually reviewed/approved there.
function waPriceListLink(inq) {
  const phone = inq.contact_phone
  if (!phone) return null
  const clean = phone.split('@')[0].replace(/\D/g, '')
  if (!clean) return null
  const text = formattedPriceList.value
  if (!text) return null
  const params = new URLSearchParams({ phone: clean, text })
  return `whatsapp://send?${params.toString()}`
}


onMounted(async () => {
  const { data } = await accountsApi.list()
  accounts.value = data
  await refresh()
  // Fetched once, not on every poll — it only changes when someone hits "Regenerate"
  // on the Products page, not on the 15s live-feed cadence.
  tradingApi.getPriceList().then(({ data }) => { formattedPriceList.value = data.body }).catch(() => {})
  pollTimer = setInterval(refresh, 15000)
  document.addEventListener('click', collapseBodyRow)
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
  document.removeEventListener('click', collapseBodyRow)
})
</script>

<style scoped>
.trading-view { display: flex; flex-direction: column; height: 100%; overflow: hidden; background: #f9fafb; }
.trading-header { display: flex; justify-content: space-between; align-items: center; padding: 14px 20px; background: #fff; border-bottom: 1px solid #e5e7eb; }
.error-banner { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 8px 20px; background: #fee2e2; color: #991b1b; font-size: 0.85rem; border-bottom: 1px solid #fca5a5; }
.error-dismiss { background: none; border: none; color: #991b1b; cursor: pointer; font-size: 0.9rem; padding: 0 4px; }
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
.feed-card { background: #fff; border: 1px solid #e5e7eb; border-radius: 8px; padding: 12px; display: flex; flex-direction: column; height: 300px; }
.feed-card.urgent { border-left: 3px solid #f59e0b; }
.card-header { flex-shrink: 0; padding-bottom: 8px; margin-bottom: 8px; border-bottom: 1px solid #f3f4f6; }
.card-body { flex: 1; min-height: 0; display: flex; flex-direction: column; gap: 3px; position: relative; }
.card-footer { flex-shrink: 0; padding-top: 8px; margin-top: 8px; border-top: 1px solid #f3f4f6; }
.card-top { display: flex; align-items: center; gap: 6px; flex-wrap: nowrap; }
.card-contact { font-weight: 600; font-size: 0.88rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; min-width: 0; flex-shrink: 1; }
.card-phone { font-weight: 400; font-size: 0.78rem; color: #6b7280; margin-left: 6px; }
.card-age { font-size: 0.78rem; color: #6b7280; margin-left: auto; flex-shrink: 0; white-space: nowrap; }
.card-age.red { color: #dc2626; font-weight: 700; }
.category-select-mini { padding: 2px 6px; border: 1px solid #d1d5db; border-radius: 5px; font-size: 0.72rem; color: #374151; cursor: pointer; background: #fff; flex-shrink: 0; }
.category-select-suggested { border-color: #fbbf24; background: #fffbeb; color: #92400e; font-weight: 600; }
.category-suggestion-chip { padding: 2px 8px; border: 1px solid #fbbf24; border-radius: 999px; font-size: 0.72rem; color: #92400e; background: #fef9c3; cursor: pointer; font-weight: 600; flex-shrink: 0; }
.category-suggestion-chip:hover { background: #fef08a; }
.body-row { flex: 1; min-height: 0; overflow: hidden; padding: 3px 6px; border-radius: 5px; cursor: pointer; transition: background-color 0.15s; }
.body-row:hover { background: #f9fafb; }
.body-row-label { font-size: 0.62rem; text-transform: uppercase; letter-spacing: 0.04em; color: #9ca3af; font-weight: 700; margin-bottom: 1px; }
.body-row-content { font-size: 0.8rem; color: #374151; line-height: 1.35; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.body-row-empty { color: #9ca3af; font-style: italic; }
.body-row.expanded {
  position: absolute; inset: 0; z-index: 30;
  background: #fff; border: 1px solid #d1d5db; border-radius: 6px;
  box-shadow: 0 8px 20px rgba(0, 0, 0, 0.18);
  padding: 8px; overflow-y: auto; cursor: default;
}
.body-row.expanded .body-row-content { -webkit-line-clamp: unset; display: block; overflow: visible; }
.source-label { font-size: 0.73rem; color: #9ca3af; text-transform: capitalize; white-space: nowrap; flex-shrink: 0; }
.account-badge { font-size: 0.7rem; background: #ede9fe; color: #6d28d9; padding: 1px 7px; border-radius: 999px; font-weight: 600; white-space: nowrap; flex-shrink: 0; }
.card-actions { display: flex; gap: 6px; align-items: center; }
.act-btn { padding: 4px 12px; border: none; border-radius: 5px; cursor: pointer; font-size: 0.8rem; font-weight: 500; }
.act-btn.close { background: #f3f4f6; color: #374151; }
.act-btn.deal  { background: #16a34a; color: #fff; }
.act-btn.chat  { background: #eff6ff; color: #1d4ed8; margin-left: auto; }
.act-btn.wa    { background: #dcfce7; color: #16a34a; display: flex; align-items: center; gap: 3px; text-decoration: none; }
.act-btn.wa-ask { background: #fef9c3; color: #92400e; text-decoration: none; }
.act-btn.wa-list { background: #e0e7ff; color: #4338ca; text-decoration: none; }
.status-select-mini { padding: 4px 8px; border: 1px solid #d1d5db; border-radius: 5px; font-size: 0.78rem; color: #374151; cursor: pointer; background: #fff; }
.incorrect-match-form { display: flex; gap: 6px; align-items: center; margin-top: 6px; }
.incorrect-match-input { flex: 1; padding: 4px 8px; border: 1px solid #fca5a5; border-radius: 5px; font-size: 0.78rem; min-width: 0; }
.feed-empty { text-align: center; color: #9ca3af; font-size: 0.85rem; padding: 30px; }
.feed-loading-more { text-align: center; color: #9ca3af; font-size: 0.78rem; padding: 8px; }
.btn-ghost { padding: 6px 14px; border: 1px solid #d1d5db; border-radius: 6px; background: transparent; cursor: pointer; font-size: 0.85rem; }
.btn-ghost.sm { padding: 4px 10px; font-size: 0.8rem; }
/* Inventory stock hints on WTB cards */
.card-stock-hints { display: flex; flex-direction: column; gap: 3px; margin-bottom: 6px; }
.stock-hint { background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 5px; padding: 4px 8px; font-size: 0.75rem; color: #166534; line-height: 1.4; }
.stock-hint-mismatch { background: #fef9c3; border-color: #fde68a; color: #92400e; }
.mismatch-tag { font-weight: 700; }
.cost-loss { color: #dc2626; font-weight: 700; }
.stock-icon { color: #16a34a; font-weight: 700; margin-right: 3px; }
.stock-hint-mismatch .stock-icon { color: #d97706; }
</style>
