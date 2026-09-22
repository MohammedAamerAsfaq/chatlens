<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { accountsApi, groupsApi, tradingApi } from '@/api'

const props = defineProps({ kind: { type: String, required: true } })
const isBuying = computed(() => props.kind === 'buying')
const title = computed(() => isBuying.value ? 'Group Buying Inquiries' : 'Group Selling Offers')
const campaigns = ref([])
const products = ref([])
const productOptions = ref([])
const expanded = ref(new Set())
const groupSearch = reactive({})
const groupOptions = reactive({})
const loadingGroups = reactive({})
const sendFeedback = reactive({})
const busy = ref('')
const error = ref('')
const draft = reactive({ name: '', messageMode: 'formatted', directMessage: '', productSearch: '', header: '', line: '', footer: '' })
const editingId = ref(null)
const editProductOptions = ref([])
const editDraft = reactive({ name: '', messageMode: 'formatted', directMessage: '', productSearch: '', header: '', line: '', footer: '' })

function defaults() {
  return isBuying.value
    ? ['Hello, looking to buy:', '- {product_name} - Qty {qty} - Target {price}', 'Please reply with availability and best price.']
    : ['Hello, available stock offer:', '- {product_name} - Qty {qty} - {price}', 'Reply with required quantity. Subject to availability.']
}

function resetDraft() {
  const [header, line, footer] = defaults()
  Object.assign(draft, { name: '', messageMode: 'formatted', directMessage: '', productSearch: '', header, line, footer })
  products.value = []
  productOptions.value = []
}

function apiFor(action) {
  const buying = {
    list: tradingApi.listBuyingInquiries,
    create: tradingApi.createBuyingInquiry,
    addGroup: tradingApi.addBuyingInquiryGroup,
    removeGroup: tradingApi.removeBuyingInquiryGroup,
    markSent: tradingApi.markBuyingInquiryGroupSent,
    update: tradingApi.updateBuyingInquiry,
    addProduct: tradingApi.addBuyingInquiryProduct,
    removeProduct: tradingApi.removeBuyingInquiryProduct,
  }
  const selling = {
    list: tradingApi.listSellingOffers,
    create: tradingApi.createSellingOffer,
    addGroup: tradingApi.addSellingOfferGroup,
    removeGroup: tradingApi.removeSellingOfferGroup,
    markSent: tradingApi.markSellingOfferGroupSent,
    update: tradingApi.updateSellingOffer,
    addProduct: tradingApi.addSellingOfferProduct,
    removeProduct: tradingApi.removeSellingOfferProduct,
  }
  return (isBuying.value ? buying : selling)[action]
}

async function loadCampaigns() {
  const { data } = await apiFor('list')({ audience_type: 'groups', page_size: 100 })
  campaigns.value = data.results || data
}

async function searchProducts() {
  const { data } = await tradingApi.listProducts({ search: draft.productSearch, active: 'true' })
  productOptions.value = (data.results || data).filter(row => !products.value.some(item => item.id === row.id))
}

function addProduct(product) {
  products.value.push(product)
  productOptions.value = productOptions.value.filter(row => row.id !== product.id)
}

async function createCampaign() {
  if (!draft.name.trim() || (draft.messageMode === 'direct' && !draft.directMessage.trim())) return
  busy.value = 'create'
  error.value = ''
  try {
    const payload = {
      name: draft.name.trim(), audience_type: 'groups', message_mode: draft.messageMode,
      direct_message: draft.messageMode === 'direct' ? draft.directMessage.trim() : '',
      product_ids: draft.messageMode === 'formatted' ? products.value.map(row => row.id) : [],
      header_template: draft.header, product_line_template: draft.line, footer_template: draft.footer,
    }
    const { data } = await apiFor('create')(payload)
    await loadCampaigns()
    expanded.value = new Set([...expanded.value, data.id])
    resetDraft()
  } catch (exc) {
    error.value = exc.response?.data?.direct_message || exc.response?.data?.detail || 'Unable to create group campaign.'
  } finally {
    busy.value = ''
  }
}

function startEdit(campaign) {
  editingId.value = campaign.id
  editProductOptions.value = []
  Object.assign(editDraft, {
    name: campaign.name,
    messageMode: campaign.message_mode || 'formatted',
    directMessage: campaign.direct_message || '',
    productSearch: '',
    header: campaign.header_template,
    line: campaign.product_line_template,
    footer: campaign.footer_template,
  })
}

function cancelEdit() {
  editingId.value = null
  editProductOptions.value = []
}

async function saveEdit(campaign) {
  if (!editDraft.name.trim() || (editDraft.messageMode === 'direct' && !editDraft.directMessage.trim())) return
  busy.value = `save-${campaign.id}`
  error.value = ''
  try {
    const { data } = await apiFor('update')(campaign.id, {
      name: editDraft.name.trim(),
      message_mode: editDraft.messageMode,
      direct_message: editDraft.messageMode === 'direct' ? editDraft.directMessage.trim() : '',
      header_template: editDraft.header,
      product_line_template: editDraft.line,
      footer_template: editDraft.footer,
    })
    replaceCampaign(data)
    cancelEdit()
  } catch (exc) {
    error.value = exc.response?.data?.direct_message || exc.response?.data?.detail || 'Unable to save campaign changes.'
  } finally { busy.value = '' }
}

async function searchEditProducts(campaign) {
  const { data } = await tradingApi.listProducts({ search: editDraft.productSearch, active: 'true' })
  const selected = new Set(campaign.products.map(row => row.product))
  editProductOptions.value = (data.results || data).filter(row => !selected.has(row.id))
}

async function addEditProduct(campaign, product) {
  busy.value = `add-product-${campaign.id}-${product.id}`
  try {
    const { data } = await apiFor('addProduct')(campaign.id, product.id)
    replaceCampaign(data.inquiry || data.offer)
    editProductOptions.value = editProductOptions.value.filter(row => row.id !== product.id)
  } catch (exc) {
    error.value = exc.response?.data?.detail || 'Unable to add product.'
  } finally { busy.value = '' }
}

async function removeEditProduct(campaign, row) {
  busy.value = `remove-product-${campaign.id}-${row.product}`
  try {
    await apiFor('removeProduct')(campaign.id, row.product)
    campaign.products = campaign.products.filter(item => item.id !== row.id)
  } catch (exc) {
    error.value = exc.response?.data?.detail || 'Unable to remove product.'
  } finally { busy.value = '' }
}

async function searchGroups(campaign) {
  loadingGroups[campaign.id] = true
  try {
    const { data } = await groupsApi.list({ search: groupSearch[campaign.id], sendable: 'true', page_size: 100 })
    const selected = new Set(campaign.groups.map(row => row.group))
    groupOptions[campaign.id] = (data.results || data).filter(row => !selected.has(row.id))
  } finally {
    loadingGroups[campaign.id] = false
  }
}

async function addGroup(campaign, group) {
  busy.value = `add-${campaign.id}-${group.id}`
  try {
    const { data } = await apiFor('addGroup')(campaign.id, group.id)
    replaceCampaign(data.inquiry || data.offer)
    groupOptions[campaign.id] = (groupOptions[campaign.id] || []).filter(row => row.id !== group.id)
  } catch (exc) {
    error.value = exc.response?.data?.group_id || 'Unable to add group.'
  } finally { busy.value = '' }
}

async function addAllAvailableGroups(campaign) {
  const available = [...(groupOptions[campaign.id] || [])]
  if (!available.length) return
  busy.value = `add-all-${campaign.id}`
  error.value = ''
  try {
    for (const group of available) {
      const { data } = await apiFor('addGroup')(campaign.id, group.id)
      replaceCampaign(data.inquiry || data.offer)
    }
    groupOptions[campaign.id] = []
  } catch (exc) {
    error.value = exc.response?.data?.group_id || 'Unable to add all available groups.'
    await loadCampaigns()
  } finally {
    busy.value = ''
  }
}

async function removeGroup(campaign, recipient) {
  await apiFor('removeGroup')(campaign.id, recipient.id)
  campaign.groups = campaign.groups.filter(row => row.id !== recipient.id)
}

function replaceCampaign(updated) {
  const index = campaigns.value.findIndex(row => row.id === updated.id)
  if (index !== -1) campaigns.value[index] = updated
}

function message(campaign) {
  if (campaign.message_mode === 'direct') return campaign.direct_message || ''
  const lines = campaign.products.map(row => campaign.product_line_template
    .replaceAll('{product_name}', row.product_name)
    .replaceAll('{qty}', row.quantity ?? '-')
    .replaceAll('{price}', row.target_price ?? row.price ?? '-'))
  return [campaign.header_template, ...lines, campaign.footer_template].filter(Boolean).join('\n')
}

async function sendGroup(campaign, recipient) {
  busy.value = `send-${campaign.id}-${recipient.id}`
  error.value = ''
  sendFeedback[recipient.id] = { state: 'checking', message: 'Checking group permission...' }
  try {
    const preflight = await accountsApi.preflightMessage(recipient.account_id, recipient.wa_group_id)
    if (!preflight.data.allowed) {
      const labels = {
        group_metadata_stale: 'Group metadata could not be refreshed.',
        session_disconnected: 'WhatsApp session is disconnected.',
        live_preflight_unavailable: 'WhatsApp worker preflight is unavailable.',
        group_sending_disabled: 'Group sending is disabled for this account.',
        master_sending_disabled: 'Outbound sending is disabled for this account.',
        group_admin_required: 'Only a group administrator can send here.',
        not_a_group_participant: 'This account is not a participant in the group.',
      }
      throw new Error(labels[preflight.data.reason] || preflight.data.reason || 'Group sending is blocked.')
    }
    sendFeedback[recipient.id] = { state: 'queueing', message: 'Queueing message...' }
    const { data } = await accountsApi.sendMessage(recipient.account_id, {
      destination_jid: recipient.wa_group_id,
      text: message(campaign),
      idempotency_key: `${props.kind}-group-${campaign.id}-${recipient.id}-${Date.now()}`,
    })
    if (['blocked', 'preflight_blocked', 'failed'].includes(data.status)) {
      throw new Error(data.status_reason || data.last_error || 'Outbound message was blocked.')
    }
    sendFeedback[recipient.id] = { state: 'queued', message: 'ChatLens message queued.' }
  } catch (exc) {
    const message = exc.response?.data?.detail || exc.message || 'Unable to queue group message.'
    sendFeedback[recipient.id] = { state: 'failed', message }
  } finally { busy.value = '' }
}

function waClientUrl(campaign) {
  return `whatsapp://send?${new URLSearchParams({ text: message(campaign) }).toString()}`
}

async function markWaPressed(campaign, recipient) {
  try {
    const { data } = await apiFor('markSent')(campaign.id, recipient.id)
    replaceCampaign(data)
  } catch (exc) {
    error.value = exc.response?.data?.detail || 'Unable to record WA Client button press.'
  }
}

async function toggle(campaign) {
  const next = new Set(expanded.value)
  const opening = !next.has(campaign.id)
  opening ? next.add(campaign.id) : next.delete(campaign.id)
  expanded.value = next
  if (opening && groupOptions[campaign.id] === undefined) await searchGroups(campaign)
}

resetDraft()
onMounted(loadCampaigns)
</script>

<template>
  <main class="campaign-page">
    <header><div><p class="eyebrow">Sendable groups only</p><h1>{{ title }}</h1><p>Create a preformatted product campaign or a direct message for groups where posting is allowed.</p></div></header>
    <div v-if="error" class="error">{{ error }}</div>
    <section class="panel composer">
      <label>Name<input v-model="draft.name" placeholder="Campaign name" /></label>
      <div class="mode-picker">
        <button :class="{ active: draft.messageMode === 'formatted' }" @click="draft.messageMode = 'formatted'"><strong>Preformatted Products</strong><span>Build the message from selected inventory and templates.</span></button>
        <button :class="{ active: draft.messageMode === 'direct' }" @click="draft.messageMode = 'direct'"><strong>Direct Message</strong><span>Write one message to send to every selected group.</span></button>
      </div>
      <template v-if="draft.messageMode === 'formatted'">
        <label>Product search<div class="inline"><input v-model="draft.productSearch" @keydown.enter.prevent="searchProducts" /><button @click="searchProducts">Search</button></div></label>
        <div v-if="productOptions.length" class="options"><button v-for="row in productOptions" :key="row.id" @click="addProduct(row)"><strong>{{ row.brand }} {{ row.name }}</strong><span>Qty {{ row.qty }}</span></button></div>
        <div class="tokens"><span v-for="row in products" :key="row.id">{{ row.brand }} {{ row.name }} <button @click="products = products.filter(item => item.id !== row.id)">x</button></span></div>
        <div class="templates"><label>Header<textarea v-model="draft.header" rows="2" /></label><label>Product line<textarea v-model="draft.line" rows="2" /></label><label>Footer<textarea v-model="draft.footer" rows="2" /></label></div>
      </template>
      <label v-else>Direct message<textarea v-model="draft.directMessage" rows="6" placeholder="Write the message that will be sent to the selected groups..." /></label>
      <button class="primary" :disabled="busy === 'create' || !draft.name.trim() || (draft.messageMode === 'direct' && !draft.directMessage.trim())" @click="createCampaign">{{ busy === 'create' ? 'Creating...' : `Create ${title}` }}</button>
    </section>
    <section class="panel list">
      <div class="section-head"><div><h2>Existing {{ title }}</h2><p>Announcements, communities, non-participant and blocked groups never appear in selection.</p></div><button @click="loadCampaigns">Refresh</button></div>
      <p v-if="!campaigns.length" class="empty">No group campaigns created.</p>
      <article v-for="campaign in campaigns" :key="campaign.id" class="campaign">
        <button class="summary" @click="toggle(campaign)"><span><strong>{{ campaign.name }}</strong><small>{{ campaign.message_mode === 'direct' ? 'Direct message' : `${campaign.products.length} products` }} · {{ campaign.groups.length }} groups</small></span><b>{{ expanded.has(campaign.id) ? '−' : '+' }}</b></button>
        <div v-if="expanded.has(campaign.id)" class="details">
          <div class="edit-toolbar"><button v-if="editingId !== campaign.id" @click="startEdit(campaign)">Edit {{ isBuying ? 'Inquiry' : 'Offer' }}</button><template v-else><button class="primary" :disabled="busy === `save-${campaign.id}`" @click="saveEdit(campaign)">{{ busy === `save-${campaign.id}` ? 'Saving...' : 'Save Changes' }}</button><button @click="cancelEdit">Cancel</button></template></div>
          <div v-if="editingId === campaign.id" class="edit-panel">
            <label>Name<input v-model="editDraft.name" /></label>
            <div class="mode-picker">
              <button :class="{ active: editDraft.messageMode === 'formatted' }" @click="editDraft.messageMode = 'formatted'"><strong>Preformatted Products</strong><span>Use products and templates.</span></button>
              <button :class="{ active: editDraft.messageMode === 'direct' }" @click="editDraft.messageMode = 'direct'"><strong>Direct Message</strong><span>Use one campaign message.</span></button>
            </div>
            <template v-if="editDraft.messageMode === 'formatted'">
              <div class="templates"><label>Header<textarea v-model="editDraft.header" rows="2" /></label><label>Product line<textarea v-model="editDraft.line" rows="2" /></label><label>Footer<textarea v-model="editDraft.footer" rows="2" /></label></div>
              <div class="edit-products"><h3>Products</h3><div class="inline"><input v-model="editDraft.productSearch" placeholder="Search product to add..." @keydown.enter.prevent="searchEditProducts(campaign)" /><button @click="searchEditProducts(campaign)">Search</button></div><div v-if="editProductOptions.length" class="options"><button v-for="product in editProductOptions" :key="product.id" @click="addEditProduct(campaign, product)"><strong>{{ product.brand }} {{ product.name }}</strong><span>Qty {{ product.qty }}</span></button></div><div class="edit-product-list"><div v-for="row in campaign.products" :key="row.id"><span>{{ row.product_name }}</span><button class="danger" :disabled="busy === `remove-product-${campaign.id}-${row.product}`" @click="removeEditProduct(campaign, row)">Remove</button></div></div></div>
            </template>
            <label v-else>Direct message<textarea v-model="editDraft.directMessage" rows="6" /></label>
          </div>
          <div v-else class="preview"><h3>Message preview</h3><pre>{{ message(campaign) }}</pre></div>
          <div class="selector"><div class="selector-head"><div><h3>Available groups</h3><small>Only groups currently allowed for sending are listed.</small></div><button :disabled="loadingGroups[campaign.id] || !(groupOptions[campaign.id] || []).length || busy === `add-all-${campaign.id}`" @click="addAllAvailableGroups(campaign)">{{ busy === `add-all-${campaign.id}` ? 'Adding...' : 'Add all available' }}</button></div><div class="inline"><input v-model="groupSearch[campaign.id]" placeholder="Filter available groups..." @keydown.enter.prevent="searchGroups(campaign)" /><button :disabled="loadingGroups[campaign.id]" @click="searchGroups(campaign)">{{ loadingGroups[campaign.id] ? 'Loading...' : 'Refresh' }}</button></div>
            <div class="options"><button v-for="group in groupOptions[campaign.id] || []" :key="group.id" :disabled="busy === `add-${campaign.id}-${group.id}` || busy === `add-all-${campaign.id}`" @click="addGroup(campaign, group)"><strong>{{ group.name || group.wa_group_id }}</strong><span>{{ group.participant_count }} participants · Account {{ group.account_id }}</span></button><p v-if="!loadingGroups[campaign.id] && !(groupOptions[campaign.id] || []).length" class="empty">No additional sendable groups available.</p></div>
          </div>
          <div class="recipients"><h3>Groups to message</h3><div v-for="recipient in campaign.groups" :key="recipient.id" class="recipient"><div><strong>{{ recipient.group_name || recipient.wa_group_id }}</strong><span>{{ recipient.account_name }}</span><span :class="['press-count', { sent: recipient.sent_count > 0 }]">{{ recipient.sent_count ? `WA pressed ${recipient.sent_count}x` : 'WA not pressed' }}</span><span v-if="sendFeedback[recipient.id]" :class="['send-feedback', sendFeedback[recipient.id].state]">{{ sendFeedback[recipient.id].message }}</span></div><div><a class="wa-client" :href="waClientUrl(campaign)" title="Open WhatsApp with this message, then select the intended group" @click="markWaPressed(campaign, recipient)">WA Client</a><button class="send" :disabled="busy === `send-${campaign.id}-${recipient.id}`" @click="sendGroup(campaign, recipient)">{{ busy === `send-${campaign.id}-${recipient.id}` ? 'Working...' : 'ChatLens Send' }}</button><button class="danger" @click="removeGroup(campaign, recipient)">Remove</button></div></div><p v-if="!campaign.groups.length" class="empty">No groups selected.</p></div>
        </div>
      </article>
    </section>
  </main>
</template>

<style scoped>
.campaign-page{height:100%;min-height:0;overflow-y:auto;padding:28px;background:radial-gradient(circle at top right,#dcfce7,transparent 32%),#f8fafc;color:#172033}.campaign-page>header{max-width:1400px;margin:auto}.eyebrow{color:#15803d;text-transform:uppercase;letter-spacing:.16em;font-size:.72rem;font-weight:800}h1{font:700 2rem Georgia,serif;margin:4px 0}header p,.section-head p{color:#64748b}.panel{max-width:1400px;margin:18px auto;background:#fff;border:1px solid #dfe7e2;border-radius:18px;padding:22px;box-shadow:0 16px 40px #0f172a0d}.fields,.templates{display:grid;grid-template-columns:1fr 1fr;gap:14px}.templates{grid-template-columns:repeat(3,1fr);margin-top:16px}label{display:flex;flex-direction:column;gap:6px;font-size:.75rem;font-weight:800;text-transform:uppercase;color:#64748b}input,textarea,button{font:inherit}input,textarea{border:1px solid #d7e2dc;border-radius:10px;padding:10px;background:#fbfdfc}.inline{display:flex;gap:8px}.inline input{flex:1}button,.wa-client{border:1px solid #cedbd4;background:#fff;border-radius:9px;padding:9px 13px;cursor:pointer}.wa-client{display:inline-flex;align-items:center;text-decoration:none;background:#25d366;color:#fff;border-color:#25d366;font-weight:700}.primary,.send{background:#168447;color:#fff;border-color:#168447}.primary{margin-top:16px;font-weight:700}.options{display:grid;gap:6px;margin-top:8px}.options button,.recipient{display:flex;justify-content:space-between;align-items:center;text-align:left}.options span,.recipient span,small{display:block;color:#64748b;font-size:.78rem}.tokens{display:flex;flex-wrap:wrap;gap:7px;margin-top:10px}.tokens span{background:#edf8f1;border-radius:20px;padding:6px 10px;font-size:.8rem}.tokens button{border:0;background:none;padding:0 0 0 6px}.section-head,.summary,.selector-head{display:flex;align-items:center;justify-content:space-between;gap:12px}.campaign{border:1px solid #e3ebe6;border-radius:13px;margin-top:10px;overflow:hidden}.summary{width:100%;border:0;border-radius:0;padding:14px 16px}.summary strong{display:block}.details{padding:16px;background:#fbfdfc;display:grid;grid-template-columns:1fr 1fr;gap:18px}.edit-toolbar,.edit-panel{grid-column:1/-1}.edit-toolbar{display:flex;gap:8px}.edit-toolbar .primary{margin-top:0}.edit-panel{border:1px solid #dfe7e2;border-radius:12px;padding:16px;background:#fff}.edit-products{margin-top:16px}.edit-product-list{display:grid;gap:6px;margin-top:10px}.edit-product-list>div{display:flex;align-items:center;justify-content:space-between;border-top:1px solid #e3ebe6;padding-top:7px}.preview pre{white-space:pre-wrap;background:#eef5f0;border-radius:12px;padding:14px}.recipients{grid-column:1/-1}.recipient{padding:11px 0;border-top:1px solid #e3ebe6}.recipient>div:last-child{display:flex;gap:7px;flex-wrap:wrap}.press-count{margin-top:3px!important;color:#64748b}.press-count.sent{color:#15803d;font-weight:700}.send-feedback{margin-top:3px!important;font-weight:700}.send-feedback.checking,.send-feedback.queueing{color:#986700}.send-feedback.queued{color:#15803d}.send-feedback.failed{color:#b42318}.danger{color:#b42318;border-color:#f3c7c3}.error{max-width:1400px;margin:14px auto;background:#fff1f0;color:#b42318;padding:12px;border-radius:10px}.empty{color:#94a3b8}@media(max-width:800px){.campaign-page{padding:14px}.fields,.templates,.details{grid-template-columns:1fr}.recipients{grid-column:auto}.recipient{align-items:flex-start;gap:10px}}
.mode-picker{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin:16px 0}.mode-picker button{padding:14px;text-align:left}.mode-picker button.active{border-color:#168447;background:#edf8f1;box-shadow:inset 0 0 0 1px #168447}.mode-picker strong,.mode-picker span{display:block}.mode-picker span{margin-top:4px;color:#64748b;font-size:.78rem}@media(max-width:800px){.mode-picker{grid-template-columns:1fr}}
</style>
