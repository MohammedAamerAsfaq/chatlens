<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { accountsApi, contactsApi, groupsApi, tradingApi } from '@/api'

const loading = ref(true)
const saving = ref('')
const error = ref('')
const notice = ref('')
const accounts = ref([])
const rules = reactive({ buy: null, sell: null })
const searches = reactive({})

const definitions = [
  { type: 'buy', label: 'WTB forwarding', description: 'Forward confirmed buying inquiries only.' },
  { type: 'sell', label: 'WTS forwarding', description: 'Forward confirmed selling offers only.' },
]

function blankRule(type) {
  return {
    id: null, inquiry_type: type, name: type === 'buy' ? 'WTB forwarding' : 'WTS forwarding',
    is_active: false, include_original_message: true,
    include_summary: true, include_stock_suggestions: true, include_sender_link: true,
    prefill_sender_link_products: true,
    include_inquiry_id: true,
    targets: [], exclusions: [], recent_runs: [], forwarded_count: 0, skipped_count: 0,
  }
}

function accountName(id) {
  const account = accounts.value.find(row => row.id === id)
  return account?.display_name || account?.phone_number || `Account ${id}`
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [rulesRes, accountsRes] = await Promise.all([
      tradingApi.listInquiryForwardingRules(), accountsApi.list(),
    ])
    accounts.value = accountsRes.data.results || accountsRes.data || []
    const rows = rulesRes.data.results || rulesRes.data || []
    for (const type of ['buy', 'sell']) {
      rules[type] = rows.find(row => row.inquiry_type === type) || blankRule(type)
    }
  } catch (e) {
    error.value = e.response?.data?.detail || 'Unable to load inquiry forwarding rules.'
  } finally {
    loading.value = false
  }
}

async function save(rule) {
  if (!rule.name.trim()) { error.value = 'Rule name is required.'; return }
  if (rule.is_active && !rule.targets.length) { error.value = 'Add at least one forwarding destination before enabling the rule.'; return }
  saving.value = rule.inquiry_type
  error.value = ''; notice.value = ''
  const payload = {
    inquiry_type: rule.inquiry_type, name: rule.name.trim(), is_active: rule.is_active,
    include_original_message: rule.include_original_message,
    include_summary: rule.include_summary,
    include_stock_suggestions: rule.include_stock_suggestions,
    include_sender_link: rule.include_sender_link,
    prefill_sender_link_products: rule.prefill_sender_link_products,
    include_inquiry_id: rule.include_inquiry_id,
    targets: rule.targets.map(endpointPayload), exclusions: rule.exclusions.map(endpointPayload),
  }
  try {
    const response = rule.id
      ? await tradingApi.updateInquiryForwardingRule(rule.id, payload)
      : await tradingApi.createInquiryForwardingRule(payload)
    rules[rule.inquiry_type] = response.data
    notice.value = `${rule.inquiry_type === 'buy' ? 'WTB' : 'WTS'} rule saved.`
    return true
  } catch (e) {
    const data = e.response?.data
    error.value = typeof data === 'string' ? data : (data?.detail || Object.values(data || {})[0] || 'Unable to save rule.')
    return false
  } finally {
    saving.value = ''
  }
}

async function hotToggle(rule, event) {
  const enabled = event.target.checked
  if (enabled && !rule.targets.length) {
    error.value = 'Add at least one forwarding destination before enabling the rule.'
    return
  }
  saving.value = rule.inquiry_type
  error.value = ''; notice.value = ''
  rule.is_active = enabled
  try {
    const saved = await save(rule)
    if (!saved) {
      rule.is_active = !enabled
      return
    }
    notice.value = `${rule.inquiry_type === 'buy' ? 'WTB' : 'WTS'} automation turned ${enabled ? 'on' : 'off'}.`
  } finally {
    saving.value = ''
  }
}

function endpointPayload(row) {
  return { type: row.type, contact_id: row.contact_id || null, group_id: row.group_id || null }
}

function searchKey(type, bucket, kind) { return `${type}:${bucket}:${kind}` }
function state(type, bucket, kind) {
  const key = searchKey(type, bucket, kind)
  if (!searches[key]) searches[key] = { query: '', loading: false, results: [] }
  return searches[key]
}

async function search(rule, bucket, kind) {
  const current = state(rule.inquiry_type, bucket, kind)
  const query = current.query.trim()
  if (!query) { current.results = []; return }
  current.loading = true
  try {
    const response = kind === 'contact'
      ? await contactsApi.list({ search: query, page_size: 12 })
      : await groupsApi.list({ search: query, page_size: 12, ...(bucket === 'targets' ? { sendable: true } : {}) })
    current.results = response.data.results || response.data || []
  } finally {
    current.loading = false
  }
}

function add(rule, bucket, kind, item) {
  const list = rule[bucket]
  const idKey = kind === 'contact' ? 'contact_id' : 'group_id'
  if (!list.some(row => row.type === kind && row[idKey] === item.id)) {
    list.push({
      type: kind, contact_id: kind === 'contact' ? item.id : null,
      group_id: kind === 'group' ? item.id : null,
      name: kind === 'contact'
        ? (item.push_name || item.display_name || item.phone_number || item.wa_contact_id)
        : (item.name || item.wa_group_id),
      account_name: item.account_name || accountName(item.account_id),
    })
  }
  const current = state(rule.inquiry_type, bucket, kind)
  current.query = ''; current.results = []
}

function remove(rule, bucket, index) { rule[bucket].splice(index, 1) }
function endpointIcon(type) { return type === 'group' ? 'G' : 'DM' }
function statusLabel(status) { return (status || '').replaceAll('_', ' ') }
const hasRules = computed(() => rules.buy && rules.sell)

onMounted(load)
</script>

<template>
  <main class="page">
    <header class="hero">
      <div>
        <p class="eyebrow">Deterministic automation</p>
        <h1>Inquiry Forwarding</h1>
        <p>Forward only classified WTB or WTS inquiry cards with persisted product lines. No additional AI call is made.</p>
      </div>
      <div class="safety"><strong>Fail closed</strong><span>Uncertain or incomplete inquiries are skipped.</span></div>
    </header>
    <div v-if="error" class="alert error">{{ error }}</div>
    <div v-if="notice" class="alert success">{{ notice }}</div>
    <div v-if="loading" class="loading">Loading forwarding rules...</div>

    <section v-else-if="hasRules" class="rule-grid">
      <article v-for="definition in definitions" :key="definition.type" class="rule-card" :class="definition.type">
        <div class="rule-head">
          <div><span class="type-badge">{{ definition.type.toUpperCase() }}</span><h2>{{ definition.label }}</h2><p>{{ definition.description }}</p></div>
          <label class="switch"><input :checked="rules[definition.type].is_active" type="checkbox" :disabled="saving === definition.type" @change="hotToggle(rules[definition.type], $event)"><span></span><b>{{ rules[definition.type].is_active ? 'Active' : 'Paused' }}</b></label>
        </div>

        <label class="field"><span>Rule name</span><input v-model="rules[definition.type].name" type="text" maxlength="200"></label>
        <div class="checks">
          <label><input v-model="rules[definition.type].include_original_message" type="checkbox"> Original message</label>
          <label><input v-model="rules[definition.type].include_summary" type="checkbox"> Summary</label>
          <label><input v-model="rules[definition.type].include_stock_suggestions" type="checkbox"> Stock suggestions</label>
          <label><input v-model="rules[definition.type].include_sender_link" type="checkbox"> WA link</label>
          <label><input v-model="rules[definition.type].prefill_sender_link_products" type="checkbox" :disabled="!rules[definition.type].include_sender_link"> Prefill products in WA link</label>
          <label><input v-model="rules[definition.type].include_inquiry_id" type="checkbox"> Inquiry ID</label>
        </div>

        <section class="endpoint-section">
          <div class="section-title"><div><h3>Forward destinations</h3><p>The originating contact and group are always excluded automatically.</p></div><span>{{ rules[definition.type].targets.length }}</span></div>
          <div class="picker-grid">
            <div v-for="kind in ['contact', 'group']" :key="kind" class="picker">
              <label>{{ kind === 'contact' ? 'Add direct contact' : 'Add sendable group' }}</label>
              <div class="search-row"><input v-model="state(definition.type, 'targets', kind).query" :placeholder="`Search ${kind}s`" @keyup.enter="search(rules[definition.type], 'targets', kind)"><button @click="search(rules[definition.type], 'targets', kind)">Search</button></div>
              <div v-if="state(definition.type, 'targets', kind).results.length" class="results">
                <button v-for="item in state(definition.type, 'targets', kind).results" :key="item.id" @click="add(rules[definition.type], 'targets', kind, item)"><b>{{ kind === 'contact' ? (item.push_name || item.display_name || item.phone_number) : item.name }}</b><small>{{ item.account_name || accountName(item.account_id) }}</small></button>
              </div>
            </div>
          </div>
          <div class="chips"><span v-for="(item, index) in rules[definition.type].targets" :key="`${item.type}:${item.contact_id || item.group_id}`"><i>{{ endpointIcon(item.type) }}</i><b>{{ item.name }}</b><small>{{ item.account_name }}</small><button @click="remove(rules[definition.type], 'targets', index)">×</button></span><em v-if="!rules[definition.type].targets.length">No destinations selected.</em></div>
        </section>

        <section class="endpoint-section exclusions">
          <div class="section-title"><div><h3>Source exclusions</h3><p>Skip the entire forwarding rule when the inquiry originated here.</p></div><span>{{ rules[definition.type].exclusions.length }}</span></div>
          <div class="picker-grid">
            <div v-for="kind in ['contact', 'group']" :key="kind" class="picker">
              <label>{{ kind === 'contact' ? 'Exclude source contact' : 'Exclude source group' }}</label>
              <div class="search-row"><input v-model="state(definition.type, 'exclusions', kind).query" :placeholder="`Search ${kind}s`" @keyup.enter="search(rules[definition.type], 'exclusions', kind)"><button @click="search(rules[definition.type], 'exclusions', kind)">Search</button></div>
              <div v-if="state(definition.type, 'exclusions', kind).results.length" class="results">
                <button v-for="item in state(definition.type, 'exclusions', kind).results" :key="item.id" @click="add(rules[definition.type], 'exclusions', kind, item)"><b>{{ kind === 'contact' ? (item.push_name || item.display_name || item.phone_number) : item.name }}</b><small>{{ item.account_name || accountName(item.account_id) }}</small></button>
              </div>
            </div>
          </div>
          <div class="chips"><span v-for="(item, index) in rules[definition.type].exclusions" :key="`${item.type}:${item.contact_id || item.group_id}`"><i>{{ endpointIcon(item.type) }}</i><b>{{ item.name }}</b><small>{{ item.account_name }}</small><button @click="remove(rules[definition.type], 'exclusions', index)">×</button></span><em v-if="!rules[definition.type].exclusions.length">No source exclusions.</em></div>
        </section>

        <div class="metrics"><span><b>{{ rules[definition.type].forwarded_count }}</b> queued deliveries</span><span><b>{{ rules[definition.type].skipped_count }}</b> strict skips</span></div>
        <div v-if="rules[definition.type].recent_runs.length" class="runs"><h3>Recent decisions</h3><div v-for="run in rules[definition.type].recent_runs" :key="run.id"><b>#{{ run.inquiry }}</b><span :class="run.status">{{ statusLabel(run.status) }}</span><small>{{ run.reason || `${run.queued_count}/${run.destination_count} queued` }}</small></div></div>
        <button class="save" :disabled="saving === definition.type" @click="save(rules[definition.type])">{{ saving === definition.type ? 'Saving...' : `Save ${definition.type.toUpperCase()} rule` }}</button>
      </article>
    </section>
  </main>
</template>

<style scoped>
.page{height:100%;overflow:auto;padding:28px;background:radial-gradient(circle at 85% 5%,#e0f7e8 0,transparent 30%),#f5f7f5;color:#17231b}.hero{display:flex;justify-content:space-between;gap:24px;align-items:end;margin-bottom:20px}.eyebrow{margin:0;color:#28704a;text-transform:uppercase;letter-spacing:.14em;font-size:.7rem;font-weight:800}.hero h1{margin:4px 0;font:700 2.1rem Georgia,serif}.hero p{margin:0;color:#607066}.safety{display:flex;flex-direction:column;background:#173c2b;color:#fff;padding:12px 18px;border-radius:10px}.safety span{font-size:.78rem;color:#cce2d4}.rule-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}.rule-card{background:#fff;border:1px solid #dce5df;border-top:5px solid #20834e;border-radius:14px;padding:20px;box-shadow:0 8px 26px #183f2810}.rule-card.sell{border-top-color:#c98217}.rule-head,.section-title{display:flex;justify-content:space-between;gap:14px;align-items:flex-start}.rule-head h2{margin:7px 0 2px;font:700 1.35rem Georgia,serif}.rule-head p,.section-title p{margin:0;color:#6c7c72;font-size:.82rem}.type-badge{font-size:.68rem;font-weight:900;letter-spacing:.12em;color:#28704a}.sell .type-badge{color:#9a5b08}.switch{display:flex;align-items:center;gap:7px;font-size:.75rem}.switch input{display:none}.switch span{width:38px;height:21px;background:#cbd5ce;border-radius:20px;position:relative}.switch span:after{content:"";position:absolute;width:15px;height:15px;left:3px;top:3px;border-radius:50%;background:#fff;transition:.2s}.switch input:checked+span{background:#21854f}.switch input:checked+span:after{transform:translateX(17px)}.field{display:flex;flex-direction:column;gap:5px;margin:18px 0 12px}.field span,.picker label{font-size:.76rem;font-weight:800;color:#40564a}.field input,.search-row input{border:1px solid #cad8ce;border-radius:8px;padding:9px;background:#fff}.checks{display:flex;flex-wrap:wrap;gap:13px;font-size:.8rem}.checks input{accent-color:#21854f}.endpoint-section{position:relative;margin-top:18px;padding:16px;border:1px solid #dce8df;border-radius:11px;background:#fbfdfb}.endpoint-section.exclusions{background:#fffaf5;border-color:#eadfce}.section-title h3{margin:0 0 3px;font-size:.95rem}.section-title>span{background:#e5f3e9;color:#226b42;border-radius:99px;padding:3px 9px;font-weight:800}.picker-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:13px}.search-row{display:flex;gap:6px;margin-top:5px}.search-row input{min-width:0;flex:1}.search-row button,.results button{border:1px solid #aac4b3;background:#fff;border-radius:7px;padding:7px;color:#225f3e;cursor:pointer}.results{position:absolute;z-index:5;background:#fff;border:1px solid #cad8ce;border-radius:8px;box-shadow:0 8px 20px #12291a22;max-height:210px;overflow:auto;margin-top:4px}.results button{display:flex;width:260px;flex-direction:column;align-items:flex-start;border:0;border-bottom:1px solid #edf1ee;border-radius:0}.results small,.chips small{color:#748279}.chips{display:flex;flex-wrap:wrap;gap:7px;margin-top:13px}.chips>span{display:grid;grid-template-columns:auto 1fr auto;gap:2px 7px;align-items:center;background:#eef7f0;border-radius:8px;padding:6px 8px}.chips i{grid-row:1/3;font-size:.6rem;font-style:normal;font-weight:900;color:#277149}.chips small{grid-column:2}.chips button{grid-column:3;grid-row:1/3;border:0;background:none;color:#9f332d;font-size:1rem}.chips em{color:#7b887f;font-size:.8rem}.metrics{display:flex;gap:10px;margin:15px 0}.metrics span{flex:1;padding:10px;background:#f0f5f1;border-radius:8px;font-size:.75rem;color:#617168}.metrics b{display:block;color:#183c2a;font-size:1.1rem}.runs h3{font-size:.82rem;margin:0 0 6px}.runs>div{display:grid;grid-template-columns:60px 75px 1fr;gap:8px;padding:6px 0;border-top:1px solid #edf0ee;font-size:.75rem}.runs span{text-transform:capitalize}.runs span.complete{color:#168046}.runs span.skipped,.runs span.failed{color:#aa3d2d}.runs small{color:#69786f}.save{width:100%;border:0;border-radius:8px;padding:10px;background:#17653d;color:#fff;font-weight:800;cursor:pointer}.save:disabled{opacity:.55}.alert,.loading{padding:11px 13px;border-radius:8px;margin-bottom:14px}.alert.error{background:#fff0ee;color:#9e3028}.alert.success{background:#eaf8ee;color:#17643b}.loading{background:#fff}@media(max-width:1100px){.rule-grid{grid-template-columns:1fr}}@media(max-width:700px){.page{padding:18px}.hero{align-items:flex-start;flex-direction:column}.picker-grid{grid-template-columns:1fr}}

/* Semantic theme bridge. */
.page{background:radial-gradient(circle at 85% 5%,var(--ui-primary-soft) 0,transparent 30%),var(--ui-bg);color:var(--ui-text);font-family:var(--ui-font-sans)}
.eyebrow,.type-badge,.chips i{color:var(--ui-primary)}.hero p,.rule-head p,.section-title p,.results small,.chips small,.chips em,.runs small{color:var(--ui-text-muted)}
.safety{background:var(--ui-text-strong);color:var(--ui-surface)}.safety span{color:var(--ui-border)}
.rule-card,.endpoint-section,.results,.loading{background:var(--ui-surface);border-color:var(--ui-border);box-shadow:var(--ui-shadow-sm)}
.rule-card{border-top-color:var(--ui-primary);border-radius:var(--ui-radius-lg)}.rule-card.sell{border-top-color:var(--ui-warning)}.sell .type-badge{color:var(--ui-warning)}
.field span,.picker label,.metrics b{color:var(--ui-text-strong)}
.field input,.search-row input,.search-row button,.results button{background:var(--ui-surface);color:var(--ui-text);border-color:var(--ui-border-strong)}
.field input:focus,.search-row input:focus{border-color:var(--ui-primary);box-shadow:var(--ui-focus-ring);outline:0}
.checks input{accent-color:var(--ui-primary)}.switch span{background:var(--ui-border-strong)}.switch input:checked+span,.save{background:var(--ui-primary)}
.endpoint-section.exclusions{background:var(--ui-warning-soft);border-color:var(--ui-warning)}
.section-title>span,.chips>span{background:var(--ui-primary-soft);color:var(--ui-primary)}
.results{box-shadow:var(--ui-shadow-lg)}.results button{border-bottom-color:var(--ui-border)}.chips button,.runs span.skipped,.runs span.failed{color:var(--ui-danger)}
.metrics span{background:var(--ui-surface-muted);color:var(--ui-text-muted)}.runs>div{border-color:var(--ui-border)}.runs span.complete{color:var(--ui-success)}
.save{color:var(--ui-on-primary)}.alert.error{background:var(--ui-danger-soft);color:var(--ui-danger)}.alert.success{background:var(--ui-success-soft);color:var(--ui-success)}
</style>
