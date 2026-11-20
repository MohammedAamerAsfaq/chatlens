<script setup>
import { ref, onMounted } from 'vue'
import { tradingReviewApi } from '@/api'

const pool = ref('all')
const sample = ref(null)
const label = ref(null)
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const done = ref(false)
const reviewed = ref(0)
const blankProduct = () => ({ name: '', quantity: '', price: '', currency: '' })

async function load() {
  loading.value = true
  error.value = ''
  try {
    const { data } = await tradingReviewApi.next(pool.value)
    done.value = !!data.done
    sample.value = data.done ? null : data
    if (!data.done) {
      reviewed.value = data.reviewed_count
      const ai = data.ai
      label.value = {
        is_inquiry: ai.is_inquiry,
        direction: ai.is_inquiry ? (['buy', 'sell', 'both'].includes(ai.direction) ? ai.direction : 'unknown') : '',
        products: ai.is_inquiry ? (ai.products || []).map(p => ({
          name: p.canonical_name || p.raw_text || '',
          quantity: p.quantity == null ? '' : String(p.quantity),
          price: p.price == null ? '' : String(p.price),
          currency: p.currency || '',
        })) : [],
        notes: '',
      }
    }
  } catch (e) { error.value = e.response?.data?.detail || 'Could not load a message.' }
  finally { loading.value = false }
}
function changeDecision() {
  if (!label.value.is_inquiry) { label.value.direction = ''; label.value.products = [] }
  else if (!label.value.direction) label.value.direction = 'unknown'
}
async function save() {
  saving.value = true
  error.value = ''
  try {
    await tradingReviewApi.submit({ message_id: sample.value.message_id, label: label.value })
    await load()
  } catch (e) { error.value = JSON.stringify(e.response?.data || 'Could not save the review.') }
  finally { saving.value = false }
}
onMounted(load)
</script>

<template>
  <main class="review-page">
    <header><div><h1>Trading AI Review</h1><p>Verify complete messages to build a human-reviewed parsing dataset. Saving a review does not change live inquiries.</p></div>
      <label>Message pool <select v-model="pool" @change="load"><option value="all">All classifications</option><option value="inquiry">AI: inquiry</option><option value="non_inquiry">AI: not an inquiry</option></select></label>
    </header>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <p v-if="loading">Loading message…</p>
    <p v-else-if="done">No unreviewed classified text messages in this pool.</p>
    <template v-else-if="sample && label">
      <section><div class="section-head"><h2>Original message</h2><span>{{ reviewed }} reviewed</span></div><pre>{{ sample.text }}</pre></section>
      <section><h2>AI draft</h2><p>{{ sample.ai.is_inquiry ? 'Inquiry' : 'Not an inquiry' }} · {{ sample.ai.direction || 'No direction' }} · {{ sample.ai.version }}</p><details><summary>View original AI products</summary><pre>{{ JSON.stringify(sample.ai.products, null, 2) }}</pre></details></section>
      <form @submit.prevent="save"><section><h2>Your review</h2>
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
        <button class="primary" type="submit" :disabled="saving">{{ saving ? 'Saving…' : 'Save verified review' }}</button>
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
.product { display: grid; grid-template-columns: 3fr 1fr 1fr 1fr auto; gap: 8px; align-items: end; } button { padding: 8px 12px; border: 1px solid #9eacba; border-radius: 5px; background: white; cursor: pointer; } .product button { margin-bottom: 12px; } .primary { background: #1766ae; color: white; border: 0; margin-top: 10px; } .error { color: #a42626; }
@media (max-width: 700px) { header { display: block; } .product { grid-template-columns: 1fr 1fr; } }
</style>
