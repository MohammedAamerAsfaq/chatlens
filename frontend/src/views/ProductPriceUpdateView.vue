<template>
  <div class="ppu-view">
    <div class="page-header">
      <div>
        <h2>Product Price Update</h2>
        <p class="subtitle">
          Two independent AI matching processes, each against your own inventory —
          keeps supplier qty/cost lists and external sale-price lists from being
          mixed together, since they come from different parties with different
          naming conventions.
          <RouterLink to="/ai-instructions" class="edit-prompt-link">Edit AI instructions →</RouterLink>
        </p>
      </div>
      <div class="page-tabs">
        <button :class="['page-tab', activeTab === 'qty_cost' && 'active']" @click="activeTab = 'qty_cost'">Qty &amp; Cost</button>
        <button :class="['page-tab', activeTab === 'sale_price' && 'active']" @click="activeTab = 'sale_price'">Sale Price</button>
      </div>
    </div>

    <!-- ── QTY & COST PROCESS ──────────────────────────────────────────── -->
    <div v-if="activeTab === 'qty_cost'" class="process-card">
      <div class="tab-bar">
        <button :class="['tab-btn', qtyCost.step === 'input' && 'active']" @click="qtyCost.step = 'input'">Input</button>
        <button :class="['tab-btn', qtyCost.step === 'review' && 'active']" :disabled="!qtyCost.preview.length" @click="qtyCost.step = 'review'">
          Review{{ qtyCost.preview.length ? ` (${qtyCost.preview.length})` : '' }}
        </button>
      </div>

      <template v-if="qtyCost.step === 'input'">
        <div class="form-group">
          <label>Supplier stock list <span class="hint">— product names with quantity and/or cost price, worded however the supplier wrote them</span></label>
          <textarea v-model="qtyCost.text" class="bulk-textarea" rows="12"
            placeholder="iPhone 17 Pro 256GB Silver Japan  50 units  cost 850 USD&#10;Samsung S25 Ultra 512GB  30 pcs  @780&#10;AirPods Pro 4  100  cost 180" />
        </div>
        <div v-if="qtyCost.error" class="bulk-error">{{ qtyCost.error }}</div>
      </template>

      <template v-else>
        <div class="preview-header">
          <span>{{ qtyCost.preview.length }} items — edit before applying:</span>
          <button class="btn-ghost btn-sm" @click="qtyCost.step = 'input'">← Back</button>
        </div>
        <div class="preview-table-wrap">
          <table class="data-table preview-table">
            <thead>
              <tr>
                <th>Product</th>
                <th>Matched</th>
                <th style="width:80px">Qty</th>
                <th style="width:100px">Cost</th>
                <th style="width:80px">Currency</th>
                <th style="width:32px"></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(item, i) in qtyCost.preview" :key="i" :class="{ 'row-unmatched': !item.product_id }">
                <td><input v-model="item.canonical_name" class="inline-input" /></td>
                <td>
                  <span v-if="item.product_id" class="match-chip">ID {{ item.product_id }}</span>
                  <span v-else class="no-match-chip">unmatched</span>
                </td>
                <td><input v-model.number="item.qty" class="inline-input" type="number" min="0" /></td>
                <td><input v-model.number="item.cost_price" class="inline-input" type="number" step="0.01" /></td>
                <td><input v-model="item.currency" class="inline-input" /></td>
                <td><button class="btn-sm danger" @click="qtyCost.preview.splice(i, 1)">✕</button></td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-if="qtyCost.result" class="bulk-result">
          ✓ {{ qtyCost.result.updated.length }} updated
          <span v-if="qtyCost.result.skipped.length">
            · {{ qtyCost.result.skipped.length }} skipped (not found): {{ qtyCost.result.skipped.join(', ') }}
          </span>
          <span v-if="qtyCost.result.zeroed && qtyCost.result.zeroed.length">
            · {{ qtyCost.result.zeroed.length }} not in this list, qty set to 0: {{ qtyCost.result.zeroed.map(p => p.name).join(', ') }}
          </span>
        </div>
      </template>

      <div class="process-foot">
        <span v-if="qtyCost.step === 'input' && qtyCost.text.trim()" class="token-pill">
          ~{{ Math.round(qtyCost.text.length / 4).toLocaleString() }} tokens
          <span v-if="agentPricing.input_price_per_1m">
            · ~${{ ((qtyCost.text.length / 4 / 1_000_000) * agentPricing.input_price_per_1m).toFixed(6) }}
          </span>
        </span>
        <span v-else class="foot-spacer" />
        <div class="foot-actions">
          <button v-if="qtyCost.step === 'input'" class="btn-primary"
            :disabled="qtyCost.parsing || !qtyCost.text.trim()"
            @click="parseQtyCost">
            {{ qtyCost.parsing ? 'Parsing…' : 'Parse with AI' }}
          </button>
          <button v-else class="btn-primary"
            :disabled="qtyCost.applying || !qtyCost.preview.length"
            @click="applyQtyCost">
            {{ qtyCost.applying ? 'Applying…' : `Apply ${qtyCost.preview.length} updates` }}
          </button>
        </div>
      </div>
    </div>

    <!-- ── SALE PRICE PROCESS ──────────────────────────────────────────── -->
    <div v-if="activeTab === 'sale_price'" class="process-card">
      <div class="tab-bar">
        <button :class="['tab-btn', salePrice.step === 'input' && 'active']" @click="salePrice.step = 'input'">Input</button>
        <button :class="['tab-btn', salePrice.step === 'review' && 'active']" :disabled="!salePrice.preview.length" @click="salePrice.step = 'review'">
          Review{{ salePrice.preview.length ? ` (${salePrice.preview.length})` : '' }}
        </button>
      </div>

      <template v-if="salePrice.step === 'input'">
        <div class="form-group">
          <label>External price list <span class="hint">— product names with selling prices, worded however that source wrote them</span></label>
          <textarea v-model="salePrice.text" class="bulk-textarea" rows="12"
            placeholder="iPhone 17 Pro 256GB Silver Japan  950 USD&#10;Samsung S25 Ultra 512GB  890&#10;AirPods Pro 4  210" />
        </div>
        <div v-if="salePrice.error" class="bulk-error">{{ salePrice.error }}</div>
      </template>

      <template v-else>
        <div class="preview-header">
          <span>{{ salePrice.preview.length }} items — edit before applying:</span>
          <button class="btn-ghost btn-sm" @click="salePrice.step = 'input'">← Back</button>
        </div>
        <div class="preview-table-wrap">
          <table class="data-table preview-table">
            <thead>
              <tr>
                <th>Product</th>
                <th>Matched</th>
                <th style="width:100px">Sale Price</th>
                <th style="width:80px">Currency</th>
                <th style="width:32px"></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(item, i) in salePrice.preview" :key="i" :class="{ 'row-unmatched': !item.product_id }">
                <td><input v-model="item.canonical_name" class="inline-input" /></td>
                <td>
                  <span v-if="item.product_id" class="match-chip">ID {{ item.product_id }}</span>
                  <span v-else class="no-match-chip">unmatched</span>
                </td>
                <td><input v-model.number="item.sale_price" class="inline-input" type="number" step="0.01" /></td>
                <td><input v-model="item.currency" class="inline-input" /></td>
                <td><button class="btn-sm danger" @click="salePrice.preview.splice(i, 1)">✕</button></td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-if="salePrice.result" class="bulk-result">
          ✓ {{ salePrice.result.updated.length }} updated
          <span v-if="salePrice.result.skipped.length">
            · {{ salePrice.result.skipped.length }} skipped (not found): {{ salePrice.result.skipped.join(', ') }}
          </span>
        </div>
      </template>

      <div class="process-foot">
        <span v-if="salePrice.step === 'input' && salePrice.text.trim()" class="token-pill">
          ~{{ Math.round(salePrice.text.length / 4).toLocaleString() }} tokens
          <span v-if="agentPricing.input_price_per_1m">
            · ~${{ ((salePrice.text.length / 4 / 1_000_000) * agentPricing.input_price_per_1m).toFixed(6) }}
          </span>
        </span>
        <span v-else class="foot-spacer" />
        <div class="foot-actions">
          <button v-if="salePrice.step === 'input'" class="btn-primary"
            :disabled="salePrice.parsing || !salePrice.text.trim()"
            @click="parseSalePrice">
            {{ salePrice.parsing ? 'Parsing…' : 'Parse with AI' }}
          </button>
          <button v-else class="btn-primary"
            :disabled="salePrice.applying || !salePrice.preview.length"
            @click="applySalePrice">
            {{ salePrice.applying ? 'Applying…' : `Apply ${salePrice.preview.length} updates` }}
          </button>
        </div>
      </div>

      <!-- ── AUTOMATED PRICE UPDATES ─────────────────────────────────────── -->
      <div class="automation-section">
        <div class="section-eyebrow"><span class="accent-mark"></span><span>Automated — Sale Price only</span></div>
        <div class="section-title-row"><h3>Automated Price Updates</h3></div>
        <p class="section-desc">Watch specific contacts or groups for incoming price lists. Matching messages are captured automatically and sent into this Sale Price process.</p>

        <div class="summary-strip">
          <div class="summary-cell"><div class="summary-num accent">{{ automationSummary.active_rules }}</div><div class="summary-label">Active rules</div></div>
          <div class="summary-cell"><div class="summary-num">{{ automationSummary.watched_sources }}</div><div class="summary-label">Watched sources</div></div>
          <div class="summary-cell"><div class="summary-num">{{ automationSummary.captured_this_week }}</div><div class="summary-label">Captured this week</div></div>
          <div class="summary-cell"><div class="summary-num">{{ automationSummary.queued }}</div><div class="summary-label">Waiting for review</div></div>
        </div>

        <div v-if="!automationRules.length && !ruleForm" class="empty-msg">No automation rules yet.</div>

        <div class="rules-list">
          <div v-for="rule in automationRules" :key="rule.id" class="rule-card" :class="{ paused: !rule.is_active }">
            <div class="rule-top">
              <div class="rule-name-group">
                <span class="rule-name">{{ rule.name }}</span>
                <span :class="['status-pill', rule.is_active ? 'on' : 'off']"><span class="dot"></span>{{ rule.is_active ? 'Active' : 'Paused' }}</span>
              </div>
              <div class="rule-actions">
                <button class="icon-btn" title="Edit" @click="editRule(rule)">✎</button>
                <button class="icon-btn" title="Pause/Resume" @click="toggleRule(rule)">{{ rule.is_active ? '⏸' : '▶' }}</button>
                <button class="icon-btn" title="Delete" @click="deleteRule(rule)">🗑</button>
              </div>
            </div>
            <div class="rule-grid">
              <div>
                <div class="rule-field-label">Watching</div>
                <div class="chip-row">
                  <span v-for="s in rule.sources" :key="s.id" :class="['chip', s.source_type === 'group' && 'group', s.source_type === 'contact_in_group' && 'in-group']">
                    <span class="chip-kind">{{ s.source_type === 'contact' ? 'DM' : s.source_type === 'group' ? 'Group' : 'In group' }}</span>
                    <template v-if="s.source_type === 'group'">
                      {{ s.group_name }}
                      <span v-if="s.group_account_name" class="chip-account">{{ s.group_account_name }}</span>
                    </template>
                    <template v-else>
                      {{ s.contact_name }}
                      <span v-if="s.contact_account_name" class="chip-account">{{ s.contact_account_name }}</span>
                      <span v-if="s.source_type === 'contact_in_group'" class="via-group">
                        → {{ s.group_name }}
                        <span v-if="s.group_account_name" class="chip-account">{{ s.group_account_name }}</span>
                      </span>
                    </template>
                  </span>
                  <span v-if="!rule.sources.length" class="muted">no sources</span>
                </div>
              </div>
              <div>
                <div class="rule-field-label">Trigger when</div>
                <div class="cond-list">
                  <div v-if="!rule.trigger_heading && !rule.trigger_ai_detect" class="cond-item"><span class="cond-value">any message</span></div>
                  <div v-if="rule.trigger_heading" class="cond-item"><span class="cond-op">has</span><span class="cond-value mono">"{{ rule.trigger_heading }}"</span></div>
                  <div v-if="rule.trigger_ai_detect" class="cond-item ai"><span class="cond-op">{{ rule.trigger_heading ? 'or' : 'if' }}</span><span class="cond-value">🤖 looks like a price list</span></div>
                </div>
              </div>
              <div>
                <div class="rule-field-label">On match</div>
                <span :class="['action-mode', rule.action_mode]">
                  {{ rule.action_mode === 'auto' ? '⚡ Auto-apply' : rule.action_mode === 'test' ? '🧪 Test rule' : '📥 Send for review' }}
                </span>
              </div>
            </div>
            <div class="rule-meta">
              {{ rule.last_triggered_at ? `Last triggered ${formatDate(rule.last_triggered_at)}` : 'Never triggered' }}
              · {{ rule.trigger_count }} message{{ rule.trigger_count === 1 ? '' : 's' }} captured total
            </div>
          </div>
        </div>

        <button v-if="!ruleForm" class="add-rule-btn" @click="openNewRule">+ Add automation rule</button>

        <!-- Add / edit rule form -->
        <div v-if="ruleForm" class="form-panel">
          <div class="form-panel-head">
            <h4>{{ ruleForm.id ? 'Edit rule' : 'New automation rule' }}</h4>
            <span class="close-x" @click="closeRuleForm">✕</span>
          </div>

          <div class="form-row single">
            <div class="field">
              <label>Rule name</label>
              <input v-model="ruleForm.name" class="fake-input-real" placeholder='e.g. "Expert Devices — supplier price lists"' />
            </div>
          </div>

          <div class="field">
            <label>Watch these sources</label>
            <span class="field-hint" style="display:block; margin: -2px 0 12px;">Three independent ways to add a source — combine any of them in one rule.</span>

            <div class="source-options">
              <div class="source-option">
                <div class="source-option-head"><span class="source-option-icon">💬</span><span class="source-option-title">Contact (direct messages)</span></div>
                <div class="source-option-body">
                  <input v-model="contactQuery" @input="searchContacts" class="fake-input-real" placeholder="Search a contact…" />
                  <div v-if="contactOptions.length" class="search-results">
                    <div v-for="c in contactOptions" :key="c.id" class="search-result" @click="addContactSource(c)">
                      <span>{{ contactLabel(c) }}</span>
                      <span class="search-result-account">{{ accountName(c.account_id) }}</span>
                    </div>
                  </div>
                </div>
              </div>

              <div class="source-option">
                <div class="source-option-head"><span class="source-option-icon">▤</span><span class="source-option-title">Group (any member)</span></div>
                <div class="source-option-body">
                  <input v-model="groupQuery" @input="searchGroups" class="fake-input-real" placeholder="Search a group…" />
                  <div v-if="groupOptions.length" class="search-results">
                    <div v-for="g in groupOptions" :key="g.id" class="search-result" @click="addGroupSource(g)">
                      <span>{{ g.name }}</span>
                      <span class="search-result-account">{{ accountName(g.account_id) }}</span>
                    </div>
                  </div>
                </div>
              </div>

              <div class="source-option" :class="{ active: igSelectedGroup }">
                <div class="source-option-head"><span class="source-option-icon">🎯</span><span class="source-option-title">Specific people in a group</span></div>
                <div class="source-option-body">
                  <div class="in-group-row">
                    <span class="igp-label">In</span>
                    <input v-if="!igSelectedGroup" v-model="igGroupQuery" @input="searchIgGroups" class="fake-input-real" placeholder="Search group…" style="flex:1" />
                    <span v-else class="fake-select">{{ igSelectedGroup.name }} <span class="x" @click="igSelectedGroup = null">✕</span></span>
                  </div>
                  <div v-if="igGroupOptions.length && !igSelectedGroup" class="search-results">
                    <div v-for="g in igGroupOptions" :key="g.id" class="search-result" @click="selectIgGroup(g)">
                      <span>{{ g.name }}</span>
                      <span class="search-result-account">{{ accountName(g.account_id) }}</span>
                    </div>
                  </div>
                  <div v-if="igSelectedGroup" class="in-group-row" style="margin-top: 8px;">
                    <span class="igp-label">listen only to</span>
                    <input v-model="igContactQuery" @input="searchIgContacts" class="fake-input-real" placeholder="Search contact…" style="flex:1" />
                  </div>
                  <div v-if="igContactOptions.length" class="search-results">
                    <div v-for="c in igContactOptions" :key="c.id" class="search-result" @click="addContactInGroupSource(c)">
                      <span>{{ contactLabel(c) }}</span>
                      <span class="search-result-account">{{ accountName(c.account_id) }}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div class="rule-field-label" style="margin-top: 16px;">Currently watching</div>
            <div class="chip-row watching-row">
              <span v-for="(s, i) in ruleForm.sources" :key="i" :class="['chip', s.source_type === 'group' && 'group', s.source_type === 'contact_in_group' && 'in-group']">
                <span class="chip-kind">{{ s.source_type === 'contact' ? 'DM' : s.source_type === 'group' ? 'Group' : 'In group' }}</span>
                <template v-if="s.source_type === 'group'">
                  {{ s.group_name }}
                  <span v-if="s.group_account_name" class="chip-account">{{ s.group_account_name }}</span>
                </template>
                <template v-else>
                  {{ s.contact_name }}
                  <span v-if="s.contact_account_name" class="chip-account">{{ s.contact_account_name }}</span>
                  <span v-if="s.source_type === 'contact_in_group'" class="via-group">
                    → {{ s.group_name }}
                    <span v-if="s.group_account_name" class="chip-account">{{ s.group_account_name }}</span>
                  </span>
                </template>
                <span class="x" @click="ruleForm.sources.splice(i, 1)">✕</span>
              </span>
              <span v-if="!ruleForm.sources.length" class="muted">none added yet</span>
            </div>
          </div>

          <div class="form-row" style="margin-top: 18px;">
            <div class="field">
              <label>Trigger heading (optional)</label>
              <input v-model="ruleForm.trigger_heading" class="fake-input-real" placeholder='e.g. "PRICE LIST"' />
              <span class="field-hint">Case-insensitive match anywhere in the message.</span>
            </div>
            <div class="field">
              <label class="checkbox-field-real">
                <input type="checkbox" v-model="ruleForm.trigger_ai_detect" />
                🤖 Also detect automatically
              </label>
              <span class="field-hint">Lets the AI parse itself decide — matches if it finds real priced products, even with no heading. Combines with heading via OR.</span>
            </div>
          </div>

          <div class="form-row single">
            <div class="field">
              <label>On match</label>
              <div class="segmented">
                <button :class="{ sel: ruleForm.action_mode === 'review' }" @click="ruleForm.action_mode = 'review'">Send for review</button>
                <button :class="{ sel: ruleForm.action_mode === 'auto' }" @click="ruleForm.action_mode = 'auto'">Auto-apply</button>
                <button :class="{ sel: ruleForm.action_mode === 'test' }" @click="ruleForm.action_mode = 'test'">🧪 Test rule</button>
              </div>
              <span class="field-hint">
                Review queues it below; auto-apply updates prices with no confirmation step; test rule never touches
                inventory or needs review — it just confirms in Recent detections that this rule fires correctly.
              </span>
            </div>
          </div>

          <div v-if="ruleFormError" class="bulk-error">{{ ruleFormError }}</div>

          <div class="form-actions">
            <button class="btn-ghost-fake" @click="closeRuleForm">Cancel</button>
            <button class="btn-primary-fake" :disabled="ruleSaving" @click="saveRule">{{ ruleSaving ? 'Saving…' : 'Save rule' }}</button>
          </div>
        </div>

        <div class="section-eyebrow" style="margin-top: 30px;"><span class="accent-mark"></span><span>Live</span></div>
        <div class="section-title-row"><h3>Recent detections</h3></div>
        <p class="section-desc">Every message a rule matched, and what happened to it.</p>

        <div class="capture-filter-bar">
          <button :class="['filter-chip', captureFilter === '' && 'sel']" @click="filterCaptures('')">All</button>
          <button :class="['filter-chip', captureFilter === 'queued' && 'sel']" @click="filterCaptures('queued')">Awaiting review</button>
          <button :class="['filter-chip', captureFilter === 'applied' && 'sel']" @click="filterCaptures('applied')">Applied</button>
          <button :class="['filter-chip', captureFilter === 'ignored' && 'sel']" @click="filterCaptures('ignored')">Ignored</button>
          <button :class="['filter-chip', captureFilter === 'test' && 'sel']" @click="filterCaptures('test')">🧪 Test matches</button>
        </div>

        <div class="capture-list-toolbar">
          <span>{{ captureRangeText() }}</span>
          <div class="capture-pager">
            <span>Rows:</span>
            <button
              v-for="size in capturePageSizes"
              :key="size"
              :class="['page-size-btn', capturePageSize === size && 'active']"
              @click="setCapturePageSize(size)"
            >
              {{ size }}
            </button>
            <button class="pager-btn" :disabled="capturePage <= 1 || captureLoading" @click="setCapturePage(capturePage - 1)">Previous</button>
            <span class="pager-label">Page {{ capturePage }} of {{ captureTotalPages() }}</span>
            <button class="pager-btn" :disabled="capturePage >= captureTotalPages() || captureLoading" @click="setCapturePage(capturePage + 1)">Next</button>
          </div>
        </div>

        <div v-if="captureLoading" class="empty-msg">Loading detections...</div>
        <div v-else-if="!captures.length" class="empty-msg">No detections yet.</div>
        <div v-else class="feed-list">
          <div v-for="cap in captures" :key="cap.id" class="feed-row">
            <div :class="['feed-avatar', cap.source_kind === 'group' && 'group']">{{ (cap.source_name || '?').charAt(0).toUpperCase() }}</div>
            <div class="feed-main">
              <div class="feed-source">
                {{ cap.source_name }}
                <span v-if="cap.source_kind === 'group'" class="feed-dim">in {{ cap.group_name }}</span>
                <span class="feed-dim">· matched "{{ cap.rule_name || 'deleted rule' }}"</span>
              </div>
              <div class="feed-snippet">{{ cap.message_text }}</div>
            </div>
            <div class="feed-meta">{{ formatDate(cap.message_time) }}</div>
            <div class="feed-actions">
              <template v-if="cap.status === 'queued'">
                <button class="btn-sm" @click="applyCapture(cap)">Apply ({{ cap.items.length }})</button>
                <button class="btn-sm danger" @click="ignoreCapture(cap)">Ignore</button>
              </template>
              <span v-else :class="['feed-outcome', cap.status]">
                {{ cap.status === 'applied' ? `Applied · ${cap.items.length} updated`
                   : cap.status === 'test' ? `🧪 Rule works · ${cap.items.length} would update`
                   : 'Ignored' }}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import { tradingApi, contactsApi, groupsApi, accountsApi } from '../api/index.js'

const activeTab = ref('qty_cost')
const accounts  = ref([])

// Contact/group search results can span multiple WhatsApp accounts with similarly
// named contacts — shown next to each result so it's unambiguous which one you're
// picking, matching by account_id rather than assuming a single-account setup.
function accountName(accountId) {
  const a = accounts.value.find(x => x.id === accountId)
  return a ? (a.display_name || a.phone_number || `Account ${a.id}`) : ''
}

// WhatsApp's own name for the contact (push_name) leads, with the locally
// saved/edited name (display_name) in brackets when it differs —
// e.g. "Laeeq Bhai Dubai (Laeeq Ahmed)".
function contactLabel(c) {
  const whatsappName = c.push_name || c.phone_number || c.wa_contact_id
  const savedName = c.display_name
  if (savedName && savedName !== whatsappName) return `${whatsappName} (${savedName})`
  return whatsappName
}
const agentPricing = ref({ input_price_per_1m: null })

function formatDate(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

function debounce(fn, delay = 300) {
  let t
  return (...args) => {
    clearTimeout(t)
    t = setTimeout(() => fn(...args), delay)
  }
}

// ── Automated Price Updates ─────────────────────────────────────────────────
const automationSummary = ref({ active_rules: 0, watched_sources: 0, captured_this_week: 0, queued: 0 })
const automationRules   = ref([])
const captures          = ref([])
const captureFilter     = ref('')
const captureLoading    = ref(false)
const captureCount      = ref(0)
const capturePage       = ref(1)
const capturePageSize   = ref(10)
const capturePageSizes  = [10, 25, 50, 100]

const ruleForm      = ref(null)
const ruleFormError = ref('')
const ruleSaving    = ref(false)

function emptyRuleForm() {
  return {
    id: null, name: '', trigger_heading: '', trigger_ai_detect: false,
    action_mode: 'review', sources: [],
  }
}

async function loadAutomation() {
  const [rulesRes, summaryRes] = await Promise.all([
    tradingApi.listAutomationRules(),
    tradingApi.captureSummary(),
  ])
  automationRules.value = rulesRes.data.results || rulesRes.data
  automationSummary.value = summaryRes.data
  await loadCaptures()
}

async function loadAutomationSummary() {
  const { data } = await tradingApi.captureSummary()
  automationSummary.value = data
}

async function loadCaptures() {
  captureLoading.value = true
  try {
    const params = {
      page: capturePage.value,
      page_size: capturePageSize.value,
    }
    if (captureFilter.value) params.status = captureFilter.value
    const { data } = await tradingApi.listPriceCaptures(params)
    captures.value = data.results || data
    captureCount.value = data.count ?? captures.value.length
    const totalPages = captureTotalPages()
    if (!captures.value.length && captureCount.value && capturePage.value > totalPages) {
      capturePage.value = totalPages
      await loadCaptures()
    }
  } finally {
    captureLoading.value = false
  }
}

function captureTotalPages() {
  return Math.max(1, Math.ceil(captureCount.value / capturePageSize.value))
}

function captureRangeText() {
  if (!captureCount.value) return 'Showing 0 detections'
  const start = ((capturePage.value - 1) * capturePageSize.value) + 1
  const end = Math.min(capturePage.value * capturePageSize.value, captureCount.value)
  return `Showing ${start}-${end} of ${captureCount.value.toLocaleString()}`
}

function setCapturePage(page) {
  const next = Math.min(Math.max(1, page), captureTotalPages())
  if (next === capturePage.value) return
  capturePage.value = next
  loadCaptures()
}

function setCapturePageSize(size) {
  capturePageSize.value = Number(size)
  capturePage.value = 1
  loadCaptures()
}

function filterCaptures(statusVal) {
  captureFilter.value = statusVal
  capturePage.value = 1
  loadCaptures()
}

function openNewRule() {
  ruleForm.value = emptyRuleForm()
  ruleFormError.value = ''
  resetPickers()
}

function editRule(rule) {
  ruleForm.value = {
    id: rule.id,
    name: rule.name,
    trigger_heading: rule.trigger_heading,
    trigger_ai_detect: rule.trigger_ai_detect,
    action_mode: rule.action_mode,
    sources: rule.sources.map(s => ({
      source_type: s.source_type,
      contact_id: s.contact, contact_name: s.contact_name, contact_account_name: s.contact_account_name,
      group_id: s.group, group_name: s.group_name, group_account_name: s.group_account_name,
    })),
  }
  ruleFormError.value = ''
  resetPickers()
}

function closeRuleForm() {
  ruleForm.value = null
}

function resetPickers() {
  contactQuery.value = ''; contactOptions.value = []
  groupQuery.value = ''; groupOptions.value = []
  igGroupQuery.value = ''; igGroupOptions.value = []; igSelectedGroup.value = null
  igContactQuery.value = ''; igContactOptions.value = []
}

async function saveRule() {
  if (!ruleForm.value.name.trim()) {
    ruleFormError.value = 'Rule name is required.'
    return
  }
  if (!ruleForm.value.sources.length) {
    ruleFormError.value = 'Add at least one contact or group to watch.'
    return
  }
  ruleSaving.value = true
  ruleFormError.value = ''
  try {
    const payload = {
      name: ruleForm.value.name.trim(),
      trigger_heading: ruleForm.value.trigger_heading.trim(),
      trigger_ai_detect: ruleForm.value.trigger_ai_detect,
      action_mode: ruleForm.value.action_mode,
      sources: ruleForm.value.sources.map(s => ({
        source_type: s.source_type, contact_id: s.contact_id, group_id: s.group_id,
      })),
    }
    if (ruleForm.value.id) {
      await tradingApi.updateAutomationRule(ruleForm.value.id, payload)
    } else {
      await tradingApi.createAutomationRule(payload)
    }
    ruleForm.value = null
    await loadAutomation()
  } catch (e) {
    ruleFormError.value = e.response?.data?.detail || e.message || 'Failed to save rule'
  } finally {
    ruleSaving.value = false
  }
}

async function toggleRule(rule) {
  await tradingApi.toggleAutomationRule(rule.id)
  await loadAutomation()
}

async function deleteRule(rule) {
  if (!confirm(`Delete rule "${rule.name}"?`)) return
  await tradingApi.deleteAutomationRule(rule.id)
  await loadAutomation()
}

async function applyCapture(cap) {
  await tradingApi.applyPriceCapture(cap.id)
  await Promise.all([loadAutomationSummary(), loadCaptures()])
}

async function ignoreCapture(cap) {
  await tradingApi.ignorePriceCapture(cap.id)
  await Promise.all([loadAutomationSummary(), loadCaptures()])
}

// Source pickers — three independent search-and-add mechanisms feeding the same
// ruleForm.sources list.
const contactQuery   = ref('')
const contactOptions = ref([])
const searchContacts = debounce(async () => {
  const q = contactQuery.value.trim()
  if (!q) { contactOptions.value = []; return }
  const { data } = await contactsApi.list({ search: q })
  contactOptions.value = (data.results || data || []).slice(0, 8)
})

function addContactSource(c) {
  const name = contactLabel(c)
  if (!ruleForm.value.sources.some(s => s.source_type === 'contact' && s.contact_id === c.id)) {
    ruleForm.value.sources.push({ source_type: 'contact', contact_id: c.id, contact_name: name, contact_account_name: accountName(c.account_id) })
  }
  contactQuery.value = ''
  contactOptions.value = []
}

const groupQuery   = ref('')
const groupOptions = ref([])
const searchGroups = debounce(async () => {
  const q = groupQuery.value.trim()
  if (!q) { groupOptions.value = []; return }
  const { data } = await groupsApi.list({ search: q })
  groupOptions.value = (data.results || data || []).slice(0, 8)
})

function addGroupSource(g) {
  if (!ruleForm.value.sources.some(s => s.source_type === 'group' && s.group_id === g.id)) {
    ruleForm.value.sources.push({ source_type: 'group', group_id: g.id, group_name: g.name, group_account_name: accountName(g.account_id) })
  }
  groupQuery.value = ''
  groupOptions.value = []
}

const igGroupQuery    = ref('')
const igGroupOptions  = ref([])
const igSelectedGroup = ref(null)
const searchIgGroups  = debounce(async () => {
  const q = igGroupQuery.value.trim()
  if (!q) { igGroupOptions.value = []; return }
  const { data } = await groupsApi.list({ search: q })
  igGroupOptions.value = (data.results || data || []).slice(0, 8)
})

function selectIgGroup(g) {
  igSelectedGroup.value = g
  igGroupOptions.value = []
}

const igContactQuery   = ref('')
const igContactOptions = ref([])
const searchIgContacts = debounce(async () => {
  const q = igContactQuery.value.trim()
  if (!q) { igContactOptions.value = []; return }
  const params = { search: q }
  if (igSelectedGroup.value) params.account = igSelectedGroup.value.account_id
  const { data } = await contactsApi.list(params)
  igContactOptions.value = (data.results || data || []).slice(0, 8)
})

function addContactInGroupSource(c) {
  if (!igSelectedGroup.value) return
  const name = contactLabel(c)
  const exists = ruleForm.value.sources.some(
    s => s.source_type === 'contact_in_group' && s.contact_id === c.id && s.group_id === igSelectedGroup.value.id,
  )
  if (!exists) {
    ruleForm.value.sources.push({
      source_type: 'contact_in_group',
      contact_id: c.id, contact_name: name, contact_account_name: accountName(c.account_id),
      group_id: igSelectedGroup.value.id, group_name: igSelectedGroup.value.name,
      group_account_name: accountName(igSelectedGroup.value.account_id),
    })
  }
  igContactQuery.value = ''
  igContactOptions.value = []
  igSelectedGroup.value = null
  igGroupQuery.value = ''
}

const qtyCost = ref({
  step: 'input', text: '', parsing: false, applying: false, preview: [], error: '', result: null,
})
const salePrice = ref({
  step: 'input', text: '', parsing: false, applying: false, preview: [], error: '', result: null,
})

async function parseQtyCost() {
  qtyCost.value.error = ''
  qtyCost.value.parsing = true
  try {
    const { data } = await tradingApi.parseQtyCost(qtyCost.value.text)
    qtyCost.value.preview = data.items.map(item => ({
      product_id:    item.product_id,
      canonical_name: item.canonical_name,
      qty:           item.qty,
      cost_price:    item.cost_price,
      currency:      item.currency || 'USD',
    }))
    qtyCost.value.result = null
    qtyCost.value.step = 'review'
  } catch (e) {
    qtyCost.value.error = e.response?.data?.error || e.message || 'AI parsing failed'
  } finally {
    qtyCost.value.parsing = false
  }
}

async function applyQtyCost() {
  qtyCost.value.applying = true
  qtyCost.value.result = null
  try {
    // apply-qty-cost zeroes any active product not in this list — confirm with
    // the user first so a short/partial paste can't silently wipe stock.
    const { data: zeroPreview } = await tradingApi.previewZeroQty(qtyCost.value.preview)
    if (zeroPreview.count > 0) {
      const names = zeroPreview.products.slice(0, 15).map(p => p.name).join(', ')
      const more  = zeroPreview.count > 15 ? ` …and ${zeroPreview.count - 15} more` : ''
      const confirmed = window.confirm(
        `${zeroPreview.count} product(s) not in this list will have their qty set to 0:\n\n${names}${more}\n\nContinue?`
      )
      if (!confirmed) return
    }
    const { data } = await tradingApi.applyQtyCost(qtyCost.value.preview)
    qtyCost.value.result = data
    qtyCost.value.preview = []
  } finally {
    qtyCost.value.applying = false
  }
}

async function parseSalePrice() {
  salePrice.value.error = ''
  salePrice.value.parsing = true
  try {
    const { data } = await tradingApi.parseSalePrice(salePrice.value.text)
    salePrice.value.preview = data.items.map(item => ({
      product_id:    item.product_id,
      canonical_name: item.canonical_name,
      sale_price:    item.sale_price,
      currency:      item.currency || 'USD',
    }))
    salePrice.value.result = null
    salePrice.value.step = 'review'
  } catch (e) {
    salePrice.value.error = e.response?.data?.error || e.message || 'AI parsing failed'
  } finally {
    salePrice.value.parsing = false
  }
}

async function applySalePrice() {
  salePrice.value.applying = true
  salePrice.value.result = null
  try {
    const { data } = await tradingApi.applySalePrice(salePrice.value.preview)
    salePrice.value.result = data
    salePrice.value.preview = []
  } finally {
    salePrice.value.applying = false
  }
}

onMounted(() => {
  tradingApi.getActiveAgent().then(r => { agentPricing.value = r.data }).catch(() => {})
  loadAutomation().catch(() => {})
  accountsApi.list().then(r => { accounts.value = r.data }).catch(() => {})
})
</script>

<style scoped>
.ppu-view { padding: 20px 24px; overflow-y: auto; height: 100%; box-sizing: border-box; }
.page-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 18px; flex-wrap: wrap; }
.page-header h2 { margin: 0 0 4px; font-size: 1.2rem; }
.subtitle { margin: 0; font-size: 0.85rem; color: #6b7280; max-width: 640px; line-height: 1.5; }
.edit-prompt-link { color: #2563eb; text-decoration: none; white-space: nowrap; margin-left: 6px; }
.page-tabs { display: flex; gap: 4px; border: 1px solid #e5e7eb; border-radius: 8px; overflow: hidden; flex-shrink: 0; }
.page-tab { padding: 8px 18px; background: #f9fafb; border: none; cursor: pointer; font-size: 0.85rem; color: #6b7280; }
.page-tab.active { background: #2563eb; color: #fff; font-weight: 500; }

.process-card { background: #fff; border: 1px solid #e5e7eb; border-radius: 10px; padding: 18px; display: flex; flex-direction: column; gap: 14px; max-width: 900px; }

.form-group { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
.form-group label { font-size: 0.83rem; color: #374151; font-weight: 500; }
.hint { font-weight: 400; color: #6b7280; }
.bulk-textarea { width: 100%; padding: 8px 10px; border: 1px solid #d1d5db; border-radius: 6px; font-size: 0.85rem; font-family: monospace; resize: vertical; box-sizing: border-box; }
.bulk-error { color: #dc2626; font-size: 0.85rem; }

.tab-bar { display: flex; gap: 0; border: 1px solid #e5e7eb; border-radius: 6px; overflow: hidden; }
.tab-btn { flex: 1; padding: 7px; background: #f9fafb; border: none; cursor: pointer; font-size: 0.85rem; color: #6b7280; }
.tab-btn.active { background: #2563eb; color: #fff; font-weight: 500; }
.tab-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.preview-header { display: flex; justify-content: space-between; align-items: center; font-size: 0.85rem; color: #374151; }
.preview-table-wrap { max-height: 400px; overflow-y: auto; border: 1px solid #e5e7eb; border-radius: 6px; }
.preview-table { width: 100%; border-collapse: collapse; }
.data-table th { background: #f9fafb; padding: 10px 14px; text-align: left; font-size: 0.8rem; color: #6b7280; border-bottom: 1px solid #e5e7eb; }
.data-table td { padding: 8px 14px; border-bottom: 1px solid #f3f4f6; vertical-align: top; }
.data-table tr:last-child td { border-bottom: none; }
.row-unmatched td:first-child { color: #92400e; }
.inline-input { width: 100%; border: none; background: transparent; font-size: 0.85rem; padding: 2px 4px; outline: none; box-sizing: border-box; }
.inline-input:focus { background: #eff6ff; border-radius: 3px; }
.match-chip { background: #dcfce7; color: #15803d; padding: 1px 7px; border-radius: 4px; font-size: 0.75rem; font-weight: 600; }
.no-match-chip { background: #fef9c3; color: #92400e; padding: 1px 7px; border-radius: 4px; font-size: 0.75rem; }
.bulk-result { font-size: 0.85rem; color: #15803d; }

.process-foot { display: flex; align-items: center; justify-content: space-between; gap: 12px; border-top: 1px solid #e5e7eb; padding-top: 14px; }
.foot-spacer { flex: 1; }
.foot-actions { display: flex; gap: 8px; }
.token-pill { font-size: 0.8rem; font-family: monospace; background: #f3f4f6; color: #374151; padding: 4px 12px; border-radius: 20px; }

.btn-primary { padding: 7px 16px; background: #2563eb; color: #fff; border: none; border-radius: 6px; cursor: pointer; font-size: 0.9rem; }
.btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-ghost { padding: 7px 16px; background: transparent; border: 1px solid #d1d5db; border-radius: 6px; cursor: pointer; font-size: 0.9rem; }
.btn-sm { padding: 4px 10px; border: 1px solid #d1d5db; border-radius: 5px; background: #fff; cursor: pointer; font-size: 0.8rem; }
.btn-sm.danger { border-color: #fca5a5; color: #dc2626; }

/* ===== Automated Price Updates ===== */
.automation-section { max-width: 900px; margin-top: 32px; padding-top: 28px; border-top: 1px solid #e5e7eb; display: flex; flex-direction: column; gap: 4px; }
.section-eyebrow { display: flex; align-items: center; gap: 8px; }
.accent-mark { width: 8px; height: 8px; border-radius: 2px; background: #0d7a70; }
.section-eyebrow span { font-size: 0.7rem; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; color: #0d7a70; }
.section-title-row h3 { margin: 4px 0 6px; font-size: 1.05rem; font-weight: 650; }
.section-desc { margin: 0 0 16px; font-size: 0.83rem; color: #6b7280; max-width: 620px; }
.muted { color: #9ca3af; font-size: 0.82rem; }
.empty-msg { font-size: 0.85rem; color: #9ca3af; padding: 10px 0; }

.summary-strip { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1px; background: #e5e7eb; border: 1px solid #e5e7eb; border-radius: 10px; overflow: hidden; margin-bottom: 20px; }
.summary-cell { background: #fff; padding: 12px 16px; }
.summary-num { font-size: 1.3rem; font-weight: 650; }
.summary-num.accent { color: #0d7a70; }
.summary-label { font-size: 0.7rem; color: #6b7280; margin-top: 2px; }

.rules-list { display: flex; flex-direction: column; gap: 10px; margin-bottom: 14px; }
.rule-card { background: #fff; border: 1px solid #e5e7eb; border-radius: 10px; padding: 14px 16px; }
.rule-card.paused { opacity: 0.6; }
.rule-top { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; margin-bottom: 10px; }
.rule-name-group { display: flex; align-items: center; gap: 9px; flex-wrap: wrap; }
.rule-name { font-size: 0.9rem; font-weight: 650; }
.status-pill { display: inline-flex; align-items: center; gap: 5px; font-size: 0.68rem; font-weight: 650; padding: 3px 8px 3px 6px; border-radius: 20px; text-transform: uppercase; letter-spacing: 0.02em; }
.status-pill .dot { width: 6px; height: 6px; border-radius: 50%; }
.status-pill.on { background: #eafaf0; color: #16a34a; }
.status-pill.on .dot { background: #16a34a; }
.status-pill.off { background: #f3f4f6; color: #9ca3af; }
.status-pill.off .dot { background: #9ca3af; }
.rule-actions { display: flex; gap: 5px; flex-shrink: 0; }
.icon-btn { width: 26px; height: 26px; border-radius: 6px; border: 1px solid #e5e7eb; background: #fff; color: #6b7280; display: flex; align-items: center; justify-content: center; cursor: pointer; font-size: 0.8rem; }
.icon-btn:hover { background: #f9fafb; }

.rule-grid { display: grid; grid-template-columns: 1.9fr 1.3fr 0.9fr; gap: 16px; }
.rule-field-label { font-size: 0.65rem; font-weight: 700; letter-spacing: 0.04em; text-transform: uppercase; color: #9ca3af; margin-bottom: 6px; }

.chip-row { display: flex; flex-wrap: wrap; gap: 6px; }
.chip { display: inline-flex; align-items: center; gap: 5px; background: #f3f4f6; border: 1px solid #e5e7eb; padding: 3px 8px; border-radius: 6px; font-size: 0.75rem; color: #1f2937; }
.chip-kind { font-size: 0.6rem; font-weight: 700; text-transform: uppercase; color: #9ca3af; letter-spacing: 0.03em; }
.chip.group .chip-kind { color: #0d7a70; }
.chip.in-group { border-color: #0d7a70; background: #e3f5f2; }
.chip.in-group .chip-kind { color: #0d7a70; }
.chip .via-group { color: #0d7a70; font-weight: 600; }
.chip-account { color: #9ca3af; font-size: 0.68rem; margin-left: 2px; }
.chip-account::before { content: '· '; }
.chip .x { color: #9ca3af; margin-left: 3px; cursor: pointer; }

.cond-list { display: flex; flex-direction: column; gap: 5px; }
.cond-item { display: flex; align-items: baseline; gap: 6px; font-size: 0.78rem; }
.cond-op { font-size: 0.62rem; font-weight: 700; color: #9ca3af; text-transform: uppercase; width: 22px; flex-shrink: 0; }
.cond-value { color: #1f2937; background: #f3f4f6; border: 1px solid #e5e7eb; padding: 1px 6px; border-radius: 4px; font-size: 0.75rem; }
.cond-value.mono { font-family: ui-monospace, "SFMono-Regular", Consolas, monospace; }
.cond-item.ai .cond-value { background: #e3f5f2; color: #0d7a70; border-color: transparent; font-weight: 600; }

.action-mode { display: inline-flex; align-items: center; gap: 5px; font-size: 0.78rem; font-weight: 600; padding: 4px 9px; border-radius: 6px; }
.action-mode.review { background: #fdf3e3; color: #b45309; }
.action-mode.auto { background: #eafaf0; color: #16a34a; }
.action-mode.test { background: #e3f5f2; color: #0d7a70; }
.rule-meta { margin-top: 8px; font-size: 0.72rem; color: #9ca3af; }

.add-rule-btn { display: flex; align-items: center; justify-content: center; width: 100%; padding: 10px; border-radius: 10px; border: 1.5px dashed #d1d5db; background: transparent; color: #6b7280; font-size: 0.82rem; font-weight: 600; cursor: pointer; margin-bottom: 24px; }
.add-rule-btn:hover { border-color: #0d7a70; color: #0d7a70; }

.form-panel { background: #fff; border: 1px solid #0d7a70; border-radius: 12px; padding: 18px 20px; margin-bottom: 28px; }
.form-panel-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px; }
.form-panel-head h4 { margin: 0; font-size: 0.92rem; font-weight: 650; }
.close-x { color: #9ca3af; cursor: pointer; font-size: 1rem; }
.form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; margin-bottom: 14px; }
.form-row.single { grid-template-columns: 1fr; }
.field label { display: block; font-size: 0.78rem; font-weight: 650; color: #374151; margin-bottom: 6px; }
.field-hint { display: block; font-size: 0.75rem; color: #9ca3af; margin-top: 4px; }
.fake-input-real { width: 100%; padding: 7px 10px; border: 1px solid #d1d5db; border-radius: 7px; font-size: 0.82rem; box-sizing: border-box; }
.checkbox-field-real { display: flex; align-items: center; gap: 6px; font-size: 0.85rem; color: #374151; cursor: pointer; }

.source-options { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
.source-option { border: 1px solid #e5e7eb; border-radius: 8px; padding: 10px; background: #f9fafb; position: relative; }
.source-option.active { border-color: #0d7a70; background: #e3f5f2; }
.source-option-head { display: flex; align-items: center; gap: 6px; margin-bottom: 8px; }
.source-option-icon { font-size: 0.8rem; }
.source-option-title { font-size: 0.75rem; font-weight: 650; color: #1f2937; }
.source-option-body { position: relative; }
.search-results { position: absolute; z-index: 10; top: 100%; left: 0; right: 0; margin-top: 3px; background: #fff; border: 1px solid #d1d5db; border-radius: 7px; box-shadow: 0 4px 12px rgba(0,0,0,0.08); max-height: 160px; overflow-y: auto; }
.search-result { display: flex; align-items: baseline; justify-content: space-between; gap: 8px; padding: 6px 10px; font-size: 0.78rem; cursor: pointer; }
.search-result:hover { background: #f3f4f6; }
.search-result-account { flex-shrink: 0; font-size: 0.68rem; color: #9ca3af; white-space: nowrap; }
.in-group-row { display: flex; align-items: center; gap: 7px; flex-wrap: wrap; }
.igp-label { font-size: 0.75rem; color: #6b7280; white-space: nowrap; }
.fake-select { display: inline-flex; align-items: center; gap: 6px; padding: 6px 9px; border: 1px solid #d1d5db; border-radius: 7px; background: #fff; font-size: 0.78rem; font-weight: 500; }
.watching-row { min-height: 32px; padding: 8px; border: 1px dashed #e5e7eb; border-radius: 8px; }

.form-actions { display: flex; justify-content: flex-end; gap: 8px; padding-top: 14px; border-top: 1px solid #e5e7eb; margin-top: 4px; }
.btn-primary-fake { padding: 7px 16px; border-radius: 7px; border: none; background: #2563eb; color: #fff; font-size: 0.85rem; font-weight: 600; cursor: pointer; }
.btn-ghost-fake { padding: 7px 16px; border-radius: 7px; border: 1px solid #d1d5db; background: transparent; color: #1f2937; font-size: 0.85rem; font-weight: 600; cursor: pointer; }

.capture-filter-bar { display: flex; gap: 6px; margin-bottom: 14px; }
.filter-chip { padding: 5px 12px; border-radius: 20px; border: 1px solid #e5e7eb; background: #fff; color: #6b7280; font-size: 0.78rem; cursor: pointer; }
.filter-chip.sel { background: #0d7a70; border-color: #0d7a70; color: #fff; }
.capture-list-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 10px; color: #6b7280; font-size: 0.76rem; flex-wrap: wrap; }
.capture-pager { display: flex; align-items: center; gap: 5px; flex-wrap: wrap; }
.page-size-btn,
.pager-btn {
  border: 1px solid #e5e7eb;
  background: #fff;
  color: #4b5563;
  border-radius: 7px;
  padding: 5px 9px;
  font-size: 0.72rem;
  cursor: pointer;
}
.page-size-btn.active {
  border-color: #16a34a;
  background: #16a34a;
  color: #fff;
  font-weight: 700;
}
.pager-btn:disabled {
  cursor: not-allowed;
  color: #cbd5e1;
  background: #f9fafb;
}
.pager-label { padding: 0 6px; color: #4b5563; }

.feed-list { display: flex; flex-direction: column; border: 1px solid #e5e7eb; border-radius: 10px; overflow: hidden; background: #fff; }
.feed-row { display: grid; grid-template-columns: auto 1fr auto auto; align-items: center; gap: 14px; padding: 12px 16px; border-bottom: 1px solid #f3f4f6; }
.feed-row:last-child { border-bottom: none; }
.feed-avatar { width: 28px; height: 28px; border-radius: 50%; background: #eaf0fe; color: #2563eb; font-size: 0.7rem; font-weight: 700; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.feed-avatar.group { border-radius: 6px; background: #e3f5f2; color: #0d7a70; }
.feed-source { font-size: 0.8rem; font-weight: 650; color: #1f2937; }
.feed-dim { color: #9ca3af; font-weight: 400; margin-left: 4px; }
.feed-snippet { font-size: 0.76rem; color: #6b7280; margin-top: 2px; max-width: 420px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.feed-meta { font-size: 0.72rem; color: #9ca3af; white-space: nowrap; }
.feed-actions { display: flex; gap: 6px; align-items: center; white-space: nowrap; }
.feed-outcome { font-size: 0.7rem; font-weight: 700; padding: 4px 9px; border-radius: 20px; white-space: nowrap; }
.feed-outcome.applied { background: #eafaf0; color: #16a34a; }
.feed-outcome.ignored { background: #f3f4f6; color: #9ca3af; }
.feed-outcome.test { background: #e3f5f2; color: #0d7a70; }

.segmented { display: inline-flex; border: 1px solid #d1d5db; border-radius: 7px; overflow: hidden; }
.segmented button { padding: 7px 14px; border: none; background: #f9fafb; color: #6b7280; font-size: 0.78rem; font-weight: 600; cursor: pointer; border-right: 1px solid #d1d5db; }
.segmented button:last-child { border-right: none; }
.segmented button.sel { background: #2563eb; color: #fff; }
</style>
