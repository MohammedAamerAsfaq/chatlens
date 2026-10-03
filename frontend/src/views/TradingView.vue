<template>
  <div class="trading-view" v-bind="$attrs">
    <Teleport v-if="auth.uiTheme === 'inspinia'" to="#inspinia-page-context">
      <div class="trading-live-status">
        <span class="live-dot"></span>
        <span class="live-label">Live</span>
        <span class="last-update">Updated {{ lastUpdateLabel }}</span>
      </div>
    </Teleport>
    <!-- Header -->
    <div class="trading-header">
      <div v-if="auth.uiTheme !== 'inspinia'" class="header-left">
        <span class="live-dot"></span>
        <span class="live-label">Live</span>
        <span class="last-update">Updated {{ lastUpdateLabel }}</span>
      </div>
      <TradingOverview :stats="stats" />
      <div class="header-right">
        <label class="toolbar-control">
          <FontAwesomeIcon :icon="faFilter" title="Inquiry status" aria-label="Inquiry status" />
          <select :value="selectedStatus" class="account-select status-filter-select" @change="setStatusFilter($event.target.value)">
            <option v-for="filter in statusFilters" :key="filter.value" :value="filter.value">{{ filter.label }}</option>
          </select>
        </label>
        <TradingToolbarSettings
          v-model:selected-account="selectedAccount"
          v-model:close-stale-hours="closeStaleHours"
          v-model:slide-direction="cardAnimation.slide_direction"
          :accounts="accounts"
          :close-stale-running="closeStaleRunning"
          @change-account="resetFeedPagesAndRefresh"
          @change-animation="saveCardAnimation"
          @close-stale="runCloseStale"
        />
        <button class="toolbar-icon-button" title="Refresh dashboard" aria-label="Refresh dashboard" @click="refresh">
          <FontAwesomeIcon :icon="faRotateRight" />
        </button>
      </div>
    </div>

    <!-- Close-stale result banner -->
    <div v-if="closeStaleMsg" class="close-stale-msg">{{ closeStaleMsg }}</div>

    <!-- Error banner -->
    <div v-if="categoryError" class="error-banner">
      {{ categoryError }}
      <button class="error-dismiss" @click="categoryError = ''">✕</button>
    </div>

    <!-- Live feed + analytics -->
    <div class="main-grid">
      <!-- WTB feed -->
      <div class="feed-col">
        <div class="feed-header wtb-header">
          <div class="feed-heading">
            <span class="feed-title">WTB<sup class="feed-count">{{ buyTotal }}</sup></span>
          </div>
          <TradingFeedControls
            v-model:contact-search="buyContactSearch"
            v-model:date-range="buyDateRange"
            v-model:sort="buySort"
            v-model:page-size="buyPageSize"
            :selected-contact="buyContact"
            :contact-open="buyContactOpen"
            :contact-loading="buyContactLoading"
            :contact-options="buyContactOptions"
            :date-options="feedDateOptions"
            :page-size-options="feedPageSizeOptions"
            @open-contact="openContactPicker('buy')"
            @search-contact="searchContacts('buy')"
            @clear-contact="clearFeedContact('buy')"
            @select-contact="selectFeedContact('buy', $event)"
            @contact-scroll="onContactMenuScroll('buy', $event)"
            @change-date="setFeedDateRange('buy')"
            @change-sort="setFeedSort('buy')"
            @change-page-size="setFeedPageSize('buy')"
          />
        </div>
        <div class="feed-list">
          <div
            v-for="inq in buyFeed" :key="inq.id"
            class="feed-card"
            :class="{ urgent: inq.age_seconds < 60, 'sliding-left': slidingCards[inq.id] === 'left', 'sliding-right': slidingCards[inq.id] === 'right' }"
          >
            <InquiryCardHeader
              :inquiry="inq"
              :category-value="categoryDisplayValue(inq)"
              :suggestion-available="hasSuggestion(inq)"
              :fresh="isFreshInquiry(inq)"
              @set-category="setContactCategory(inq, $event)"
              @apply-suggestion="applySuggestedCategory(inq)"
              @set-status="setStatus(inq, $event)"
              @close="act(inq, 'closed')"
            />
            <InquiryCardBody
              :inquiry="inq"
              :hints="inventoryHintRows(inq)"
              :expanded-row="expandedBodyRow?.inqId === inq.id ? expandedBodyRow.row : ''"
              :matching-pending="isProductMatchingPending(inq)"
              @toggle-row="toggleBodyRow(inq.id, $event)"
              @verify="verifyStockMatch(inq, $event)"
              @create-inquiry="createInquiryFromStockHint(inq, $event)"
              @auto-match="runAutoMatch(inq, $event)"
              @fix-match="toggleMatchFix(inq, $event)"
            />
            <div class="card-footer">
              <InquiryCardActions
                :inquiry="inq"
                :manual-match-available="hasManualMatchTargets(inq)"
                :wa-link="waLink(inq)"
                :ask-price-link="waAskPriceLink(inq)"
                :price-list-link="waPriceListLink(inq)"
                price-list-enabled
                :formatted-price-list-available="Boolean(formattedPriceList)"
                @inquiry-products="openInquiryProducts(inq)"
                @manual-match="openManualMatch(inq)"
                @market-parties="openMarketParties(inq)"
                @wa-chatlens="openChatLensWa(inq)"
                @wa-direct-chatlens="openDirectChatLensWa(inq)"
                @chat-reference="openChatReference(inq)"
                @ask-price-chatlens="openAskPriceChatLens(inq)"
                @ask-price-direct-chatlens="openDirectAskPriceChatLens(inq)"
                @price-list-chatlens="openPriceListChatLens(inq)"
                @price-list-direct-chatlens="openDirectPriceListChatLens(inq)"
              />
              <InquiryCardReview
                :rating="inq.classification_rating ?? 5"
                :incorrect-open="Boolean(incorrectMatchForms[inq.id]?.open)"
                :incorrect-reason="incorrectMatchForms[inq.id]?.reason || ''"
                @rate="setRating(inq, $event)"
                @update:incorrect-reason="incorrectMatchForms[inq.id].reason = $event"
                @submit="submitIncorrectMatch(inq)"
                @cancel="cancelIncorrectMatch(inq)"
              />
            </div>
          </div>
          <div v-if="buyFeed.length === 0" class="feed-empty">No open buying inquiries</div>
        </div>
        <TradingFeedPager :page="buyPage" :total-pages="buyTotalPages" :loading="buyLoading" @change="changeFeedPage('buy', $event)" />
      </div>

      <!-- WTS feed -->
      <div class="feed-col">
        <div class="feed-header wts-header">
          <div class="feed-heading">
            <span class="feed-title">WTS<sup class="feed-count">{{ sellTotal }}</sup></span>
          </div>
          <TradingFeedControls
            v-model:contact-search="sellContactSearch"
            v-model:date-range="sellDateRange"
            v-model:sort="sellSort"
            v-model:page-size="sellPageSize"
            :selected-contact="sellContact"
            :contact-open="sellContactOpen"
            :contact-loading="sellContactLoading"
            :contact-options="sellContactOptions"
            :date-options="feedDateOptions"
            :page-size-options="feedPageSizeOptions"
            @open-contact="openContactPicker('sell')"
            @search-contact="searchContacts('sell')"
            @clear-contact="clearFeedContact('sell')"
            @select-contact="selectFeedContact('sell', $event)"
            @contact-scroll="onContactMenuScroll('sell', $event)"
            @change-date="setFeedDateRange('sell')"
            @change-sort="setFeedSort('sell')"
            @change-page-size="setFeedPageSize('sell')"
          />
        </div>
        <div class="feed-list">
          <div
            v-for="inq in sellFeed" :key="inq.id"
            class="feed-card"
            :class="{ urgent: inq.age_seconds < 60, 'sliding-left': slidingCards[inq.id] === 'left', 'sliding-right': slidingCards[inq.id] === 'right' }"
          >
            <InquiryCardHeader
              :inquiry="inq"
              :category-value="categoryDisplayValue(inq)"
              :suggestion-available="hasSuggestion(inq)"
              :fresh="isFreshInquiry(inq)"
              @set-category="setContactCategory(inq, $event)"
              @apply-suggestion="applySuggestedCategory(inq)"
              @set-status="setStatus(inq, $event)"
              @close="act(inq, 'closed')"
            />
            <InquiryCardBody
              :inquiry="inq"
              :hints="inventoryHintRows(inq)"
              :expanded-row="expandedBodyRow?.inqId === inq.id ? expandedBodyRow.row : ''"
              :matching-pending="isProductMatchingPending(inq)"
              @toggle-row="toggleBodyRow(inq.id, $event)"
              @verify="verifyStockMatch(inq, $event)"
              @create-inquiry="createInquiryFromStockHint(inq, $event)"
              @auto-match="runAutoMatch(inq, $event)"
              @fix-match="toggleMatchFix(inq, $event)"
            />
            <div class="card-footer">
              <InquiryCardActions
                :inquiry="inq"
                :manual-match-available="hasManualMatchTargets(inq)"
                :wa-link="waLink(inq)"
                :ask-price-link="waAskPriceLink(inq)"
                @inquiry-products="openInquiryProducts(inq)"
                @manual-match="openManualMatch(inq)"
                @market-parties="openMarketParties(inq)"
                @wa-chatlens="openChatLensWa(inq)"
                @wa-direct-chatlens="openDirectChatLensWa(inq)"
                @chat-reference="openChatReference(inq)"
                @ask-price-chatlens="openAskPriceChatLens(inq)"
                @ask-price-direct-chatlens="openDirectAskPriceChatLens(inq)"
              />
              <InquiryCardReview
                :rating="inq.classification_rating ?? 5"
                :incorrect-open="Boolean(incorrectMatchForms[inq.id]?.open)"
                :incorrect-reason="incorrectMatchForms[inq.id]?.reason || ''"
                @rate="setRating(inq, $event)"
                @update:incorrect-reason="incorrectMatchForms[inq.id].reason = $event"
                @submit="submitIncorrectMatch(inq)"
                @cancel="cancelIncorrectMatch(inq)"
              />
            </div>
          </div>
          <div v-if="sellFeed.length === 0" class="feed-empty">No open selling offers</div>
        </div>
        <TradingFeedPager :page="sellPage" :total-pages="sellTotalPages" :loading="sellLoading" @change="changeFeedPage('sell', $event)" />
      </div>

    </div>
  </div>

  <MatchFixDialog
    :target="matchFixTarget"
    :active-line="activeMatchFixLine"
    :drag="matchFixDrag"
    :loading="autoSearchLoading"
    :error="autoSearchError"
    :results="autoSearchResults"
    :query="matchFixQuery"
    :products="filteredMatchProducts"
    @close="closeMatchFix"
    @start-drag="startMatchFixDrag"
    @select-line="selectMatchFixLine"
    @select-product="selectMatchFix"
    @update:query="matchFixQuery = $event"
    @search="runManualEmbeddingSearch"
  />

  <ExpandedInquiryDialog
    :inquiry="expandedInquiry"
    :row="expandedBodyRow?.row || ''"
    :title="expandedBodyRow ? rowLabel(expandedBodyRow.row) : ''"
    :drag="rowDialogDrag"
    :hints="expandedInquiry ? inventoryHintRows(expandedInquiry) : []"
    @close="collapseBodyRow"
    @start-drag="startRowDialogDrag"
    @verify="verifyStockMatch(expandedInquiry, $event)"
    @create-inquiry="createInquiryFromStockHint(expandedInquiry, $event)"
    @auto-match="runAutoMatch(expandedInquiry, $event)"
    @fix-match="toggleMatchFix(expandedInquiry, $event)"
  />

  <TradingConversationDialog
    :open="chatLensWaOpen"
    :title="chatLensWaTitle"
    :inquiry="chatLensWaInquiry"
    :loading="chatLensWaLoading"
    :error="chatLensWaError"
    :draft="chatLensWaDraft"
    @close="closeChatLensWa"
  />

  <InquiryProductsDialog
    :open="productModalOpen"
    :inquiry="productModalInquiry"
    :loading="productLinesLoading"
    :error="productLinesError"
    :lines="productLines"
    :creating-index="creatingLineIndex"
    :tracking-index="trackingLineIndex"
    @close="closeInquiryProducts"
    @create-product="createProductFromLine"
    @track-non-inventory="trackNonInventoryFromLine"
  />

  <MarketPartiesDialog
    :open="marketModalOpen"
    :title="marketModalTitle"
    :inquiry="marketModalInquiry"
    :products="marketProducts"
    :loading="marketLoading"
    :error="marketError"
    :source="marketSource"
    :method="marketMethod"
    :drag="marketDialogDrag"
    @close="closeMarketParties"
    @start-drag="startMarketDialogDrag"
    @set-source="setMarketSource"
    @set-method="setMarketMethod"
    @view-chat="viewChat($event.source_chat_id, $event.account_id, $event.source_message_id, $event.source_message_time)"
  />
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { FontAwesomeIcon } from '@fortawesome/vue-fontawesome'
import { faFilter, faRotateRight } from '@fortawesome/free-solid-svg-icons'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useConversationsStore } from '@/stores/conversations'
import { useDraggableDialog } from '@/features/trading/composables/useDraggableDialog'
import { useTradingContactPicker } from '@/features/trading/composables/useTradingContactPicker'
import { useTradingConversationDialog } from '@/features/trading/composables/useTradingConversationDialog'
import { useInquiryMatchController } from '@/features/trading/composables/useInquiryMatchController'
import { useInquiryProductsController } from '@/features/trading/composables/useInquiryProductsController'
import { useMarketPartiesController } from '@/features/trading/composables/useMarketPartiesController'
import {
  feedDateOptions,
  feedPageSizeOptions,
  useTradingFeedController,
} from '@/features/trading/composables/useTradingFeedController'
import {
  InquiryCardActions,
  InquiryCardBody,
  InquiryCardHeader,
  InquiryCardReview,
  InquiryProductsDialog,
  InquiryStockHints,
  ExpandedInquiryDialog,
  MatchFixDialog,
  MarketPartiesDialog,
  TradingConversationDialog,
  TradingFeedControls,
  TradingFeedPager,
  TradingOverview,
  TradingToolbarSettings,
} from '@/features/trading'
import { accountsApi, tradingApi, contactsApi } from '../api/index.js'

// The teleported "Fix match" dialog below makes this component multi-root, which breaks
// Vue's automatic $attrs inheritance onto a single root (see the same fix on StorageView.vue) —
// bind explicitly onto the real root div instead.
defineOptions({ inheritAttrs: false })

const router = useRouter()
const auth = useAuthStore()
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
const formattedPriceList = ref('')
// Hot-settable WhatsApp price-reply composition (§ AI Instructions > Trading
// dashboard) — same defaults the backend falls back to.
const wtsReply          = ref({
  heading: 'WTS',
  send_flag: true, flag_position: 'prefix',
  send_color: true, color_position: 'prefix',
  send_currency: true, currency_position: 'prefix', currency: 'AED',
  send_secondary_currency: false, secondary_currency: 'USD', secondary_currency_rate: 0.27,
  sort_by: 'original',
  heading_blank_lines: 0,
})

// Card slide-out animation played on an inquiry card when its status is changed —
// direction is a hot-settable board preference (left/right/none), same
// load-on-mount pattern as wtsReply above. slidingCards maps inquiry id -> the
// direction currently animating, read by the card's :class binding; the actual
// status-changing API call is deliberately delayed by CARD_SLIDE_MS so the user
// sees the slide before the list refresh potentially removes/updates the card.
const CARD_SLIDE_MS = 320
const cardAnimation = ref({ slide_direction: 'left' })
const slidingCards = reactive({})

function slideThenRun(inq, run) {
  const direction = cardAnimation.value.slide_direction
  if (direction === 'none') return run()
  slidingCards[inq.id] = direction
  return new Promise(resolve => {
    setTimeout(async () => {
      try {
        await run()
      } finally {
        delete slidingCards[inq.id]
        resolve()
      }
    }, CARD_SLIDE_MS)
  })
}

async function saveCardAnimation() {
  try {
    const { data } = await tradingApi.setCardAnimationSettings(cardAnimation.value)
    Object.assign(cardAnimation.value, data)
  } catch {
    // non-critical — the select just keeps its local value if the save fails
  }
}

// WTB/WTS feeds are paginated independently (each column scrolls on its own) rather than
// a single combined list silently capped at N — the open-feed endpoint returns a real
// `count` so we know when there's more to load as the user scrolls each column.
let   pollTimer        = null

const contactPickers = useTradingContactPicker({
  accountId: selectedAccount,
  listContacts: contactsApi.list,
  onSelectionChange: type => feedController.reloadFromFirstPage(type),
})
const {
  selected: buyContact,
  search: buyContactSearch,
  open: buyContactOpen,
  loading: buyContactLoading,
  options: buyContactOptions,
} = contactPickers.buy
const {
  selected: sellContact,
  search: sellContactSearch,
  open: sellContactOpen,
  loading: sellContactLoading,
  options: sellContactOptions,
} = contactPickers.sell
const loadContactOptions = contactPickers.load
const openContactPicker = contactPickers.open
const searchContacts = contactPickers.search
const onContactMenuScroll = contactPickers.loadNext
const selectFeedContact = contactPickers.select
const clearFeedContact = contactPickers.clear
const closeContactPickersOnOutsideClick = contactPickers.closeOnOutsideClick

const feedController = useTradingFeedController({
  api: tradingApi,
  accountId: selectedAccount,
  status: selectedStatus,
  contacts: { buy: buyContact, sell: sellContact },
  resetContact: type => contactPickers.clear(type, { notify: false, reload: true }),
})
const { stats, products: allProducts, lastUpdate, refresh } = feedController
const {
  items: buyFeed, total: buyTotal, page: buyPage, pageSize: buyPageSize,
  sort: buySort, dateRange: buyDateRange, loading: buyLoading, totalPages: buyTotalPages,
} = feedController.buy
const {
  items: sellFeed, total: sellTotal, page: sellPage, pageSize: sellPageSize,
  sort: sellSort, dateRange: sellDateRange, loading: sellLoading, totalPages: sellTotalPages,
} = feedController.sell
const loadBuyFeed = () => feedController.load('buy')
const loadSellFeed = () => feedController.load('sell')
const setFeedSort = type => feedController.reloadFromFirstPage(type)
const setFeedPageSize = type => feedController.reloadFromFirstPage(type)
const setFeedDateRange = type => feedController.setDateRange(type)
const changeFeedPage = (type, page) => feedController.changePage(type, page)

// Ticks once a second so `isFreshInquiry` re-evaluates and the Close button
// re-enables itself without needing a manual refresh.
const nowTick = ref(Date.now())
let   freshnessTimer = null
const CLOSE_GUARD_MS = 5000

function isFreshInquiry(inq) {
  if (!inq.created_at) return false
  return nowTick.value - new Date(inq.created_at).getTime() < CLOSE_GUARD_MS
}

// Expand/collapse state for card-body rows (Summary / Original Message / Stock Suggestion).
// Only one row across all cards can be expanded at a time; clicking the row again or
// anywhere outside it collapses it back to its fixed-height, clamped preview.
const expandedBodyRow = ref(null) // { inqId, row } | null

function isRowExpanded(inqId, row) {
  return expandedBodyRow.value?.inqId === inqId && expandedBodyRow.value?.row === row
}

function toggleBodyRow(inqId, row) {
  const willOpen = !isRowExpanded(inqId, row)
  expandedBodyRow.value = willOpen ? { inqId, row } : null
  // Always reopen centered — a drag offset from a previous popup shouldn't carry over.
  if (willOpen) resetRowDialogDrag()
}

function collapseBodyRow() {
  expandedBodyRow.value = null
}

// Dragging for the row-expand popup below — tracked as a cumulative translate offset
// from its default centered position, rather than absolute viewport coordinates, so it
// doesn't need a getBoundingClientRect measurement to initialize.
const {
  position: rowDialogDrag,
  reset: resetRowDialogDrag,
  start: startRowDialogDrag,
  stop: stopRowDialogDrag,
} = useDraggableDialog()

// Looked up by id (not stored directly on expandedBodyRow) so the popup keeps reading
// the same live inquiry object the feed already has — edits made from inside it (e.g.
// a "Fix match" correction) show up immediately without a separate sync step.
const expandedInquiry = computed(() => {
  if (!expandedBodyRow.value) return null
  const id = expandedBodyRow.value.inqId
  return buyFeed.value.find(i => i.id === id) || sellFeed.value.find(i => i.id === id) || null
})

const ROW_LABELS = { summary: 'Summary', message: 'Original Message', stock: 'Stock Suggestion' }
function rowLabel(row) {
  return ROW_LABELS[row] || row
}

// "Fix match" dialog on a mismatch ("closest match only") stock-suggestion pill — lets a
// human pick the actually-correct catalog product when the AI's near-match was wrong,
// which promotes that line to match_type 'exact' server-side (the pill then renders green
// on its own, same as any other confirmed exact match — no separate "confirmed" styling
// needed).
const matchController = useInquiryMatchController({
  api: tradingApi,
  products: allProducts,
  buildLines: manualMatchLines,
})
const {
  target: matchFixTarget,
  query: matchFixQuery,
  results: autoSearchResults,
  loading: autoSearchLoading,
  error: autoSearchError,
  activeLine: activeMatchFixLine,
  filteredProducts: filteredMatchProducts,
  drag: matchFixDrag,
  startDrag: startMatchFixDrag,
  stopDrag: stopMatchFixDrag,
  openHint: openMatchFix,
  openManual: openManualMatch,
  toggle: toggleMatchFix,
  selectLine: selectMatchFixLine,
  close: closeMatchFix,
  autoMatch: runAutoMatch,
  search: runManualEmbeddingSearch,
  selectProduct: selectMatchFix,
} = matchController

// Auto-search results (from the "Auto" button below) — null means no auto-search has
// run yet for the currently-open dialog; [] means one ran and found nothing.
const matchVerifications = ref({})
const stockInquiryCreates = ref({})
const productDialog = useInquiryProductsController({
  api: tradingApi,
  products: allProducts,
  patchInquiry: updatedInquiry => patchInquiryInFeeds(updatedInquiry),
})
const {
  open: productModalOpen,
  inquiry: productModalInquiry,
  lines: productLines,
  loading: productLinesLoading,
  error: productLinesError,
  creatingIndex: creatingLineIndex,
  trackingIndex: trackingLineIndex,
  show: openInquiryProducts,
  close: closeInquiryProducts,
  createProduct: createProductFromLine,
  trackNonInventory: trackNonInventoryFromLine,
} = productDialog
const conversationDialog = useTradingConversationDialog(convStore)
const {
  open: chatLensWaOpen,
  loading: chatLensWaLoading,
  error: chatLensWaError,
  draft: chatLensWaDraft,
  inquiry: chatLensWaInquiry,
  title: chatLensWaTitle,
  close: closeChatLensWa,
} = conversationDialog
const marketDialog = useMarketPartiesController(tradingApi)
const {
  open: marketModalOpen,
  inquiry: marketModalInquiry,
  products: marketProducts,
  loading: marketLoading,
  error: marketError,
  source: marketSource,
  method: marketMethod,
  title: marketModalTitle,
  drag: marketDialogDrag,
  startDrag: startMarketDialogDrag,
  stopDrag: stopMarketDialogDrag,
  show: openMarketParties,
  close: closeMarketParties,
  setSource: setMarketSource,
  setMethod: setMarketMethod,
} = marketDialog

function matchVerificationKey(inq, hint) {
  return `${inq?.id || 'unknown'}:${hint?.index ?? 'unknown'}`
}

function matchVerificationFor(inq, hint) {
  return matchVerifications.value[matchVerificationKey(inq, hint)] || null
}

function stockInquiryCreateKey(inq, hint) {
  return `${inq?.id || 'unknown'}:${hint?.index ?? 'unknown'}:${hint?.product?.id || 'unknown'}`
}

function stockInquiryCreateFor(inq, hint) {
  return stockInquiryCreates.value[stockInquiryCreateKey(inq, hint)] || null
}

function stockInquiryCreateLabel(inq, hint) {
  const state = stockInquiryCreateFor(inq, hint)
  if (state?.loading) return 'Saving'
  if (state?.saved) return 'Saved'
  return 'Create Inquiry'
}

function manualMatchLines(inq) {
  return (inq?.products || []).map((product, index) => {
    const match = matchInventory(product)
    const name = product?.canonical_name || product?.raw_text || match?.name || `Product ${index + 1}`
    return {
      index,
      name,
      mismatch: !!(match && !isReliableMatch(product, match)),
      unmatched: !product?.product_id,
    }
  })
}

function hasManualMatchTargets(inq) {
  return manualMatchLines(inq).length > 0
}

function matchVerificationLabel(result) {
  if (!result) return ''
  if (result.loading) return 'Checking match'
  if (result.error) return 'Verification failed'
  const labels = {
    exact: 'AI says exact match',
    near: 'AI says near match',
    incorrect: 'AI says incorrect match',
    unknown: 'AI could not verify',
  }
  return labels[result.verdict] || 'AI could not verify'
}

function openChatLensWa(inq) {
  return conversationDialog.openSource(inq, {
    title: 'WA ChatLens',
    draft: waPrefillText(inq),
  })
}

function openDirectChatLensWa(inq) {
  return conversationDialog.openDirect(inq, {
    title: 'WA ChatLens - Direct Message',
    draft: waPrefillText(inq),
  })
}

function openChatReference(inq) {
  return conversationDialog.openSource(inq, {
    title: 'Chat Reference',
    draft: '',
  })
}

function openAskPriceChatLens(inq) {
  return conversationDialog.openSource(inq, {
    title: 'Ask Price - ChatLens',
    draft: waAskPriceText(inq),
  })
}

function openDirectAskPriceChatLens(inq) {
  return conversationDialog.openDirect(inq, {
    title: 'Ask Price - Direct Message',
    draft: waAskPriceText(inq),
  })
}

function openPriceListChatLens(inq) {
  return conversationDialog.openSource(inq, {
    title: 'Price List - ChatLens',
    draft: formattedPriceList.value,
  })
}

function openDirectPriceListChatLens(inq) {
  return conversationDialog.openDirect(inq, {
    title: 'Price List - Direct Message',
    draft: formattedPriceList.value,
  })
}

function patchInquiryInFeeds(updatedInquiry) {
  if (!updatedInquiry?.id) return
  const patch = (list) => {
    const idx = list.findIndex(i => i.id === updatedInquiry.id)
    if (idx >= 0) list[idx] = { ...list[idx], ...updatedInquiry }
  }
  patch(buyFeed.value)
  patch(sellFeed.value)
}

async function createInquiryFromStockHint(inq, hint) {
  if (!inq || hint?.index == null) return
  const key = stockInquiryCreateKey(inq, hint)
  stockInquiryCreates.value = {
    ...stockInquiryCreates.value,
    [key]: { loading: true, saved: false, error: '' },
  }
  try {
    const { data } = await tradingApi.createInquiryProductFromLine(inq.id, hint.index)
    if (data.inquiry) {
      patchInquiryInFeeds(data.inquiry)
    }
    stockInquiryCreates.value = {
      ...stockInquiryCreates.value,
      [key]: { loading: false, saved: true, error: '' },
    }
  } catch (e) {
    stockInquiryCreates.value = {
      ...stockInquiryCreates.value,
      [key]: {
        loading: false,
        saved: false,
        error: e.response?.data?.detail || e.message || 'Failed to save inquiry product',
      },
    }
  }
}

async function verifyStockMatch(inq, hint) {
  const key = matchVerificationKey(inq, hint)
  matchVerifications.value = {
    ...matchVerifications.value,
    [key]: { loading: true, verdict: 'unknown', reason: '' },
  }
  try {
    const { data } = await tradingApi.verifyMatch(inq.id, { index: hint.index })
    matchVerifications.value = {
      ...matchVerifications.value,
      [key]: {
        loading: false,
        verdict: data.verdict || 'unknown',
        reason: data.reason || '',
        detected_differences: data.detected_differences || [],
        recommended_action: data.recommended_action || 'manual_review',
        is_acceptable: !!data.is_acceptable,
      },
    }
  } catch (e) {
    matchVerifications.value = {
      ...matchVerifications.value,
      [key]: {
        loading: false,
        verdict: 'unknown',
        error: e.response?.data?.detail || e.message || 'Verification failed',
      },
    }
  }
}

const statusFilters = [
  { value: 'all',            label: 'All Today' },
  { value: 'open',           label: 'Open' },
  { value: 'requested_price', label: 'Requested Price' },
  { value: 'quoted_waiting', label: 'Quoted - Waiting' },
  { value: 'no_response',    label: 'No Response' },
  { value: 'price_high',     label: 'Price High' },
  { value: 'no_stock',       label: 'No Stock' },
  { value: 'currently_in_stock', label: 'Currently In Stock' },
  { value: 'not_dealing',    label: 'Not Dealing' },
  { value: 'irrelevant',     label: 'Irrelevant' },
  { value: 'closed',         label: 'Closed' },
  { value: 'deal_done',      label: 'Deal Done' },
  { value: 'tracking',       label: 'Tracking' },
  { value: 'incorrect_match', label: 'Incorrect Match' },
]

function setStatusFilter(val) {
  selectedStatus.value = val
  buyPage.value = 1
  sellPage.value = 1
  buyContact.value = ''
  sellContact.value = ''
  buyContactSearch.value = ''
  sellContactSearch.value = ''
  loadContactOptions('buy', { reset: true })
  loadContactOptions('sell', { reset: true })
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

// Looks up a hot-added key/value attribute (§ ProductAttribute) on the matched catalog
// row — used to prefix outgoing reply text with the region flag/color when set.
function attributeValue(match, key) {
  return match?.attributes?.find(a => a.key === key)?.value || ''
}

// Maps a Color attribute value to the closest standard colored-circle emoji. Only
// the 9 solid circles Unicode actually defines (🔴🟠🟡🟢🔵🟣🟤⚫⚪) — no dedicated
// pink/gray circle exists, so those map to the nearest hue rather than guessing
// with an unrelated symbol. Unrecognized color names get no emoji at all (silent
// gap, not a wrong-colored guess).
const COLOR_EMOJI = {
  red: '🔴', pink: '🔴', rose: '🔴', magenta: '🔴',
  orange: '🟠',
  yellow: '🟡', gold: '🟡', citrus: '🟡',
  green: '🟢', mint: '🟢',
  blue: '🔵', sky: '🔵', navy: '🔵',
  purple: '🟣', violet: '🟣', indigo: '🟣', lavender: '🟣',
  brown: '🟤', bronze: '🟤', copper: '🟤', 'rose gold': '🟤',
  black: '⚫', graphite: '⚫', midnight: '⚫', 'space gray': '⚫', 'space grey': '⚫',
  white: '⚪', silver: '⚪', starlight: '⚪', pearl: '⚪', ivory: '⚪', grey: '⚪', gray: '⚪',
}

function colorEmoji(colorName) {
  if (!colorName) return ''
  return COLOR_EMOJI[colorName.trim().toLowerCase()] || ''
}

function getInventoryHints(inq) {
  const hints = []
  ;(inq.products || []).forEach((p, index) => {
    const match = matchInventory(p)
    if (match) {
      hints.push({ name: p.canonical_name, product: match, mismatch: !isReliableMatch(p, match), index })
    }
  })
  return hints
}

function isProductInStock(product) {
  return Number(product?.qty || 0) > 0
}

function stockHintClass(hint) {
  return {
    'stock-hint-mismatch': hint?.mismatch,
    'stock-hint-out': !isProductInStock(hint?.product),
  }
}

function stockHintIcon(hint) {
  if (hint?.mismatch) return '⚠'
  return isProductInStock(hint?.product) ? '✓' : '!'
}

function stockHintAvailabilityLabel(hint) {
  return isProductInStock(hint?.product) ? 'in stock' : 'matched, not in stock'
}

function inventoryHintRows(inq) {
  return getInventoryHints(inq).map(hint => {
    const verification = matchVerificationFor(inq, hint)
    return {
      ...hint,
      presentationClass: stockHintClass(hint),
      icon: stockHintIcon(hint),
      availabilityLabel: stockHintAvailabilityLabel(hint),
      verification,
      verificationLabel: verification ? matchVerificationLabel(verification) : '',
      createState: stockInquiryCreateFor(inq, hint),
      createLabel: stockInquiryCreateLabel(inq, hint),
    }
  })
}

function isProductMatchingPending(inq) {
  return inq?.classification_version === 'v2' && inq?.product_match_status === 'pending'
}

const lastUpdateLabel = computed(() => {
  if (!lastUpdate.value) return '—'
  const secs = Math.floor((Date.now() - lastUpdate.value) / 1000)
  if (secs < 10) return 'just now'
  return `${secs}s ago`
})


function closeCardMenusOnOutsideClick(event) {
  const menuSelector = '.action-menu'
  const activeMenu = event.target.closest?.(menuSelector)
  const openMenuSelector = '.action-menu[open]'
  document.querySelectorAll(openMenuSelector).forEach(menu => {
    if (menu !== activeMenu) menu.removeAttribute('open')
  })
}

// Housekeeping sweep — closes every still-open inquiry older than N hours (optionally
// scoped to the selected account). Never touches anything already actioned (quoted,
// no_stock, closed, etc.), only status=open.
const closeStaleHours   = ref(1)
const closeStaleRunning = ref(false)
const closeStaleMsg     = ref('')

async function runCloseStale() {
  const hours = closeStaleHours.value
  if (!hours || hours <= 0) return
  if (!confirm(`Close all open inquiries older than ${hours} hour(s)?`)) return

  closeStaleRunning.value = true
  closeStaleMsg.value = ''
  try {
    const accountParam = selectedAccount.value || undefined
    const { data } = await tradingApi.closeStaleInquiries({
      hours,
      ...(accountParam ? { account: accountParam } : {}),
    })
    closeStaleMsg.value = `Closed ${data.closed} inquiry${data.closed === 1 ? '' : 's'}`
    setTimeout(() => { closeStaleMsg.value = '' }, 8000)
    await refresh()
  } catch (e) {
    closeStaleMsg.value = 'Failed: ' + (e.response?.data?.detail || e.message)
  } finally {
    closeStaleRunning.value = false
  }
}

function resetFeedPagesAndRefresh() {
  feedController.resetPages()
  contactPickers.clearAll({ reload: true })
  refresh()
}

async function act(inq, status) {
  await slideThenRun(inq, async () => {
    await tradingApi.updateInquiry(inq.id, { status })
    await refresh()
  })
}

// Manual 1-5 rating of how well the AI classified/matched this inquiry — defaults to 5
// server-side, so a reviewer only has to touch the ones that are actually wrong instead
// of confirming every single inquiry. Updated in place, no full refresh needed.
async function setRating(inq, rating) {
  if (inq.classification_rating === rating) return
  await tradingApi.updateInquiry(inq.id, { classification_rating: rating })
  inq.classification_rating = rating
}

// ── Quick contact categorization (supplier/customer/both) ────────────────────────

const categoryError = ref('')

function hasSuggestion(inq) {
  return !!(inq.suggested_contact_category && inq.suggested_contact_category !== inq.contact_category)
}

// Pre-fill the dropdown with the AI's suggestion when one is pending, instead of the
// currently-saved category — the select still only persists on an explicit change/apply.
function categoryDisplayValue(inq) {
  return hasSuggestion(inq) ? inq.suggested_contact_category : (inq.contact_category || '')
}

// Manual dropdown pick — a deliberate human choice (e.g. correcting a wrong "both"),
// always applied as-is regardless of the contact's current category.
async function setContactCategory(inq, value) {
  if (!inq.contact) return
  try {
    const { data } = await contactsApi.update(inq.contact, { category: value })
    inq.contact_category = data.role_category || data.category || value
    categoryError.value = ''
  } catch (err) {
    categoryError.value = `Failed to update contact category: ${err.response?.data?.detail || err.message}`
  }
}

// "✓ Apply" button on an "AI suggests..." chip — the suggestion can be stale (computed
// at classification time, before a *different* inquiry from the same contact already
// moved it to "both"), so this goes through confirm-category, which re-checks on save
// and silently ignores the click if the contact is already "both" — instead of letting
// a stale suggestion downgrade it back to "supplier"/"customer".
async function applySuggestedCategory(inq) {
  if (!inq.contact) return
  try {
    const { data } = await contactsApi.confirmCategory(inq.contact, inq.suggested_contact_category)
    inq.contact_category = data.role_category || data.category
    inq.suggested_contact_category = inq.contact_category
    categoryError.value = ''
  } catch (err) {
    categoryError.value = `Failed to update contact category: ${err.response?.data?.detail || err.message}`
  }
}

// Inline "Incorrect Match" reason form, keyed by inquiry id
const incorrectMatchForms = ref({})

function setStatus(inq, e) {
  const val = typeof e === 'string' ? e : e.target.value
  if (typeof e !== 'string') e.target.value = ''
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
  await slideThenRun(inq, async () => {
    await tradingApi.updateInquiry(inq.id, { status: 'incorrect_match', remarks: form.reason.trim() })
    form.open = false
    await refresh()
  })
}

function cancelIncorrectMatch(inq) {
  const form = incorrectMatchForms.value[inq.id]
  if (form) form.open = false
}

// Applies a prefix/suffix token relative to a base string, per a 'prefix'|'suffix' setting.
function affix(base, token, position) {
  if (!token) return base
  return position === 'suffix' ? `${base} ${token}` : `${token} ${base}`
}

// Reorders inquiry line items by a ProductAttribute value ('original' is a no-op —
// keeps whatever order the sender's message/AI extraction produced). Items missing
// the chosen attribute sort to the end, in their original relative order, rather
// than being scattered arbitrarily among items that do have it.
const SORT_ATTR_KEY = { color: 'Color', storage: 'Storage', region: 'Region', flag: 'Flag' }

function sortProductsForReply(products, sortBy) {
  const attrKey = SORT_ATTR_KEY[sortBy]
  if (!attrKey) return products

  const withMeta = products.map((p, i) => ({ p, i, val: attributeValue(matchInventory(p), attrKey) }))
  withMeta.sort((a, b) => {
    const aHas = a.val !== ''
    const bHas = b.val !== ''
    if (aHas !== bHas) return aHas ? -1 : 1
    if (!aHas) return a.i - b.i
    if (attrKey === 'Storage') {
      const an = parseInt(a.val, 10)
      const bn = parseInt(b.val, 10)
      if (!Number.isNaN(an) && !Number.isNaN(bn) && an !== bn) return an - bn
    }
    return a.val.localeCompare(b.val, undefined, { sensitivity: 'base' }) || (a.i - b.i)
  })
  return withMeta.map(x => x.p)
}

function waPrefillText(inq) {
  const r = wtsReply.value
  const lines = []
  for (const p of sortProductsForReply(inq.products || [], r.sort_by)) {
    const match = matchInventory(p)
    let line = p.canonical_name || match?.name
    if (!line) continue
    line = stripBrandPrefix(line, match?.brand)
    if (r.send_flag) {
      line = affix(line, attributeValue(match, 'Flag'), r.flag_position)
    }
    if (r.send_color) {
      line = affix(line, colorEmoji(attributeValue(match, 'Color')), r.color_position)
    }
    // Only attach the matched price when it's actually the same product requested —
    // never quote a price that belongs to a different model/color/region than the line says.
    // Also never quote a price for something we have zero units of.
    if (match?.sale_price != null && match.qty > 0 && isReliableMatch(p, match)) {
      let price = r.send_currency && r.currency ? affix(String(match.sale_price), r.currency, r.currency_position) : String(match.sale_price)
      if (r.send_secondary_currency && r.secondary_currency && r.secondary_currency_rate) {
        const converted = Math.round(match.sale_price * r.secondary_currency_rate * 100) / 100
        price += ` (≈ ${r.secondary_currency} ${converted})`
      }
      line += ` - ${price}`
    }
    lines.push(line)
  }
  const offer = lines.join('\n')
  if (!offer) return ''
  // Deliberately does not quote the sender's own message back — just our prices,
  // prefixed with a hot-settable heading (§ AI Instructions > Trading dashboard).
  // One newline always separates heading from items; heading_blank_lines (0-3)
  // adds extra blank lines on top of that base separator.
  const blankLines = Math.max(0, Math.min(3, r.heading_blank_lines || 0))
  const separator = '\n'.repeat(1 + blankLines)
  return `${r.heading}${separator}${offer}`
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
    const flag = attributeValue(matchInventory(p), 'Flag')
    if (flag) line = `${flag} ${line}`
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
  tradingApi.getWtsReplySettings().then(({ data }) => { Object.assign(wtsReply.value, data) }).catch(() => {})
  tradingApi.getCardAnimationSettings().then(({ data }) => { Object.assign(cardAnimation.value, data) }).catch(() => {})
  document.addEventListener('pointerdown', closeContactPickersOnOutsideClick)
  document.addEventListener('pointerdown', closeCardMenusOnOutsideClick)
  pollTimer = setInterval(refresh, 15000)
  freshnessTimer = setInterval(() => { nowTick.value = Date.now() }, 1000)
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
  if (freshnessTimer) clearInterval(freshnessTimer)
  document.removeEventListener('pointerdown', closeContactPickersOnOutsideClick)
  document.removeEventListener('pointerdown', closeCardMenusOnOutsideClick)
  stopRowDialogDrag()
  stopMatchFixDrag()
  stopMarketDialogDrag()
  contactPickers.destroy()
  convStore.stopPolling()
})
</script>

<style scoped>
.trading-view { display: flex; flex-direction: column; height: 100%; overflow: hidden; background: var(--ui-bg); color: var(--ui-text); font-family: var(--ui-font-sans); }
.trading-header { display: flex; flex-wrap: wrap; gap: 6px 12px; align-items: center; padding: 6px 14px; background: var(--ui-surface); border-bottom: 1px solid var(--ui-border); }
.error-banner { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 8px 20px; background: var(--ui-danger-soft); color: var(--ui-danger); font-size: 0.85rem; border-bottom: 1px solid color-mix(in srgb,var(--ui-danger) 35%,white); }
.error-dismiss { background: none; border: none; color: var(--ui-danger); cursor: pointer; font-size: 0.9rem; padding: 0 4px; }
.header-left { display: flex; align-items: center; gap: 10px; }
.trading-live-status { display: flex; align-items: center; gap: 7px; white-space: nowrap; }
.live-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--ui-success); animation: blink 1.5s ease-in-out infinite; }
@keyframes blink { 0%,100% { opacity: 1; } 50% { opacity: 0.3; } }
.live-label { font-size: 0.8rem; color: var(--ui-success); font-weight: 600; }
.last-update { font-size: 0.78rem; color: var(--ui-text-subtle); }
.header-right { display: flex; flex-wrap: wrap; row-gap: 6px; gap: 7px; align-items: center; margin-left: auto; }
.toolbar-control { display: flex; align-items: center; gap: 6px; color: var(--ui-text-muted); font-size: .72rem; font-weight: 700; text-transform: uppercase; }
.status-filter-select { width: 126px; text-transform: none; }
.account-select { padding: 5px 10px; border: 1px solid var(--ui-border-strong); border-radius: var(--ui-radius-xs); background: var(--ui-surface); color: var(--ui-text); font-size: 0.85rem; }
.toolbar-icon-button { display: grid; width: 30px; height: 30px; place-items: center; border: 1px solid var(--ui-border-strong); border-radius: var(--ui-radius-xs); background: var(--ui-surface); color: var(--ui-text-muted); cursor: pointer; }
.toolbar-icon-button:hover { border-color: var(--ui-primary); color: var(--ui-primary); }
.close-stale-msg { padding: 6px 20px; font-size: 0.8rem; color: var(--ui-success); background: var(--ui-success-soft); border-bottom: 1px solid color-mix(in srgb,var(--ui-success) 30%,white); }
/* Main grid */
.main-grid { flex: 1; display: grid; grid-template-columns: 1fr 1fr; gap: 0; overflow: hidden; }
.feed-col { display: flex; flex-direction: column; border-right: 1px solid var(--ui-border); overflow: hidden; }
.feed-header { display: flex; align-items: center; justify-content: space-between; gap: 10px; padding: 10px 14px; border-bottom: 1px solid var(--ui-border); flex-wrap: wrap; }
.wtb-header { background: var(--ui-success-soft); }
.wts-header { background: var(--ui-warning-soft); }
.feed-heading { display: flex; align-items: center; min-width: 52px; }
.feed-title { font-weight: 800; font-size: 0.88rem; letter-spacing: 0.08em; }
.feed-count { margin-left: 3px; color: var(--ui-text-muted); font-size: 0.62rem; font-weight: 800; letter-spacing: 0; vertical-align: super; }
.feed-list { flex: 1; overflow-y: auto; padding: 10px; display: flex; flex-direction: column; gap: 8px; }
.feed-card { background: var(--ui-surface); border: 1px solid var(--ui-border); border-radius: var(--ui-radius-md); padding: 12px; display: flex; flex-direction: column; height: 300px; box-shadow: var(--ui-shadow-card); transition: transform 0.32s ease, opacity 0.32s ease; }
.feed-card.sliding-left { transform: translateX(-120%); opacity: 0; }
.feed-card.sliding-right { transform: translateX(120%); opacity: 0; }
.feed-card.urgent { border-left: 3px solid var(--ui-warning); }
.card-footer { flex-shrink: 0; padding-top: 8px; margin-top: 8px; border-top: 1px solid var(--ui-border); }
.feed-empty { text-align: center; color: var(--ui-text-subtle); font-size: 0.85rem; padding: 30px; }
.btn-ghost { padding: 6px 14px; border: 1px solid var(--ui-border-strong); border-radius: var(--ui-radius-xs); background: var(--ui-surface); color: var(--ui-text); cursor: pointer; font-size: 0.85rem; }
.btn-ghost.sm { padding: 4px 10px; font-size: 0.8rem; }
</style>
