<script setup>
import { ref, onMounted } from 'vue'
import { tradingReviewApi } from '@/api'

const mode = ref('batch')
const sample = ref(null)
const after = ref(0)
const label = ref(null)
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const done = ref(false)
const unavailable = ref(false)
const progress = ref(null)
const editing = ref(false)
const blankProduct = () => ({ name: '', quantity: '', price: '', currency: '' })

async function load() {
  loading.value = true
  error.value = ''
  try {
    const { data } = mode.value === 'batch' ? await tradingReviewApi.batchNext(after.value) : await tradingReviewApi.reviewNext(mode.value === 'evaluation' ? 'ai' : mode.value, after.value, mode.value === 'evaluation' ? 'evaluation' : 'all')
    unavailable.value = data.available === false
    done.value = !!data.done
    sample.value = (data.done || unavailable.value) ? null : data
    editing.value = false
    if (mode.value === 'batch' && data.available) progress.value = { name: data.batch_name, completed: data.completed, total: data.total }
    if (sample.value) {
      if (data.label) {
        label.value = JSON.parse(JSON.stringify(data.label))
        if (data.origin === 'ai' && label.value.notes?.startsWith('AI review by OpenAI Codex;')) label.value.notes = ''
      } else {
        const ai = data.ai
        label.value = { is_inquiry: ai.is_inquiry,
          direction: ai.is_inquiry ? (['buy', 'sell', 'both'].includes(ai.direction) ? ai.direction : 'unknown') : '',
          products: ai.is_inquiry ? (ai.products || []).map(p => ({ name: p.canonical_name || p.raw_text || '', quantity: p.quantity == null ? '' : String(p.quantity), price: p.price == null ? '' : String(p.price), currency: p.currency || '' })) : [], notes: '' }
      }
    }
  } catch (e) { error.value = e.response?.data?.detail || 'Could not load a message.' }
  finally { loading.value = false }
}
function changeDecision() {
  if (!label.value.is_inquiry) { label.value.direction = ''; label.value.products = [] }
  else if (!label.value.direction) label.value.direction = 'unknown'
}
function changeMode() { after.value = 0; progress.value = null; load() }
function skip() { after.value = mode.value === 'batch' ? sample.value.position : sample.value.review_id; load() }
async function save() {
  if (saving.value || loading.value) return
  saving.value = true
  error.value = ''
  try {
    if (mode.value === 'batch') await tradingReviewApi.submit({ message_id: sample.value.message_id, label: label.value })
    else {
      const currentId = sample.value.review_id
      await tradingReviewApi.correct({ review_id: currentId, expected_label: sample.value.label, label: label.value })
      after.value = currentId
    }
    await load()
  } catch (e) { error.value = JSON.stringify(e.response?.data || 'Could not save the review.') }
  finally { saving.value = false }
}
onMounted(load)
</script>

<template>
  <main class="review-page">
    <header><div><h1>Trading AI Review</h1><p>Verify messages and correct saved reviews. Saving a review does not change live inquiries.</p></div>
      <label>Review work <select v-model="mode" @change="changeMode"><option value="evaluation">Check evaluation sample</option><option value="batch">Selected batch</option><option value="ai">Check all AI reviews</option><option value="human">Correct human reviews</option></select></label>
    </header>
    <p v-if="mode === 'evaluation'">AI reviews assigned to the held-out validation or test groups. Confirming one adds your human label to that evaluation split.</p>
    <p v-if="progress">{{ progress.name }}: {{ progress.completed }} / {{ progress.total }} reviewed</p>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <p v-if="loading">Loading message…</p>
    <p v-else-if="unavailable">No review batch has been imported yet.</p>
    <p v-else-if="done">No more messages after this position. Switch review work to restart.</p>
    <template v-else-if="sample && label">
      <section><div class="section-head"><h2>Original message</h2><span v-if="mode === 'batch'">{{ sample.duplicate_count }} linked copies ? AI pool: {{ sample.sampling_pool }}</span><span v-else>Saved {{ sample.origin }} review #{{ sample.review_id }}</span></div><pre>{{ sample.text }}</pre></section>
      <section class="decision">
        <h2>{{ mode === 'batch' ? 'AI draft to verify' : 'Saved review to verify' }}</h2>
        <p>Check the direction and every product line against the original message before confirming.</p>
        <div class="decision-kind">{{ label.is_inquiry ? 'Inquiry ? ' + ({ buy: 'Buy', sell: 'Sell', both: 'Buy and sell', unknown: 'Direction unknown' }[label.direction] || 'Direction missing') : 'Not an inquiry' }}</div>
        <template v-if="label.is_inquiry">
          <p v-if="!label.products.length" class="empty-products">No product lines extracted.</p>
          <ul v-else class="product-summary">
            <li v-for="(product, index) in label.products" :key="index">
              <strong>{{ product.name || 'Missing product name' }}</strong>
              <span>Quantity: {{ product.quantity || 'Not specified' }}</span>
              <span>Price: {{ product.price || 'Not specified' }}{{ product.currency ? ' ' + product.currency : '' }}</span>
            </li>
          </ul>
        </template>
        <p v-if="label.notes" class="review-notes">Review notes: {{ label.notes }}</p>
        <p v-if="mode === 'ai' || mode === 'evaluation'">This is an AI review. Your confirmation records a human decision and keeps the prior AI label in history.</p>
        <details><summary>View original AI output</summary><pre>{{ JSON.stringify(sample.ai, null, 2) }}</pre></details>
        <div v-if="!editing" class="actions">
          <button type="button" class="primary" :disabled="saving || (label.is_inquiry && label.products.some(p => !p.name || !p.name.trim()))" @click="save">{{ saving ? 'Saving?' : 'Correct' }}</button>
          <button type="button" :disabled="saving" @click="editing = true">Needs correction</button>
          <button type="button" :disabled="saving" @click="skip">Skip</button>
        </div>
        <p v-if="!editing && label.is_inquiry && label.products.some(p => !p.name || !p.name.trim())" class="error">A product name is missing. Choose Needs correction to fix or remove it.</p>
      </section>
      <form v-if="editing" @submit.prevent="save"><section><h2>Correct this review</h2>
        <label>Is this an inquiry? <select v-model="label.is_inquiry" @change="changeDecision"><option :value="true">Yes</option><option :value="false">No</option></select></label>
        <template v-if="label.is_inquiry"><label>Direction <select v-model="label.direction"><option value="buy">Buy</option><option value="sell">Sell</option><option value="both">Both</option><option value="unknown">Unknown</option></select></label>
          <h3>Product lines</h3><p>Correct the draft and add any missing lines. Leave unknown fields blank.</p>
          <div v-for="(product, index) in label.products" :key="index" class="product">
            <label>Product <input v-model.trim="product.name" required maxlength="500"></label>
            <label>Quantity <input v-model="product.quantity" maxlength="100"></label>
            <label>Price <input v-model="product.price" maxlength="100"></label>
            <label>Currency <input v-model="product.currency" maxlength="20"></label>
            <button type="button" @click="label.products.splice(index, 1)">Remove</button>
          </div><button type="button" @click="label.products.push(blankProduct())">Add product</button>
        </template>
        <label>Review notes <textarea v-model="label.notes" maxlength="2000" rows="2" /></label>
        <div class="actions"><button type="button" @click="skip" :disabled="saving">Skip</button>
        <button class="primary" type="submit" :disabled="saving">{{ saving ? 'Saving?' : 'Save correction' }}</button></div>
      </section></form>
    </template>
  </main>
</template>

<style scoped>
.review-page { max-width: 1100px; margin: auto; padding: 24px; overflow: auto; height: 100%; color: #202a34; }
header, .section-head { display: flex; justify-content: space-between; gap: 20px; align-items: start; }
h1, h2, h3 { margin: 0 0 10px; } h1 { font-size: 1.6rem; } h2 { font-size: 1.1rem; } h3 { margin-top: 20px; font-size: 1rem; }
p { color: #596573; } section { background: white; border: 1px solid #dce2e7; border-radius: 10px; padding: 18px; margin: 16px 0; }
pre { white-space: pre-wrap; overflow-wrap: anywhere; font: inherit; background: #f6f8fa; padding: 12px; border-radius: 6px; }
label { display: grid; gap: 5px; margin: 12px 0; font-weight: 600; font-size: .9rem; } input, select, textarea { border: 1px solid #b5c0ca; border-radius: 5px; padding: 8px; font: inherit; min-width: 0; }
.decision-kind { font-weight: 700; font-size: 1.05rem; margin: 12px 0; }
.product-summary { padding: 0; list-style: none; } .product-summary li { display: flex; flex-wrap: wrap; gap: 8px 20px; padding: 10px 0; border-bottom: 1px solid #e5e9ed; } .product-summary li strong { min-width: 240px; } .product-summary li span { color: #596573; } .actions { display: flex; gap: 8px; align-items: center; margin-top: 16px; } .actions .primary { margin-top: 0; }
.product { display: grid; grid-template-columns: 3fr 1fr 1fr 1fr auto; gap: 8px; align-items: end; } button { padding: 8px 12px; border: 1px solid #9eacba; border-radius: 5px; background: white; cursor: pointer; } .product button { margin-bottom: 12px; } .primary { background: #1766ae; color: white; border: 0; margin-top: 10px; } .error { color: #a42626; }
@media (max-width: 700px) { header { display: block; } .product { grid-template-columns: 1fr 1fr; } }
</style>
