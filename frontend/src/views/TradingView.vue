<template>
  <div class="trading-view" v-bind="$attrs">
    <!-- Header -->
    <div class="trading-header">
      <div class="header-left">
        <h2>Trading Dashboard</h2>
        <span class="live-dot"></span>
        <span class="live-label">Live</span>
        <span class="last-update">Updated {{ lastUpdateLabel }}</span>
      </div>
      <div class="header-right">
        <select v-model="selectedAccount" @change="resetFeedPagesAndRefresh" class="account-select">
          <option value="">All accounts</option>
          <option v-for="a in accounts" :key="a.id" :value="a.id">{{ a.display_name }}</option>
        </select>
        <div class="close-stale-control">
          <input
            type="number"
            v-model.number="closeStaleHours"
            min="1"
            step="1"
            class="close-stale-input"
            title="Close open inquiries older than this many hours"
          />
          <button class="btn-ghost sm" :disabled="closeStaleRunning" @click="runCloseStale">
            Close Older Than {{ closeStaleHours || 1 }}h
          </button>
        </div>
        <label class="card-animation-control" title="Direction an inquiry card slides when its status is changed">
          <span>Card animation</span>
          <select v-model="cardAnimation.slide_direction" @change="saveCardAnimation" class="account-select">
            <option value="left">Slide left</option>
            <option value="right">Slide right</option>
            <option value="none">Off</option>
          </select>
        </label>
        <button class="btn-ghost sm" @click="refresh">Refresh</button>
      </div>
    </div>

    <!-- Close-stale result banner -->
    <div v-if="closeStaleMsg" class="close-stale-msg">{{ closeStaleMsg }}</div>

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
          <div class="feed-heading">
            <span class="feed-title">BUYING (WTB)</span>
            <span class="feed-count">{{ buyTotal }}</span>
          </div>
          <div class="feed-controls">
            <div class="contact-picker contact-picker-buy">
              <input
                v-model="buyContactSearch"
                class="feed-control-input contact-search"
                placeholder="Search contact..."
                @focus="openContactPicker('buy')"
                @input="searchContacts('buy')"
              />
              <button v-if="buyContact" class="contact-clear-btn" title="Clear contact filter" @click="clearFeedContact('buy')">x</button>
              <div v-if="buyContactOpen" class="contact-menu" @scroll="onContactMenuScroll('buy', $event)">
                <button class="contact-option muted" @mousedown.prevent="clearFeedContact('buy')">All contacts</button>
                <button
                  v-for="contact in buyContactOptions"
                  :key="contact.id"
                  class="contact-option"
                  @mousedown.prevent="selectFeedContact('buy', contact)"
                >
                  <span class="contact-option-main">
                    <span>{{ contactLabel(contact) }}</span>
                    <span class="contact-account-badge">{{ contact.account_name || `Account ${contact.account_id}` }}</span>
                  </span>
                  <small>{{ contact.phone_number || contact.wa_contact_id }}</small>
                </button>
                <div v-if="buyContactLoading" class="contact-loading">Loading...</div>
                <div v-else-if="!buyContactOptions.length" class="contact-loading">No contacts</div>
              </div>
            </div>
            <select v-model="buyDateRange" class="feed-control-select" @change="setFeedDateRange('buy')">
              <option v-for="opt in feedDateOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
            </select>
            <select v-model="buySort" class="feed-control-select" @change="setFeedSort('buy')">
              <option v-for="opt in feedSortOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
            </select>
            <select v-model.number="buyPageSize" class="feed-control-select compact" @change="setFeedPageSize('buy')">
              <option v-for="size in feedPageSizeOptions" :key="size" :value="size">{{ size }}</option>
            </select>
          </div>
        </div>
        <div class="feed-list">
          <div
            v-for="inq in buyFeed" :key="inq.id"
            class="feed-card"
            :class="{ urgent: inq.age_seconds < 60, 'sliding-left': slidingCards[inq.id] === 'left', 'sliding-right': slidingCards[inq.id] === 'right' }"
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
                  @click="applySuggestedCategory(inq)"
                  :title="`AI suggests: ${categoryLabel(inq.suggested_contact_category)} — click to confirm`"
                >✓ Apply</button>
                <span class="source-label">{{ inq.source_type }}</span>
                <span v-if="inq.account_name" class="account-badge">{{ inq.account_name }}</span>
                <select class="status-select-mini header-status-select" @change="setStatus(inq, $event)">
                  <option value="" disabled selected>Set status...</option>
                  <option value="requested_price">Requested Price</option>
                  <option value="quoted_waiting">Quoted - Waiting</option>
                  <option value="no_response">No Response</option>
                  <option value="price_high">Price High</option>
                  <option value="no_stock">No Stock</option>
                  <option value="currently_in_stock">Currently In Stock</option>
                  <option value="not_dealing">Not Dealing ATM</option>
                  <option value="irrelevant">Irrelevant</option>
                  <option value="closed">Close</option>
                  <option value="tracking">Tracking</option>
                  <option value="incorrect_match">Incorrect Match</option>
                </select>
                <span class="card-age" :class="{ red: inq.age_seconds > 60 }">
                  {{ formatAge(inq.age_seconds) }}
                </span>
                <button
                  class="card-close-btn"
                  :disabled="isFreshInquiry(inq)"
                  :title="isFreshInquiry(inq) ? 'Just appeared - wait a moment to avoid closing it by accident' : 'Close inquiry'"
                  @click.stop="act(inq, 'closed')"
                >
                  <FontAwesomeIcon :icon="faXmark" />
                </button>
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
                    <div v-for="h in getInventoryHints(inq)" :key="h.name" class="stock-hint" :class="stockHintClass(h)">
                      <span class="stock-icon">{{ stockHintIcon(h) }}</span>
                      {{ h.product.name }} {{ stockHintAvailabilityLabel(h) }}
                      <span v-if="h.mismatch" class="mismatch-tag">— not "{{ h.name }}", closest match only</span>
                      <span v-if="h.product.sale_price"> · Sale: {{ h.product.currency || 'USD' }} {{ h.product.sale_price }}</span>
                      <span> · Qty: {{ h.product.qty }}</span>
                      <span v-if="h.product.cost_price">
                        ·
                        <span :class="{ 'cost-loss': h.product.sale_price != null && h.product.sale_price < h.product.cost_price }">
                          Cost: {{ h.product.currency || 'USD' }} {{ h.product.cost_price }}
                        </span>
                      </span>
                      <span class="stock-hint-actions">
                        <button
                          class="match-fix-btn verify"
                          :disabled="matchVerificationFor(inq, h)?.loading"
                          @click.stop="verifyStockMatch(inq, h)"
                          title="Ask AI to compare original message, summary, and this stock suggestion"
                        >{{ matchVerificationFor(inq, h)?.loading ? 'Checking' : 'Verify' }}</button>
                        <button
                          class="match-fix-btn create-inquiry"
                          :disabled="stockInquiryCreateFor(inq, h)?.loading || stockInquiryCreateFor(inq, h)?.saved"
                          @click.stop="createInquiryFromStockHint(inq, h)"
                          title="Save this stock suggestion as an inquiry product trace"
                        >{{ stockInquiryCreateLabel(inq, h) }}</button>
                        <button
                          v-if="h.mismatch"
                          class="match-fix-btn auto"
                          @click.stop="runAutoMatch(inq, h)"
                          title="Auto-search inventory (exact match, then embeddings) for the correct product"
                        >Auto</button>
                        <button
                          v-if="h.mismatch"
                          class="match-fix-btn"
                          @click.stop="toggleMatchFix(inq, h)"
                          title="This is actually the exact match — pick the correct product"
                        >Fix</button>
                      </span>
                      <div
                        v-if="matchVerificationFor(inq, h)"
                        class="match-verify-result"
                        :class="`verdict-${matchVerificationFor(inq, h).verdict || 'unknown'}`"
                      >
                        <strong>{{ matchVerificationLabel(matchVerificationFor(inq, h)) }}</strong>
                        <span v-if="matchVerificationFor(inq, h).reason"> - {{ matchVerificationFor(inq, h).reason }}</span>
                        <span v-if="matchVerificationFor(inq, h).error"> - {{ matchVerificationFor(inq, h).error }}</span>
                      </div>
                      <div v-if="stockInquiryCreateFor(inq, h)?.error" class="stock-create-error">
                        {{ stockInquiryCreateFor(inq, h).error }}
                      </div>
                    </div>
                  </template>
                  <span v-else class="body-row-empty">No matching stock found</span>
                </div>
              </div>
              <div v-if="isProductMatchingPending(inq)" class="product-match-pending">
                Product matching in progress. Extracted inquiry products are available now; inventory match results will update after V2 pass 2 completes.
              </div>
            </div>
            <div class="card-footer">
              <div class="card-actions">
                <button v-if="inq.products?.length" class="act-btn products" @click="openInquiryProducts(inq)">Inquiry Products</button>
                <button v-if="inq.products?.length" class="act-btn market" @click="openMarketParties(inq)">
                  {{ inq.inquiry_type === 'sell' ? 'Potential Buyers' : 'Available Sellers' }}
                </button>
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
              <div class="rating-row">
                <span class="rating-label">Match quality:</span>
                <button
                  v-for="n in 5" :key="n"
                  class="rating-btn"
                  :class="{ active: n === (inq.classification_rating ?? 5), low: n <= 2, mid: n === 3 }"
                  @click="setRating(inq, n)"
                  :title="`Rate ${n}/5 — ${n === 1 ? 'worst' : n === 5 ? 'exact' : ''}`"
                >{{ n }}</button>
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
        </div>
        <div class="feed-pager">
          <button class="btn-ghost sm" :disabled="buyLoading || buyPage <= 1" @click="changeFeedPage('buy', buyPage - 1)">Previous</button>
          <span class="feed-page-label">Page {{ buyPage }} of {{ buyTotalPages }}</span>
          <button class="btn-ghost sm" :disabled="buyLoading || buyPage >= buyTotalPages" @click="changeFeedPage('buy', buyPage + 1)">Next</button>
        </div>
      </div>

      <!-- WTS feed -->
      <div class="feed-col">
        <div class="feed-header wts-header">
          <div class="feed-heading">
            <span class="feed-title">SELLING (WTS)</span>
            <span class="feed-count">{{ sellTotal }}</span>
          </div>
          <div class="feed-controls">
            <div class="contact-picker contact-picker-sell">
              <input
                v-model="sellContactSearch"
                class="feed-control-input contact-search"
                placeholder="Search contact..."
                @focus="openContactPicker('sell')"
                @input="searchContacts('sell')"
              />
              <button v-if="sellContact" class="contact-clear-btn" title="Clear contact filter" @click="clearFeedContact('sell')">x</button>
              <div v-if="sellContactOpen" class="contact-menu" @scroll="onContactMenuScroll('sell', $event)">
                <button class="contact-option muted" @mousedown.prevent="clearFeedContact('sell')">All contacts</button>
                <button
                  v-for="contact in sellContactOptions"
                  :key="contact.id"
                  class="contact-option"
                  @mousedown.prevent="selectFeedContact('sell', contact)"
                >
                  <span class="contact-option-main">
                    <span>{{ contactLabel(contact) }}</span>
                    <span class="contact-account-badge">{{ contact.account_name || `Account ${contact.account_id}` }}</span>
                  </span>
                  <small>{{ contact.phone_number || contact.wa_contact_id }}</small>
                </button>
                <div v-if="sellContactLoading" class="contact-loading">Loading...</div>
                <div v-else-if="!sellContactOptions.length" class="contact-loading">No contacts</div>
              </div>
            </div>
            <select v-model="sellDateRange" class="feed-control-select" @change="setFeedDateRange('sell')">
              <option v-for="opt in feedDateOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
            </select>
            <select v-model="sellSort" class="feed-control-select" @change="setFeedSort('sell')">
              <option v-for="opt in feedSortOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
            </select>
            <select v-model.number="sellPageSize" class="feed-control-select compact" @change="setFeedPageSize('sell')">
              <option v-for="size in feedPageSizeOptions" :key="size" :value="size">{{ size }}</option>
            </select>
          </div>
        </div>
        <div class="feed-list">
          <div
            v-for="inq in sellFeed" :key="inq.id"
            class="feed-card"
            :class="{ urgent: inq.age_seconds < 60, 'sliding-left': slidingCards[inq.id] === 'left', 'sliding-right': slidingCards[inq.id] === 'right' }"
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
                  @click="applySuggestedCategory(inq)"
                  :title="`AI suggests: ${categoryLabel(inq.suggested_contact_category)} — click to confirm`"
                >✓ Apply</button>
                <span class="source-label">{{ inq.source_type }}</span>
                <span v-if="inq.account_name" class="account-badge">{{ inq.account_name }}</span>
                <select class="status-select-mini header-status-select" @change="setStatus(inq, $event)">
                  <option value="" disabled selected>Set status...</option>
                  <option value="requested_price">Requested Price</option>
                  <option value="quoted_waiting">Quoted - Waiting</option>
                  <option value="no_response">No Response</option>
                  <option value="price_high">Price High</option>
                  <option value="no_stock">No Stock</option>
                  <option value="currently_in_stock">Currently In Stock</option>
                  <option value="not_dealing">Not Dealing ATM</option>
                  <option value="irrelevant">Irrelevant</option>
                  <option value="closed">Close</option>
                  <option value="tracking">Tracking</option>
                  <option value="incorrect_match">Incorrect Match</option>
                </select>
                <span class="card-age" :class="{ red: inq.age_seconds > 60 }">
                  {{ formatAge(inq.age_seconds) }}
                </span>
                <button
                  class="card-close-btn"
                  :disabled="isFreshInquiry(inq)"
                  :title="isFreshInquiry(inq) ? 'Just appeared - wait a moment to avoid closing it by accident' : 'Close inquiry'"
                  @click.stop="act(inq, 'closed')"
                >
                  <FontAwesomeIcon :icon="faXmark" />
                </button>
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
                    <div v-for="h in getInventoryHints(inq)" :key="h.name" class="stock-hint" :class="stockHintClass(h)">
                      <span class="stock-icon">{{ stockHintIcon(h) }}</span>
                      {{ h.product.name }} {{ stockHintAvailabilityLabel(h) }}
                      <span v-if="h.mismatch" class="mismatch-tag">— not "{{ h.name }}", closest match only</span>
                      <span v-if="h.product.sale_price"> · Sale: {{ h.product.currency || 'USD' }} {{ h.product.sale_price }}</span>
                      <span> · Qty: {{ h.product.qty }}</span>
                      <span v-if="h.product.cost_price">
                        ·
                        <span :class="{ 'cost-loss': h.product.sale_price != null && h.product.sale_price < h.product.cost_price }">
                          Cost: {{ h.product.currency || 'USD' }} {{ h.product.cost_price }}
                        </span>
                      </span>
                      <span class="stock-hint-actions">
                        <button
                          class="match-fix-btn verify"
                          :disabled="matchVerificationFor(inq, h)?.loading"
                          @click.stop="verifyStockMatch(inq, h)"
                          title="Ask AI to compare original message, summary, and this stock suggestion"
                        >{{ matchVerificationFor(inq, h)?.loading ? 'Checking' : 'Verify' }}</button>
                        <button
                          class="match-fix-btn create-inquiry"
                          :disabled="stockInquiryCreateFor(inq, h)?.loading || stockInquiryCreateFor(inq, h)?.saved"
                          @click.stop="createInquiryFromStockHint(inq, h)"
                          title="Save this stock suggestion as an inquiry product trace"
                        >{{ stockInquiryCreateLabel(inq, h) }}</button>
                        <button
                          v-if="h.mismatch"
                          class="match-fix-btn auto"
                          @click.stop="runAutoMatch(inq, h)"
                          title="Auto-search inventory (exact match, then embeddings) for the correct product"
                        >Auto</button>
                        <button
                          v-if="h.mismatch"
                          class="match-fix-btn"
                          @click.stop="toggleMatchFix(inq, h)"
                          title="This is actually the exact match — pick the correct product"
                        >Fix</button>
                      </span>
                      <div
                        v-if="matchVerificationFor(inq, h)"
                        class="match-verify-result"
                        :class="`verdict-${matchVerificationFor(inq, h).verdict || 'unknown'}`"
                      >
                        <strong>{{ matchVerificationLabel(matchVerificationFor(inq, h)) }}</strong>
                        <span v-if="matchVerificationFor(inq, h).reason"> - {{ matchVerificationFor(inq, h).reason }}</span>
                        <span v-if="matchVerificationFor(inq, h).error"> - {{ matchVerificationFor(inq, h).error }}</span>
                      </div>
                      <div v-if="stockInquiryCreateFor(inq, h)?.error" class="stock-create-error">
                        {{ stockInquiryCreateFor(inq, h).error }}
                      </div>
                    </div>
                  </template>
                  <span v-else class="body-row-empty">No matching stock found</span>
                </div>
              </div>
              <div v-if="isProductMatchingPending(inq)" class="product-match-pending">
                Product matching in progress. Extracted inquiry products are available now; inventory match results will update after V2 pass 2 completes.
              </div>
            </div>
            <div class="card-footer">
              <div class="card-actions">
                <button v-if="inq.products?.length" class="act-btn products" @click="openInquiryProducts(inq)">Inquiry Products</button>
                <button v-if="inq.products?.length" class="act-btn market" @click="openMarketParties(inq)">
                  {{ inq.inquiry_type === 'sell' ? 'Potential Buyers' : 'Available Sellers' }}
                </button>
                <button v-if="inq.source_chat_id" class="act-btn chat" @click="viewChat(inq.source_chat_id, inq.account, inq.source_message_id, inq.source_message_time)" title="Open conversation">Chat →</button>
                <a v-if="waLink(inq)" :href="waLink(inq)" class="act-btn wa" title="Open in WhatsApp">
                  <svg viewBox="0 0 24 24" fill="currentColor" width="13" height="13"><path d="M12.04 2C6.58 2 2.13 6.45 2.13 11.91c0 1.75.46 3.45 1.32 4.95L2.05 22l5.25-1.38c1.45.79 3.08 1.21 4.74 1.21 5.46 0 9.91-4.45 9.91-9.91S17.5 2 12.04 2zm4.82 13.68c-.2.56-1.18 1.07-1.62 1.14-.44.07-.98.1-1.58-.1-.36-.12-.83-.28-1.42-.55-2.5-1.08-4.13-3.6-4.26-3.77-.13-.17-1.05-1.4-1.05-2.67 0-1.27.66-1.9.9-2.16.23-.26.5-.32.67-.32.17 0 .33 0 .48.01.15.01.36-.06.56.43.2.49.7 1.7.76 1.82.06.13.1.27.02.43-.08.17-.12.27-.23.41-.11.14-.24.31-.33.42-.11.13-.23.27-.1.53.13.26.59 1 1.27 1.63.87.8 1.61 1.04 1.87 1.16.26.12.41.1.57-.06.16-.16.66-.77.83-1.04.17-.26.34-.22.57-.13.23.09 1.44.68 1.69.8.25.12.41.18.47.28.07.1.07.56-.13 1.12z"/></svg>
                  WA
                </a>
                <a v-if="waAskPriceLink(inq)" :href="waAskPriceLink(inq)" class="act-btn wa-ask" title="Ask price on WhatsApp">
                  Ask Price
                </a>
              </div>
              <div class="rating-row">
                <span class="rating-label">Match quality:</span>
                <button
                  v-for="n in 5" :key="n"
                  class="rating-btn"
                  :class="{ active: n === (inq.classification_rating ?? 5), low: n <= 2, mid: n === 3 }"
                  @click="setRating(inq, n)"
                  :title="`Rate ${n}/5 — ${n === 1 ? 'worst' : n === 5 ? 'exact' : ''}`"
                >{{ n }}</button>
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
        </div>
        <div class="feed-pager">
          <button class="btn-ghost sm" :disabled="sellLoading || sellPage <= 1" @click="changeFeedPage('sell', sellPage - 1)">Previous</button>
          <span class="feed-page-label">Page {{ sellPage }} of {{ sellTotalPages }}</span>
          <button class="btn-ghost sm" :disabled="sellLoading || sellPage >= sellTotalPages" @click="changeFeedPage('sell', sellPage + 1)">Next</button>
        </div>
      </div>

    </div>
  </div>

  <!-- "Fix match" dialog — teleported so it isn't clipped by the card body's
       overflow:hidden (needed for the clamped/expandable Summary/Message/Stock rows). -->
  <Teleport to="body">
    <div v-if="matchFixTarget" class="match-fix-backdrop">
      <div
        class="match-fix-dialog"
        :style="{ transform: `translate(${matchFixDrag.x}px, ${matchFixDrag.y}px)` }"
      >
        <div class="match-fix-header" @mousedown="startMatchFixDrag">
          <span class="match-fix-dialog-title">
            Pick the correct product for "{{ matchFixTarget.hint.name }}"
          </span>
          <button class="match-fix-close" @mousedown.stop @click="closeMatchFix" title="Close">×</button>
        </div>

        <div v-if="autoSearchLoading" class="match-fix-status">Searching embeddings…</div>
        <div v-if="autoSearchError" class="match-fix-error">{{ autoSearchError }}</div>
        <template v-if="autoSearchResults?.length">
          <div class="match-fix-section-label">Suggested matches</div>
          <div class="match-fix-list">
            <label v-for="r in autoSearchResults" :key="`auto-${r.product.id}`" class="match-fix-row">
              <input type="checkbox" @change="selectMatchFix(r.product)" />
              {{ r.product.name }}
              <span v-if="r.product.sale_price" class="match-fix-price">· {{ r.product.currency || 'USD' }} {{ r.product.sale_price }}</span>
              <span class="match-fix-source" :class="r.source">
                {{ r.source === 'direct' ? 'exact' : `~${Math.round((1 - r.distance) * 100)}% match` }}
              </span>
            </label>
          </div>
        </template>
        <div v-else-if="autoSearchResults && !autoSearchLoading" class="match-fix-status">
          No automatic match found — search manually below
        </div>

        <div class="match-fix-section-label">Search manually</div>
        <input
          v-model="matchFixQuery"
          class="match-fix-search"
          placeholder="Search products…"
          autofocus
        />
        <div class="match-fix-list">
          <label v-for="prod in filteredMatchProducts" :key="prod.id" class="match-fix-row">
            <input type="checkbox" @change="selectMatchFix(prod)" />
            {{ prod.name }}
            <span v-if="prod.sale_price" class="match-fix-price">· {{ prod.currency || 'USD' }} {{ prod.sale_price }}</span>
          </label>
          <div v-if="!filteredMatchProducts.length" class="match-fix-empty">No products found</div>
        </div>
      </div>
    </div>
  </Teleport>

  <!-- Expanded Summary/Original Message/Stock Suggestion row — a centered popup instead
       of growing in place inside the card, which used to leave a lot of dead space
       around a short expanded row and made the card jump around in the feed. -->
  <Teleport to="body">
    <div v-if="expandedInquiry" class="row-expand-backdrop">
      <div
        class="row-expand-dialog"
        :style="{ transform: `translate(${rowDialogDrag.x}px, ${rowDialogDrag.y}px)` }"
      >
        <div class="row-expand-header" @mousedown="startRowDialogDrag">
          <span class="row-expand-title">{{ rowLabel(expandedBodyRow.row) }}</span>
          <button class="row-expand-close" @mousedown.stop @click="collapseBodyRow" title="Close">×</button>
        </div>
        <div class="row-expand-content">
          <template v-if="expandedBodyRow.row === 'summary'">
            {{ expandedInquiry.summary || '—' }}
          </template>
          <template v-else-if="expandedBodyRow.row === 'message'">
            {{ expandedInquiry.source_message_text || '—' }}
          </template>
          <template v-else-if="expandedBodyRow.row === 'stock'">
            <template v-if="getInventoryHints(expandedInquiry).length">
              <div v-for="h in getInventoryHints(expandedInquiry)" :key="h.name" class="stock-hint" :class="stockHintClass(h)">
                <span class="stock-icon">{{ stockHintIcon(h) }}</span>
                {{ h.product.name }} {{ stockHintAvailabilityLabel(h) }}
                <span v-if="h.mismatch" class="mismatch-tag">— not "{{ h.name }}", closest match only</span>
                <span v-if="h.product.sale_price"> · Sale: {{ h.product.currency || 'USD' }} {{ h.product.sale_price }}</span>
                <span> · Qty: {{ h.product.qty }}</span>
                <span v-if="h.product.cost_price">
                  ·
                  <span :class="{ 'cost-loss': h.product.sale_price != null && h.product.sale_price < h.product.cost_price }">
                    Cost: {{ h.product.currency || 'USD' }} {{ h.product.cost_price }}
                  </span>
                </span>
                <span class="stock-hint-actions">
                  <button
                    class="match-fix-btn verify"
                    :disabled="matchVerificationFor(expandedInquiry, h)?.loading"
                    @click.stop="verifyStockMatch(expandedInquiry, h)"
                    title="Ask AI to compare original message, summary, and this stock suggestion"
                  >{{ matchVerificationFor(expandedInquiry, h)?.loading ? 'Checking' : 'Verify' }}</button>
                  <button
                    class="match-fix-btn create-inquiry"
                    :disabled="stockInquiryCreateFor(expandedInquiry, h)?.loading || stockInquiryCreateFor(expandedInquiry, h)?.saved"
                    @click.stop="createInquiryFromStockHint(expandedInquiry, h)"
                    title="Save this stock suggestion as an inquiry product trace"
                  >{{ stockInquiryCreateLabel(expandedInquiry, h) }}</button>
                  <button
                    v-if="h.mismatch"
                    class="match-fix-btn auto"
                    @click.stop="runAutoMatch(expandedInquiry, h)"
                    title="Auto-search inventory (exact match, then embeddings) for the correct product"
                  >Auto</button>
                  <button
                    v-if="h.mismatch"
                    class="match-fix-btn"
                    @click.stop="toggleMatchFix(expandedInquiry, h)"
                    title="This is actually the exact match — pick the correct product"
                  >Fix</button>
                </span>
                <div
                  v-if="matchVerificationFor(expandedInquiry, h)"
                  class="match-verify-result"
                  :class="`verdict-${matchVerificationFor(expandedInquiry, h).verdict || 'unknown'}`"
                >
                  <strong>{{ matchVerificationLabel(matchVerificationFor(expandedInquiry, h)) }}</strong>
                  <span v-if="matchVerificationFor(expandedInquiry, h).reason"> - {{ matchVerificationFor(expandedInquiry, h).reason }}</span>
                  <span v-if="matchVerificationFor(expandedInquiry, h).error"> - {{ matchVerificationFor(expandedInquiry, h).error }}</span>
                </div>
                <div v-if="stockInquiryCreateFor(expandedInquiry, h)?.error" class="stock-create-error">
                  {{ stockInquiryCreateFor(expandedInquiry, h).error }}
                </div>
              </div>
            </template>
            <span v-else class="body-row-empty">No matching stock found</span>
          </template>
        </div>
      </div>
    </div>
  </Teleport>

  <Teleport to="body">
    <div v-if="productModalOpen" class="inquiry-product-backdrop" @click.self="closeInquiryProducts">
      <div class="inquiry-product-dialog">
        <div class="inquiry-product-header">
          <div>
            <div class="inquiry-product-title">Inquiry Products</div>
            <div class="inquiry-product-subtitle">{{ productModalInquiry?.summary || 'Parsed products from selected inquiry' }}</div>
          </div>
          <button class="match-fix-close" @click="closeInquiryProducts" title="Close">×</button>
        </div>

        <div v-if="productLinesLoading" class="inquiry-product-state">Loading products...</div>
        <div v-else-if="productLinesError" class="inquiry-product-error">{{ productLinesError }}</div>
        <div v-else-if="!productLines.length" class="inquiry-product-state">No product lines found.</div>
        <div v-else class="inquiry-product-list">
          <div
            v-for="line in productLines"
            :key="line.index"
            class="inquiry-product-row"
            :class="{ linked: line.has_inventory_mapping || line.inquiry_product_id }"
          >
            <div class="inquiry-product-main">
              <div class="inquiry-product-name">{{ line.canonical_name || 'Invalid product line' }}</div>
              <div class="inquiry-product-meta">
                <span v-if="line.brand">Brand {{ line.brand }}</span>
                <span v-if="formatLineAttributes(line.attributes)">Attrs {{ formatLineAttributes(line.attributes) }}</span>
                <span v-if="line.quantity">Qty {{ line.quantity }}</span>
                <span v-if="line.price">{{ line.currency || '' }} {{ line.price }}</span>
                <span v-if="line.match_type">AI match: {{ line.match_type }}</span>
              </div>
              <div v-if="line.product_name" class="inquiry-product-linked">Mapped to inventory: {{ line.product_name }}</div>
              <div v-else-if="line.non_inventory_product_name" class="inquiry-product-linked">Tracked as non-inventory: {{ line.non_inventory_product_name }}</div>
              <div v-else-if="line.inquiry_product_id" class="inquiry-product-linked">Inquiry product row already exists.</div>
            </div>
            <div class="inquiry-product-actions">
              <span v-if="line.has_inventory_mapping || line.non_inventory_mention_id" class="linked-pill">Linked</span>
              <button
                v-if="!line.has_inventory_mapping && !line.inquiry_product_id"
                class="act-btn deal"
                :disabled="creatingLineIndex === line.index || !line.valid"
                @click="createProductFromLine(line)"
              >
                {{ creatingLineIndex === line.index ? 'Creating...' : 'Create Product' }}
              </button>
              <button
                v-if="line.can_track_non_inventory"
                class="act-btn products"
                :disabled="trackingLineIndex === line.index || !line.valid"
                @click="trackNonInventoryFromLine(line)"
              >
                {{ trackingLineIndex === line.index ? 'Tracking...' : 'Track Non-Inventory' }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </Teleport>

  <Teleport to="body">
    <div v-if="marketModalOpen" class="market-backdrop" @click.self="closeMarketParties">
      <div
        class="market-dialog"
        :style="{ transform: `translate(${marketDialogDrag.x}px, ${marketDialogDrag.y}px)` }"
      >
        <div class="market-header" @mousedown="startMarketDialogDrag">
          <div>
            <div class="market-eyebrow">{{ marketModalTitle }}</div>
            <div class="market-title">{{ marketModalInquiry?.summary || 'Market parties for selected inquiry' }}</div>
            <div class="market-subtitle">
              {{ marketModalInquiry?.inquiry_type === 'sell' ? 'Showing parties asking for these products' : 'Showing parties selling these products' }}
            </div>
          </div>
          <button class="match-fix-close" @mousedown.stop @click="closeMarketParties" title="Close">×</button>
        </div>

        <div class="market-body">
          <div class="market-source-tabs">
            <button
              class="market-source-tab"
              :class="{ active: marketSource === 'inventory' }"
              @click="setMarketSource('inventory')"
            >Inventory Matches</button>
            <button
              class="market-source-tab"
              :class="{ active: marketSource === 'non_inventory' }"
              @click="setMarketSource('non_inventory')"
            >Non-Inventory Tracking</button>
          </div>
          <div class="market-source-tabs method-tabs">
            <button
              class="market-source-tab"
              :class="{ active: marketMethod === 'exact' }"
              @click="setMarketMethod('exact')"
            >Exact</button>
            <button
              class="market-source-tab"
              :class="{ active: marketMethod === 'text' }"
              @click="setMarketMethod('text')"
            >Text</button>
            <button
              class="market-source-tab"
              :class="{ active: marketMethod === 'embedding' }"
              @click="setMarketMethod('embedding')"
            >Embedding</button>
          </div>
          <div v-if="marketLoading" class="market-state">Loading market offers...</div>
          <div v-else-if="marketError" class="market-error">{{ marketError }}</div>
          <div v-else-if="!marketProducts.length" class="market-state">No product lines available.</div>
          <div v-else class="market-product-list">
            <div
              v-for="product in marketProducts"
              :key="`${product.index}-${product.product_id || 'unmapped'}`"
              class="market-product"
            >
              <div class="market-product-head">
                <div>
                  <div class="market-product-name">
                    {{ product.product_name || product.canonical_name || `Product line ${product.index + 1}` }}
                  </div>
                  <div class="market-product-meta">
                    Line {{ product.index + 1 }} · {{ product.action_label === 'selling' ? 'parties selling this item' : 'parties asking for this item' }}
                  </div>
                </div>
                <span class="market-count">{{ product.parties?.length || 0 }}</span>
              </div>

              <div v-if="product.message" class="market-state compact">{{ product.message }}</div>
              <div v-else class="market-party-list">
                <div
                  v-for="party in product.parties"
                  :key="party.inquiry_product_id"
                  class="market-party"
                >
                  <div class="market-party-main">
                    <div class="market-party-name">{{ party.contact_name || 'Unknown contact' }}</div>
                    <div class="market-party-meta">
                      <span>{{ party.contact_phone || 'No phone' }}</span>
                      <span v-if="party.account_name">· {{ party.account_name }}</span>
                      <span v-if="party.source_chat_name">· {{ party.source_chat_name }}</span>
                    </div>
                    <div class="market-party-text">{{ party.original_text || 'No source text' }}</div>
                    <div class="market-party-facts">
                      <span v-if="party.quantity">Qty {{ party.quantity }}</span>
                      <span v-if="party.price">{{ party.currency || '' }} {{ party.price }}</span>
                      <span v-if="party.first_seen_at">{{ formatDateTime(party.first_seen_at) }}</span>
                      <span v-if="party.distance != null">Distance {{ party.distance }}</span>
                    </div>
                  </div>
                  <div class="market-party-actions">
                    <button
                      v-if="party.source_chat_id"
                      class="act-btn chat"
                      @click="viewChat(party.source_chat_id, party.account_id, party.source_message_id, party.source_message_time)"
                    >Chat →</button>
                    <a
                      v-if="marketWaLink(party)"
                      :href="marketWaLink(party)"
                      class="act-btn wa"
                    >WA</a>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { FontAwesomeIcon } from '@fortawesome/vue-fontawesome'
import { faXmark } from '@fortawesome/free-solid-svg-icons'
import { useConversationsStore } from '@/stores/conversations'
import { accountsApi, tradingApi, contactsApi } from '../api/index.js'

// The teleported "Fix match" dialog below makes this component multi-root, which breaks
// Vue's automatic $attrs inheritance onto a single root (see the same fix on StorageView.vue) —
// bind explicitly onto the real root div instead.
defineOptions({ inheritAttrs: false })

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
const buyFeed          = ref([])
const sellFeed         = ref([])
const buyTotal         = ref(0)
const sellTotal        = ref(0)
const buyPage          = ref(1)
const sellPage         = ref(1)
const buyPageSize      = ref(50)
const sellPageSize     = ref(50)
const buySort          = ref('latest')
const sellSort         = ref('latest')
const buyContact       = ref('')
const sellContact      = ref('')
const buyContactSearch = ref('')
const sellContactSearch = ref('')
const buyContactOpen = ref(false)
const sellContactOpen = ref(false)
const buyContactLoading = ref(false)
const sellContactLoading = ref(false)
const buyContactPage = ref(1)
const sellContactPage = ref(1)
const buyContactTotalPages = ref(1)
const sellContactTotalPages = ref(1)
const buyDateRange     = ref('today')
const sellDateRange    = ref('today')
const buyContactOptions = ref([])
const sellContactOptions = ref([])
const buyLoading       = ref(false)
const sellLoading      = ref(false)
let   pollTimer        = null
let   buyContactSearchTimer = null
let   sellContactSearchTimer = null

const feedPageSizeOptions = [25, 50, 100, 200]
const feedSortOptions = [
  { value: 'latest', label: 'Latest first' },
  { value: 'oldest', label: 'Oldest first' },
  { value: 'recently_updated', label: 'Recently updated' },
  { value: 'least_recently_updated', label: 'Least updated' },
  { value: 'contact_name', label: 'Contact A-Z' },
]
const feedDateOptions = [
  { value: 'last_30_minutes', label: 'Last 30 mins' },
  { value: 'last_hour', label: 'Last hour' },
  { value: 'last_2_hours', label: 'Last 2 hours' },
  { value: 'last_5_hours', label: 'Last 5 hours' },
  { value: 'today', label: 'Today' },
  { value: 'yesterday', label: 'Yesterday' },
  { value: 'this_week', label: 'This week' },
  { value: 'last_week', label: 'Last week' },
  { value: 'this_month', label: 'This month' },
  { value: 'last_month', label: 'Last month' },
]

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
  if (willOpen) rowDialogDrag.value = { x: 0, y: 0 }
}

function collapseBodyRow() {
  expandedBodyRow.value = null
}

// Dragging for the row-expand popup below — tracked as a cumulative translate offset
// from its default centered position, rather than absolute viewport coordinates, so it
// doesn't need a getBoundingClientRect measurement to initialize.
const rowDialogDrag = ref({ x: 0, y: 0 })
let rowDragState = null

function startRowDialogDrag(e) {
  rowDragState = {
    startX: e.clientX,
    startY: e.clientY,
    baseX: rowDialogDrag.value.x,
    baseY: rowDialogDrag.value.y,
  }
  window.addEventListener('mousemove', onRowDialogDrag)
  window.addEventListener('mouseup', stopRowDialogDrag)
}

function onRowDialogDrag(e) {
  if (!rowDragState) return
  rowDialogDrag.value = {
    x: rowDragState.baseX + (e.clientX - rowDragState.startX),
    y: rowDragState.baseY + (e.clientY - rowDragState.startY),
  }
}

function stopRowDialogDrag() {
  rowDragState = null
  window.removeEventListener('mousemove', onRowDialogDrag)
  window.removeEventListener('mouseup', stopRowDialogDrag)
}

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
const matchFixTarget = ref(null) // { inq, hint } | null
const matchFixQuery  = ref('')

// Auto-search results (from the "Auto" button below) — null means no auto-search has
// run yet for the currently-open dialog; [] means one ran and found nothing.
const autoSearchResults = ref(null) // [{ product, source: 'direct'|'embedding', distance? }] | null
const autoSearchLoading = ref(false)
const autoSearchError   = ref('')
const matchVerifications = ref({})
const stockInquiryCreates = ref({})
const productModalOpen = ref(false)
const productModalInquiry = ref(null)
const productLines = ref([])
const productLinesLoading = ref(false)
const productLinesError = ref('')
const creatingLineIndex = ref(null)
const trackingLineIndex = ref(null)
const marketModalOpen = ref(false)
const marketModalInquiry = ref(null)
const marketProducts = ref([])
const marketLoading = ref(false)
const marketError = ref('')
const marketActionLabel = ref('')
const marketSource = ref('inventory')
const marketMethod = ref('exact')
const marketDialogDrag = ref({ x: 0, y: 0 })
let marketDragState = null

const marketModalTitle = computed(() => {
  if (marketModalInquiry.value?.inquiry_type === 'sell') return 'Potential Buyers'
  return 'Available Sellers'
})

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

async function openInquiryProducts(inq) {
  productModalInquiry.value = inq
  productModalOpen.value = true
  await loadInquiryProducts(inq.id)
}

function closeInquiryProducts() {
  productModalOpen.value = false
  productModalInquiry.value = null
  productLines.value = []
  productLinesError.value = ''
}

async function openMarketParties(inq) {
  marketModalInquiry.value = inq
  marketModalOpen.value = true
  marketSource.value = 'inventory'
  marketMethod.value = 'exact'
  marketDialogDrag.value = { x: 0, y: 0 }
  await loadMarketParties(inq.id)
}

function closeMarketParties() {
  marketModalOpen.value = false
  marketModalInquiry.value = null
  marketProducts.value = []
  marketError.value = ''
  stopMarketDialogDrag()
}

async function loadMarketParties(inquiryId) {
  marketLoading.value = true
  marketError.value = ''
  try {
    const { data } = await tradingApi.getInquiryMarketParties(inquiryId, {
      limit: 25,
      market_source: marketSource.value,
      market_method: marketMethod.value,
    })
    marketProducts.value = data.products || []
    marketModalInquiry.value = data.inquiry || marketModalInquiry.value
    marketActionLabel.value = data.action_label || ''
    marketSource.value = data.source || marketSource.value
    marketMethod.value = data.method || marketMethod.value
  } catch (e) {
    marketError.value = e.response?.data?.detail || e.message || 'Failed to load market offers'
  } finally {
    marketLoading.value = false
  }
}

async function setMarketSource(source) {
  if (marketSource.value === source || !marketModalInquiry.value) return
  marketSource.value = source
  await loadMarketParties(marketModalInquiry.value.id)
}

async function setMarketMethod(method) {
  if (marketMethod.value === method || !marketModalInquiry.value) return
  marketMethod.value = method
  await loadMarketParties(marketModalInquiry.value.id)
}

function startMarketDialogDrag(e) {
  marketDragState = {
    startX: e.clientX,
    startY: e.clientY,
    baseX: marketDialogDrag.value.x,
    baseY: marketDialogDrag.value.y,
  }
  window.addEventListener('mousemove', onMarketDialogDrag)
  window.addEventListener('mouseup', stopMarketDialogDrag)
}

function onMarketDialogDrag(e) {
  if (!marketDragState) return
  marketDialogDrag.value = {
    x: marketDragState.baseX + (e.clientX - marketDragState.startX),
    y: marketDragState.baseY + (e.clientY - marketDragState.startY),
  }
}

function stopMarketDialogDrag() {
  marketDragState = null
  window.removeEventListener('mousemove', onMarketDialogDrag)
  window.removeEventListener('mouseup', stopMarketDialogDrag)
}

function formatLineAttributes(attributes) {
  if (!attributes || typeof attributes !== 'object' || Array.isArray(attributes)) return ''
  return Object.entries(attributes)
    .filter(([, value]) => value != null && String(value).trim() !== '')
    .map(([key, value]) => `${key}: ${value}`)
    .join(', ')
}

async function loadInquiryProducts(inquiryId) {
  productLinesLoading.value = true
  productLinesError.value = ''
  try {
    const { data } = await tradingApi.getInquiryProductLines(inquiryId)
    productLines.value = data.products || []
    productModalInquiry.value = data.inquiry || productModalInquiry.value
  } catch (e) {
    productLinesError.value = e.response?.data?.detail || e.message || 'Failed to load inquiry products'
  } finally {
    productLinesLoading.value = false
  }
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

async function createProductFromLine(line) {
  if (!productModalInquiry.value) return
  creatingLineIndex.value = line.index
  productLinesError.value = ''
  try {
    const { data } = await tradingApi.createProductFromInquiryLine(
      productModalInquiry.value.id,
      line.index,
      { brand: line.brand || '' },
    )
    if (data.product) {
      allProducts.value = [data.product, ...allProducts.value.filter(p => p.id !== data.product.id)]
    }
    if (data.inquiry) {
      productModalInquiry.value = data.inquiry
      patchInquiryInFeeds(data.inquiry)
    }
    await loadInquiryProducts(productModalInquiry.value.id)
  } catch (e) {
    productLinesError.value = e.response?.data?.detail || e.message || 'Failed to create product'
  } finally {
    creatingLineIndex.value = null
  }
}

async function trackNonInventoryFromLine(line) {
  if (!productModalInquiry.value) return
  trackingLineIndex.value = line.index
  productLinesError.value = ''
  try {
    await tradingApi.trackNonInventoryFromInquiryLine(productModalInquiry.value.id, line.index)
    await loadInquiryProducts(productModalInquiry.value.id)
  } catch (e) {
    productLinesError.value = e.response?.data?.detail || e.message || 'Failed to track non-inventory product'
  } finally {
    trackingLineIndex.value = null
  }
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

function openMatchFix(inq, hint) {
  matchFixTarget.value = { inq, hint }
  matchFixQuery.value = ''
  autoSearchResults.value = null
  autoSearchError.value = ''
  // Always reopen centered — a drag offset from a previous popup shouldn't carry over.
  matchFixDrag.value = { x: 0, y: 0 }
}

function toggleMatchFix(inq, hint) {
  const isOpen = matchFixTarget.value?.inq === inq && matchFixTarget.value?.hint === hint
  if (isOpen) { closeMatchFix(); return }
  openMatchFix(inq, hint)
}

function closeMatchFix() {
  matchFixTarget.value = null
  autoSearchResults.value = null
  autoSearchError.value = ''
}

// Dragging for the "Fix match" popup — same cumulative-translate-offset technique as the
// row-expand popup above, so it doesn't need a getBoundingClientRect measurement.
const matchFixDrag = ref({ x: 0, y: 0 })
let matchFixDragState = null

function startMatchFixDrag(e) {
  matchFixDragState = {
    startX: e.clientX,
    startY: e.clientY,
    baseX: matchFixDrag.value.x,
    baseY: matchFixDrag.value.y,
  }
  window.addEventListener('mousemove', onMatchFixDrag)
  window.addEventListener('mouseup', stopMatchFixDrag)
}

function onMatchFixDrag(e) {
  if (!matchFixDragState) return
  matchFixDrag.value = {
    x: matchFixDragState.baseX + (e.clientX - matchFixDragState.startX),
    y: matchFixDragState.baseY + (e.clientY - matchFixDragState.startY),
  }
}

function stopMatchFixDrag() {
  matchFixDragState = null
  window.removeEventListener('mousemove', onMatchFixDrag)
  window.removeEventListener('mouseup', stopMatchFixDrag)
}

function normalizeForSearch(s) {
  return (s || '').toLowerCase().replace(/[^a-z0-9]/g, '')
}

// Fully client-side — allProducts is already loaded, and this is just an equality/substring
// check, so there's no reason to round-trip to the server for it.
function directProductSearch(query) {
  const qNorm = normalizeForSearch(query)
  if (!qNorm) return []
  return (allProducts.value || []).filter(p => {
    const nameNorm = normalizeForSearch(p.name)
    if (qNorm === nameNorm || nameNorm.includes(qNorm) || qNorm.includes(nameNorm)) return true
    return (p.aliases || []).some(a => normalizeForSearch(a) === qNorm)
  })
}

// "Auto" button — tries a direct name/alias search first (instant, no network); only
// falls back to the embedding-search endpoint when that comes up empty, since embeddings
// are a slower, fuzzier last resort, not the first thing to reach for. Either way this
// only *suggests* candidates — the human still has to tick a checkbox to apply one, same
// as manual "Fix" — an automatic pick here would repeat the same kind of mismatch this
// button exists to correct, just with an embedding-distance guess instead of the AI's.
async function runAutoMatch(inq, hint) {
  openMatchFix(inq, hint)
  const direct = directProductSearch(hint.name)
  if (direct.length) {
    autoSearchResults.value = direct.map(product => ({ product, source: 'direct' }))
    return
  }
  autoSearchLoading.value = true
  try {
    const { data } = await tradingApi.searchProductEmbeddings({ q: hint.name })
    autoSearchResults.value = (data.results || []).map(r => ({ product: r.product, source: 'embedding', distance: r.distance }))
  } catch (e) {
    autoSearchError.value = 'Search failed: ' + (e.response?.data?.detail || e.message)
    autoSearchResults.value = []
  } finally {
    autoSearchLoading.value = false
  }
}

const filteredMatchProducts = computed(() => {
  const q = matchFixQuery.value.trim().toLowerCase()
  const list = allProducts.value || []
  if (!q) return list
  return list.filter(p =>
    (p.name || '').toLowerCase().includes(q) || (p.brand || '').toLowerCase().includes(q)
  )
})

async function selectMatchFix(product) {
  const target = matchFixTarget.value
  if (!target) return
  const { data } = await tradingApi.correctMatch(target.inq.id, { index: target.hint.index, product_id: product.id })
  target.inq.products = data.products
  matchFixTarget.value = null
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

function isProductMatchingPending(inq) {
  return inq?.classification_version === 'v2' && inq?.product_match_status === 'pending'
}

const lastUpdateLabel = computed(() => {
  if (!lastUpdate.value) return '—'
  const secs = Math.floor((Date.now() - lastUpdate.value) / 1000)
  if (secs < 10) return 'just now'
  return `${secs}s ago`
})


const buyTotalPages = computed(() => Math.max(1, Math.ceil(buyTotal.value / buyPageSize.value)))
const sellTotalPages = computed(() => Math.max(1, Math.ceil(sellTotal.value / sellPageSize.value)))

function formatAge(secs) {
  if (secs < 60)   return `${secs}s`
  if (secs < 3600) return `${Math.floor(secs / 60)}m`
  return `${Math.floor(secs / 3600)}h`
}

function contactLabel(contact) {
  return contact?.display_name || contact?.push_name || contact?.phone_number || contact?.wa_contact_id || `Contact ${contact?.id || ''}`
}

function contactPickerState(type) {
  const isBuy = type === 'buy'
  return {
    options: isBuy ? buyContactOptions : sellContactOptions,
    search: isBuy ? buyContactSearch : sellContactSearch,
    loading: isBuy ? buyContactLoading : sellContactLoading,
    page: isBuy ? buyContactPage : sellContactPage,
    totalPages: isBuy ? buyContactTotalPages : sellContactTotalPages,
    open: isBuy ? buyContactOpen : sellContactOpen,
  }
}

async function loadContactOptions(type, { reset = false } = {}) {
  const state = contactPickerState(type)
  if (state.loading.value) return
  if (!reset && state.page.value >= state.totalPages.value) return

  if (reset) {
    state.page.value = 1
    state.totalPages.value = 1
    state.options.value = []
  } else {
    state.page.value += 1
  }

  state.loading.value = true
  try {
    const params = {
      page: state.page.value,
      page_size: 10,
      ordering: 'display_name',
      type: 'phone',
    }
    if (selectedAccount.value) params.account = selectedAccount.value
    if (state.search.value.trim()) params.search = state.search.value.trim()

    const { data } = await contactsApi.list(params)
    const incoming = data.results ?? data
    state.totalPages.value = data.total_pages || Math.max(1, Math.ceil((data.count || incoming.length) / 10))
    const seen = new Set(state.options.value.map(c => c.id))
    const merged = reset ? [] : [...state.options.value]
    for (const contact of incoming) {
      if (!seen.has(contact.id)) {
        merged.push(contact)
        seen.add(contact.id)
      }
    }
    state.options.value = merged
  } finally {
    state.loading.value = false
  }
}

function openContactPicker(type) {
  const state = contactPickerState(type)
  state.open.value = true
  if (!state.options.value.length) loadContactOptions(type, { reset: true })
}

function closeContactPickersOnOutsideClick(event) {
  if (event.target.closest?.('.contact-picker')) return
  buyContactOpen.value = false
  sellContactOpen.value = false
}

function searchContacts(type) {
  const timerRef = type === 'buy' ? 'buy' : 'sell'
  if (timerRef === 'buy') {
    clearTimeout(buyContactSearchTimer)
    buyContactSearchTimer = setTimeout(() => loadContactOptions('buy', { reset: true }), 250)
  } else {
    clearTimeout(sellContactSearchTimer)
    sellContactSearchTimer = setTimeout(() => loadContactOptions('sell', { reset: true }), 250)
  }
}

function onContactMenuScroll(type, event) {
  const el = event.target
  if (el.scrollTop + el.clientHeight >= el.scrollHeight - 20) {
    loadContactOptions(type)
  }
}

function selectFeedContact(type, contact) {
  if (type === 'buy') {
    buyContact.value = contact.id
    buyContactSearch.value = contactLabel(contact)
    buyContactOpen.value = false
    setFeedContact('buy')
  } else {
    sellContact.value = contact.id
    sellContactSearch.value = contactLabel(contact)
    sellContactOpen.value = false
    setFeedContact('sell')
  }
}

function clearFeedContact(type) {
  if (type === 'buy') {
    buyContact.value = ''
    buyContactSearch.value = ''
    buyContactOpen.value = false
    setFeedContact('buy')
  } else {
    sellContact.value = ''
    sellContactSearch.value = ''
    sellContactOpen.value = false
    setFeedContact('sell')
  }
}

function isoDate(date) {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function isoDateTime(date) {
  return date.toISOString()
}

function startOfWeek(date) {
  const d = new Date(date)
  const day = d.getDay() || 7
  d.setDate(d.getDate() - day + 1)
  return d
}

function feedDateRangeParams(value) {
  const today = new Date()
  const start = new Date(today)
  const end = new Date(today)
  const rollingMinutes = {
    last_30_minutes: 30,
    last_hour: 60,
    last_2_hours: 120,
    last_5_hours: 300,
  }

  if (rollingMinutes[value]) {
    start.setTime(today.getTime() - rollingMinutes[value] * 60 * 1000)
    return { date_from: isoDateTime(start), date_to: isoDateTime(end) }
  }

  if (value === 'yesterday') {
    start.setDate(today.getDate() - 1)
    end.setDate(today.getDate() - 1)
  } else if (value === 'this_week') {
    const weekStart = startOfWeek(today)
    start.setTime(weekStart.getTime())
  } else if (value === 'last_week') {
    const weekStart = startOfWeek(today)
    start.setTime(weekStart.getTime())
    start.setDate(start.getDate() - 7)
    end.setTime(start.getTime())
    end.setDate(start.getDate() + 6)
  } else if (value === 'this_month') {
    start.setDate(1)
  } else if (value === 'last_month') {
    start.setMonth(today.getMonth() - 1, 1)
    end.setFullYear(start.getFullYear(), start.getMonth() + 1, 0)
  }

  return { date_from: isoDate(start), date_to: isoDate(end) }
}

function feedParams(type) {
  const accountParam = selectedAccount.value || undefined
  const isBuy = type === 'buy'
  const contact = isBuy ? buyContact.value : sellContact.value
  const dateParams = feedDateRangeParams(isBuy ? buyDateRange.value : sellDateRange.value)
  return {
    ...(accountParam ? { account: accountParam } : {}),
    status: selectedStatus.value,
    type,
    page: isBuy ? buyPage.value : sellPage.value,
    page_size: isBuy ? buyPageSize.value : sellPageSize.value,
    sort: isBuy ? buySort.value : sellSort.value,
    ...(contact ? { contact } : {}),
    ...dateParams,
  }
}

async function refresh() {
  const accountParam = selectedAccount.value || undefined
  const params = accountParam ? { account: accountParam } : {}
  const [statsRes, buyRes, sellRes, prodsRes] = await Promise.all([
    tradingApi.getStats(params),
    tradingApi.getOpenFeed(feedParams('buy')),
    tradingApi.getOpenFeed(feedParams('sell')),
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

async function loadBuyFeed() {
  buyLoading.value = true
  try {
    const { data } = await tradingApi.getOpenFeed(feedParams('buy'))
    buyFeed.value = data.results
    buyTotal.value = data.count
  } finally {
    buyLoading.value = false
  }
}

async function loadSellFeed() {
  sellLoading.value = true
  try {
    const { data } = await tradingApi.getOpenFeed(feedParams('sell'))
    sellFeed.value = data.results
    sellTotal.value = data.count
  } finally {
    sellLoading.value = false
  }
}

function resetFeedPagesAndRefresh() {
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

function setFeedSort(type) {
  if (type === 'buy') {
    buyPage.value = 1
    loadBuyFeed()
  } else {
    sellPage.value = 1
    loadSellFeed()
  }
}

function setFeedPageSize(type) {
  if (type === 'buy') {
    buyPage.value = 1
    loadBuyFeed()
  } else {
    sellPage.value = 1
    loadSellFeed()
  }
}

function setFeedContact(type) {
  if (type === 'buy') {
    buyPage.value = 1
    loadBuyFeed()
  } else {
    sellPage.value = 1
    loadSellFeed()
  }
}

function setFeedDateRange(type) {
  if (type === 'buy') {
    buyPage.value = 1
    buyContact.value = ''
    buyContactSearch.value = ''
    loadContactOptions('buy', { reset: true })
    loadBuyFeed()
  } else {
    sellPage.value = 1
    sellContact.value = ''
    sellContactSearch.value = ''
    loadContactOptions('sell', { reset: true })
    loadSellFeed()
  }
}

function changeFeedPage(type, page) {
  if (type === 'buy') {
    buyPage.value = Math.min(Math.max(1, page), buyTotalPages.value)
    loadBuyFeed()
  } else {
    sellPage.value = Math.min(Math.max(1, page), sellTotalPages.value)
    loadSellFeed()
  }
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

function marketWaLink(party) {
  const phone = party?.contact_phone
  if (!phone) return null
  const clean = phone.split('@')[0].replace(/\D/g, '')
  if (!clean) return null
  const text = party.original_text || ''
  const params = new URLSearchParams({ phone: clean })
  if (text) params.set('text', text)
  return `whatsapp://send?${params.toString()}`
}

function formatDateTime(value) {
  if (!value) return ''
  try {
    return new Date(value).toLocaleString()
  } catch {
    return ''
  }
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
  pollTimer = setInterval(refresh, 15000)
  freshnessTimer = setInterval(() => { nowTick.value = Date.now() }, 1000)
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
  if (freshnessTimer) clearInterval(freshnessTimer)
  document.removeEventListener('pointerdown', closeContactPickersOnOutsideClick)
  stopRowDialogDrag()
  stopMatchFixDrag()
  stopMarketDialogDrag()
})
</script>

<style scoped>
.trading-view { display: flex; flex-direction: column; height: 100%; overflow: hidden; background: #f9fafb; }
.trading-header { display: flex; flex-wrap: wrap; row-gap: 8px; justify-content: space-between; align-items: center; padding: 14px 20px; background: #fff; border-bottom: 1px solid #e5e7eb; }
.error-banner { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 8px 20px; background: #fee2e2; color: #991b1b; font-size: 0.85rem; border-bottom: 1px solid #fca5a5; }
.error-dismiss { background: none; border: none; color: #991b1b; cursor: pointer; font-size: 0.9rem; padding: 0 4px; }
.header-left { display: flex; align-items: center; gap: 10px; }
.header-left h2 { margin: 0; font-size: 1.15rem; }
.live-dot { width: 8px; height: 8px; border-radius: 50%; background: #22c55e; animation: blink 1.5s ease-in-out infinite; }
@keyframes blink { 0%,100% { opacity: 1; } 50% { opacity: 0.3; } }
.live-label { font-size: 0.8rem; color: #22c55e; font-weight: 600; }
.last-update { font-size: 0.78rem; color: #9ca3af; }
.header-right { display: flex; flex-wrap: wrap; row-gap: 8px; gap: 10px; align-items: center; }
.card-animation-control { display: flex; align-items: center; gap: 6px; font-size: 0.78rem; color: #4b5563; font-weight: 600; }
.account-select { padding: 5px 10px; border: 1px solid #d1d5db; border-radius: 6px; font-size: 0.85rem; }
.close-stale-control { display: flex; align-items: center; gap: 4px; }
.close-stale-input { width: 52px; padding: 5px 6px; border: 1px solid #d1d5db; border-radius: 6px; font-size: 0.85rem; }
.close-stale-msg { padding: 6px 20px; font-size: 0.8rem; color: #166534; background: #f0fdf4; border-bottom: 1px solid #bbf7d0; }
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
.feed-header { display: flex; align-items: center; justify-content: space-between; gap: 10px; padding: 10px 14px; border-bottom: 1px solid #e5e7eb; flex-wrap: wrap; }
.wtb-header { background: #f0fdf4; }
.wts-header { background: #fff7ed; }
.feed-heading { display: flex; align-items: center; gap: 10px; min-width: 140px; }
.feed-title { font-weight: 700; font-size: 0.85rem; letter-spacing: 0.05em; }
.feed-count { background: #e5e7eb; border-radius: 999px; padding: 1px 8px; font-size: 0.78rem; }
.feed-controls { display: flex; align-items: center; gap: 6px; margin-left: auto; }
.feed-control-select { height: 28px; border: 1px solid #d1d5db; border-radius: 6px; background: #fff; color: #374151; font-size: 0.78rem; padding: 2px 8px; }
.feed-control-input { height: 28px; border: 1px solid #d1d5db; border-radius: 6px; background: #fff; color: #374151; font-size: 0.78rem; padding: 2px 8px; }
.feed-control-select.compact { width: 72px; }
.contact-picker { position: relative; width: 170px; }
.contact-search { width: 100%; padding-right: 22px; }
.contact-clear-btn {
  position: absolute;
  right: 5px;
  top: 5px;
  border: 0;
  background: transparent;
  color: #9ca3af;
  cursor: pointer;
  font-size: 0.74rem;
  line-height: 1;
}
.contact-menu {
  position: absolute;
  z-index: 30;
  top: 32px;
  left: 0;
  width: 260px;
  max-height: 230px;
  overflow-y: auto;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.16);
  padding: 4px;
}
.contact-option {
  width: 100%;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 1px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: #111827;
  cursor: pointer;
  padding: 6px 8px;
  text-align: left;
  font-size: 0.78rem;
}
.contact-option:hover { background: #f3f4f6; }
.contact-option.muted { color: #6b7280; font-weight: 600; }
.contact-option-main { width: 100%; display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.contact-account-badge {
  max-width: 98px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  border-radius: 999px;
  background: #eef2ff;
  color: #4338ca;
  padding: 1px 7px;
  font-size: 0.64rem;
  font-weight: 700;
  flex-shrink: 0;
}
.contact-option small { color: #9ca3af; font-size: 0.68rem; }
.contact-loading { padding: 8px; color: #9ca3af; font-size: 0.74rem; text-align: center; }
.feed-list { flex: 1; overflow-y: auto; padding: 10px; display: flex; flex-direction: column; gap: 8px; }
.feed-card { background: #fff; border: 1px solid #e5e7eb; border-radius: 8px; padding: 12px; display: flex; flex-direction: column; height: 300px; transition: transform 0.32s ease, opacity 0.32s ease; }
.feed-card.sliding-left { transform: translateX(-120%); opacity: 0; }
.feed-card.sliding-right { transform: translateX(120%); opacity: 0; }
.feed-card.urgent { border-left: 3px solid #f59e0b; }
.card-header { flex-shrink: 0; padding-bottom: 8px; margin-bottom: 8px; border-bottom: 1px solid #f3f4f6; }
.card-body { flex: 1; min-height: 0; display: flex; flex-direction: column; gap: 3px; position: relative; }
.card-footer { flex-shrink: 0; padding-top: 8px; margin-top: 8px; border-top: 1px solid #f3f4f6; }
.card-top { display: flex; align-items: center; gap: 6px; flex-wrap: nowrap; }
.card-contact { font-weight: 600; font-size: 0.88rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; min-width: 0; flex-shrink: 1; }
.card-phone { font-weight: 400; font-size: 0.78rem; color: #6b7280; margin-left: 6px; }
.card-age { font-size: 0.78rem; color: #6b7280; flex-shrink: 0; white-space: nowrap; }
.card-age.red { color: #dc2626; font-weight: 700; }
.card-close-btn {
  width: 24px;
  height: 24px;
  border: 1px solid #fecaca;
  border-radius: 999px;
  background: #fef2f2;
  color: #dc2626;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  flex-shrink: 0;
  font-size: 0.76rem;
  line-height: 1;
}
.card-close-btn:hover:not(:disabled) { background: #fee2e2; border-color: #fca5a5; }
.card-close-btn:disabled { opacity: 0.45; cursor: not-allowed; }
.category-select-mini { padding: 2px 6px; border: 1px solid #d1d5db; border-radius: 5px; font-size: 0.72rem; color: #374151; cursor: pointer; background: #fff; flex-shrink: 0; }
.category-select-suggested { border-color: #fbbf24; background: #fffbeb; color: #92400e; font-weight: 600; }
.category-suggestion-chip { padding: 2px 8px; border: 1px solid #fbbf24; border-radius: 999px; font-size: 0.72rem; color: #92400e; background: #fef9c3; cursor: pointer; font-weight: 600; flex-shrink: 0; }
.category-suggestion-chip:hover { background: #fef08a; }
.body-row { flex: 1; min-height: 0; overflow: hidden; padding: 3px 6px; border-radius: 5px; cursor: pointer; transition: background-color 0.15s; }
.body-row:hover { background: #f9fafb; }
.body-row-label { font-size: 0.62rem; text-transform: uppercase; letter-spacing: 0.04em; color: #9ca3af; font-weight: 700; margin-bottom: 1px; }
.body-row-content { font-size: 0.8rem; color: #374151; line-height: 1.35; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.body-row-empty { color: #9ca3af; font-style: italic; }
.body-row.expanded { background: #eff6ff; }
.product-match-pending {
  margin: 4px 6px 0;
  padding: 6px 8px;
  border: 1px solid #fde68a;
  border-radius: 6px;
  background: #fffbeb;
  color: #92400e;
  font-size: 0.74rem;
  line-height: 1.35;
}
.source-label { font-size: 0.73rem; color: #9ca3af; text-transform: capitalize; white-space: nowrap; flex-shrink: 0; }
.account-badge { font-size: 0.7rem; background: #ede9fe; color: #6d28d9; padding: 1px 7px; border-radius: 999px; font-weight: 600; white-space: nowrap; flex-shrink: 0; }
.card-actions { display: flex; gap: 6px; align-items: center; }
.act-btn { padding: 4px 12px; border: none; border-radius: 5px; cursor: pointer; font-size: 0.8rem; font-weight: 500; }
.act-btn.close { background: #f3f4f6; color: #374151; }
.act-btn.close:disabled { opacity: 0.45; cursor: not-allowed; }
.act-btn.deal  { background: #16a34a; color: #fff; }
.act-btn.products { background: #eef2ff; color: #3730a3; }
.act-btn.market { background: #ecfeff; color: #0e7490; }
.act-btn.chat  { background: #eff6ff; color: #1d4ed8; margin-left: auto; }
.act-btn.wa    { background: #dcfce7; color: #16a34a; display: flex; align-items: center; gap: 3px; text-decoration: none; }
.act-btn.wa-ask { background: #fef9c3; color: #92400e; text-decoration: none; }
.act-btn.wa-list { background: #e0e7ff; color: #4338ca; text-decoration: none; }
.status-select-mini { padding: 4px 8px; border: 1px solid #d1d5db; border-radius: 5px; font-size: 0.78rem; color: #374151; cursor: pointer; background: #fff; }
.header-status-select {
  width: 118px;
  margin-left: auto;
  flex-shrink: 0;
  font-size: 0.72rem;
}
.rating-row { display: flex; align-items: center; gap: 4px; margin-top: 8px; }
.rating-label { font-size: 0.72rem; color: #9ca3af; margin-right: 2px; }
.rating-btn {
  width: 20px;
  height: 20px;
  border: 1px solid #d1d5db;
  border-radius: 4px;
  background: #fff;
  color: #9ca3af;
  font-size: 0.7rem;
  font-weight: 600;
  cursor: pointer;
  line-height: 1;
  padding: 0;
}
.rating-btn:hover { border-color: #9ca3af; color: #374151; }
.rating-btn.active { color: #fff; border-color: transparent; }
.rating-btn.active.low { background: #dc2626; }
.rating-btn.active.mid { background: #f59e0b; }
.rating-btn.active:not(.low):not(.mid) { background: #16a34a; }
.incorrect-match-form { display: flex; gap: 6px; align-items: center; margin-top: 6px; }
.incorrect-match-input { flex: 1; padding: 4px 8px; border: 1px solid #fca5a5; border-radius: 5px; font-size: 0.78rem; min-width: 0; }
.feed-empty { text-align: center; color: #9ca3af; font-size: 0.85rem; padding: 30px; }
.feed-pager { display: flex; align-items: center; justify-content: center; gap: 10px; color: #6b7280; font-size: 0.78rem; padding: 8px; border-top: 1px solid #e5e7eb; background: #fff; }
.feed-pager.inline { margin-top: 2px; border: 1px solid #e5e7eb; border-radius: 8px; }
.feed-page-label { min-width: 82px; text-align: center; }
.btn-ghost { padding: 6px 14px; border: 1px solid #d1d5db; border-radius: 6px; background: transparent; cursor: pointer; font-size: 0.85rem; }
.btn-ghost.sm { padding: 4px 10px; font-size: 0.8rem; }
/* Inventory stock hints on WTB cards */
.card-stock-hints { display: flex; flex-direction: column; gap: 3px; margin-bottom: 6px; }
.stock-hint { background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 5px; padding: 4px 8px; font-size: 0.75rem; color: #166534; line-height: 1.4; }
.stock-hint-mismatch { background: #fef9c3; border-color: #fde68a; color: #92400e; }
.stock-hint-out { background: #fff7ed; border-color: #fdba74; color: #9a3412; }
.mismatch-tag { font-weight: 700; }
.cost-loss { color: #dc2626; font-weight: 700; }
.stock-icon { color: #16a34a; font-weight: 700; margin-right: 3px; }
.stock-hint-mismatch .stock-icon { color: #d97706; }
.stock-hint-out .stock-icon { color: #ea580c; }
.stock-hint-actions { float: right; display: inline-flex; gap: 4px; }
.match-fix-btn {
  padding: 1px 9px;
  border: 1px solid #d97706;
  border-radius: 999px;
  font-size: 0.68rem;
  font-weight: 700;
  background: #fff;
  color: #b45309;
  cursor: pointer;
}
.match-fix-btn:hover { background: #fffbeb; }
.match-fix-btn.auto { border-color: #2563eb; color: #1d4ed8; }
.match-fix-btn.auto:hover { background: #eff6ff; }
.match-fix-btn.verify { border-color: #64748b; color: #334155; }
.match-fix-btn.verify:hover { background: #f8fafc; }
.match-fix-btn.create-inquiry { border-color: #16a34a; color: #15803d; }
.match-fix-btn.create-inquiry:hover { background: #f0fdf4; }
.match-fix-btn:disabled { opacity: 0.65; cursor: wait; }
.stock-create-error { clear: both; margin-top: 5px; color: #b91c1c; font-size: 0.72rem; font-weight: 700; }
.match-verify-result {
  clear: both;
  margin-top: 5px;
  padding: 4px 7px;
  border-radius: 4px;
  border: 1px solid #d1d5db;
  background: #f9fafb;
  color: #374151;
}
.match-verify-result.verdict-exact { background: #ecfdf5; border-color: #86efac; color: #166534; }
.match-verify-result.verdict-near { background: #fffbeb; border-color: #fcd34d; color: #92400e; }
.match-verify-result.verdict-incorrect { background: #fef2f2; border-color: #fca5a5; color: #b91c1c; }
.match-verify-result.verdict-unknown { background: #f8fafc; border-color: #cbd5e1; color: #475569; }
.inquiry-product-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 110;
  padding: 24px;
}
.inquiry-product-dialog {
  width: 860px;
  max-width: calc(100vw - 32px);
  max-height: calc(100vh - 64px);
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 14px 38px rgba(0,0,0,0.22);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.inquiry-product-header {
  padding: 16px 18px;
  border-bottom: 1px solid #e5e7eb;
  display: flex;
  justify-content: space-between;
  gap: 14px;
}
.inquiry-product-title { font-size: 0.95rem; font-weight: 700; color: #111827; }
.inquiry-product-subtitle { margin-top: 3px; font-size: 0.8rem; color: #6b7280; line-height: 1.4; }
.inquiry-product-state { padding: 32px; text-align: center; color: #6b7280; font-size: 0.88rem; }
.inquiry-product-error { margin: 14px 18px; padding: 9px 11px; border: 1px solid #fecaca; border-radius: 8px; background: #fef2f2; color: #b91c1c; font-size: 0.82rem; }
.inquiry-product-list { padding: 12px 18px 18px; overflow-y: auto; display: flex; flex-direction: column; gap: 9px; }
.inquiry-product-row { display: flex; justify-content: space-between; align-items: center; gap: 14px; padding: 11px; border: 1px solid #e5e7eb; border-radius: 9px; background: #fff; }
.inquiry-product-row.linked { background: #f0fdf4; border-color: #bbf7d0; }
.inquiry-product-main { min-width: 0; }
.inquiry-product-name { font-size: 0.88rem; font-weight: 700; color: #111827; }
.inquiry-product-meta { margin-top: 4px; display: flex; gap: 8px; flex-wrap: wrap; color: #6b7280; font-size: 0.75rem; }
.inquiry-product-linked { margin-top: 5px; color: #15803d; font-size: 0.78rem; font-weight: 600; }
.inquiry-product-actions { flex-shrink: 0; }
.linked-pill { background: #dcfce7; color: #166534; border-radius: 999px; padding: 3px 9px; font-size: 0.72rem; font-weight: 700; }
.match-fix-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}
.match-fix-dialog {
  width: 640px;
  max-width: calc(100vw - 32px);
  max-height: calc(100vh - 64px);
  background: #fff;
  border-radius: 10px;
  box-shadow: 0 10px 30px rgba(0,0,0,0.2);
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  overflow-y: auto;
}
.match-fix-header { display: flex; align-items: center; justify-content: space-between; gap: 12px; cursor: move; user-select: none; }
.match-fix-dialog-title { font-size: 0.85rem; font-weight: 600; color: #374151; }
.match-fix-close {
  border: none;
  background: transparent;
  font-size: 1.4rem;
  line-height: 1;
  color: #9ca3af;
  cursor: pointer;
  padding: 0 6px;
  border-radius: 4px;
  flex-shrink: 0;
}
.match-fix-close:hover { background: #f3f4f6; color: #374151; }
.match-fix-search {
  width: 100%;
  box-sizing: border-box;
  padding: 5px 8px;
  border: 1px solid #d1d5db;
  border-radius: 5px;
  font-size: 0.78rem;
  margin-bottom: 6px;
}
.match-fix-list { max-height: 360px; overflow-y: auto; display: flex; flex-direction: column; gap: 1px; }
.match-fix-row {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 4px;
  border-radius: 4px;
  font-size: 0.78rem;
  color: #374151;
  cursor: pointer;
}
.match-fix-row:hover { background: #f3f4f6; }
.match-fix-price { color: #6b7280; }
.match-fix-empty { text-align: center; color: #9ca3af; font-size: 0.78rem; padding: 8px; }
.match-fix-status { font-size: 0.75rem; color: #6b7280; text-align: center; padding: 4px 0; }
.match-fix-error { font-size: 0.75rem; color: #b91c1c; background: #fef2f2; border: 1px solid #fecaca; border-radius: 4px; padding: 4px 8px; }
.match-fix-section-label { font-size: 0.68rem; text-transform: uppercase; letter-spacing: 0.03em; color: #9ca3af; font-weight: 700; margin-top: 2px; }
.match-fix-source { margin-left: auto; font-size: 0.68rem; font-weight: 600; color: #16a34a; flex-shrink: 0; }
.match-fix-source.embedding { color: #2563eb; }
.market-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 95;
}
.market-dialog {
  width: min(980px, calc(100vw - 36px));
  max-height: calc(100vh - 54px);
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 18px 44px rgba(15, 23, 42, 0.28);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.market-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 16px 18px;
  border-bottom: 1px solid #e5e7eb;
  cursor: move;
  user-select: none;
}
.market-eyebrow {
  font-size: 0.68rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #0e7490;
  font-weight: 800;
}
.market-title {
  margin-top: 3px;
  font-size: 0.98rem;
  font-weight: 800;
  color: #111827;
}
.market-subtitle {
  margin-top: 3px;
  font-size: 0.78rem;
  color: #6b7280;
}
.market-body {
  padding: 14px 18px 18px;
  overflow-y: auto;
  min-height: 260px;
}
.market-source-tabs {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px;
  margin: 0 8px 12px 0;
  border: 1px solid #dbe4ef;
  border-radius: 999px;
  background: #f8fafc;
}
.market-source-tabs.method-tabs { background: #fff; }
.market-source-tab {
  border: 0;
  border-radius: 999px;
  padding: 6px 12px;
  background: transparent;
  color: #64748b;
  cursor: pointer;
  font-size: 0.78rem;
  font-weight: 800;
}
.market-source-tab.active {
  background: #0e7490;
  color: #fff;
}
.market-state {
  padding: 18px;
  border: 1px dashed #cbd5e1;
  border-radius: 10px;
  color: #64748b;
  background: #f8fafc;
  text-align: center;
  font-size: 0.84rem;
}
.market-state.compact {
  padding: 10px;
  text-align: left;
  font-size: 0.78rem;
}
.market-error {
  padding: 12px;
  border: 1px solid #fecaca;
  border-radius: 10px;
  color: #b91c1c;
  background: #fef2f2;
  font-size: 0.84rem;
}
.market-product-list { display: flex; flex-direction: column; gap: 12px; }
.market-product {
  border: 1px solid #dbe4ef;
  border-radius: 12px;
  overflow: hidden;
  background: #fff;
}
.market-product-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 11px 13px;
  background: #f8fafc;
  border-bottom: 1px solid #e5e7eb;
}
.market-product-name { font-weight: 800; color: #111827; }
.market-product-meta { margin-top: 2px; font-size: 0.73rem; color: #64748b; }
.market-count {
  min-width: 28px;
  height: 24px;
  padding: 0 8px;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: #cffafe;
  color: #0e7490;
  font-size: 0.78rem;
  font-weight: 800;
}
.market-party-list { display: flex; flex-direction: column; }
.market-party {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
  padding: 12px 13px;
  border-top: 1px solid #f1f5f9;
}
.market-party:first-child { border-top: 0; }
.market-party-main { min-width: 0; flex: 1; }
.market-party-name { font-weight: 800; color: #111827; }
.market-party-meta,
.market-party-facts {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 2px;
  color: #64748b;
  font-size: 0.74rem;
}
.market-party-text {
  margin-top: 6px;
  color: #334155;
  font-size: 0.8rem;
  line-height: 1.35;
  white-space: pre-wrap;
}
.market-party-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}
.row-expand-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 90;
}
.row-expand-dialog {
  width: 1040px;
  min-height: 400px;
  max-width: calc(100vw - 32px);
  max-height: calc(100vh - 64px);
  background: #fff;
  border-radius: 10px;
  box-shadow: 0 10px 30px rgba(0,0,0,0.25);
  padding: 18px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.row-expand-header { display: flex; align-items: center; justify-content: space-between; gap: 12px; cursor: move; user-select: none; }
.row-expand-title { font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.04em; color: #9ca3af; font-weight: 700; }
.row-expand-close {
  border: none;
  background: transparent;
  font-size: 1.4rem;
  line-height: 1;
  color: #9ca3af;
  cursor: pointer;
  padding: 0 6px;
  border-radius: 4px;
}
.row-expand-close:hover { background: #f3f4f6; color: #374151; }
.row-expand-content { font-size: 0.9rem; color: #374151; line-height: 1.5; overflow-y: auto; white-space: pre-wrap; flex: 1; min-height: 0; }
</style>
