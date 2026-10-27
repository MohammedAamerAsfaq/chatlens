<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { accountsApi, contactsApi, tradingApi } from '@/api'
import UiButton from '@/components/ui/UiButton.vue'
import UiCard from '@/components/ui/UiCard.vue'
import UiFormField from '@/components/ui/UiFormField.vue'
import UiNotice from '@/components/ui/UiNotice.vue'
import UiPage from '@/components/ui/UiPage.vue'
import UiPageHeader from '@/components/ui/UiPageHeader.vue'
import UiRadioGroup from '@/components/ui/UiRadioGroup.vue'
import UiSelect from '@/components/ui/UiSelect.vue'

const router = useRouter()
const accounts = ref([])
const loading = ref(true)
const saving = ref(false)
const error = ref('')

const typeOptions = [
  { value: 'buy', label: 'WTB (Buying)' },
  { value: 'sell', label: 'WTS (Selling)' },
]
const statusOptions = [
  { value: 'open', label: 'Open' },
  { value: 'requested_price', label: 'Requested Price' },
  { value: 'quoted_waiting', label: 'Quoted - Waiting' },
  { value: 'tracking', label: 'Tracking' },
]

function emptyItem() {
  return {
    product_id: null, product_search: '', product_results: [],
    canonical_name: '', quantity: '', price: '', currency: '',
  }
}

const form = reactive({
  account_id: '', contact_id: '', contact_search: '', contact_results: [],
  inquiry_type: 'buy', status: 'open', summary: '', remarks: '',
  items: [emptyItem()],
})

const accountOptions = computed(() => accounts.value.map(a => ({ value: a.id, label: a.display_name || a.phone_number || `Account ${a.id}` })))

function rows(response) { return response.data.results || response.data || [] }

async function loadAccounts() {
  loading.value = true
  error.value = ''
  try {
    accounts.value = await rows(await accountsApi.list())
    if (!form.account_id && accounts.value.length) form.account_id = accounts.value[0].id
  } catch (exc) {
    error.value = exc.response?.data?.detail || 'Unable to load accounts.'
  } finally {
    loading.value = false
  }
}

async function searchContacts() {
  const query = form.contact_search.trim()
  if (!query || !form.account_id) { form.contact_results = []; return }
  form.contact_results = await rows(await contactsApi.list({ search: query, account: form.account_id, page_size: 10 }))
}

function pickContact(contact) {
  form.contact_id = contact.id
  form.contact_search = contact.display_name || contact.push_name || contact.phone_number
  form.contact_results = []
}

function clearContact() {
  form.contact_id = ''
  form.contact_search = ''
}

async function searchProducts(item) {
  const query = item.product_search.trim()
  if (!query) { item.product_results = []; return }
  item.product_results = await rows(await tradingApi.listProducts({ search: query, page_size: 10 }))
}

function pickProduct(item, product) {
  item.product_id = product.id
  item.product_search = `${product.brand ? `${product.brand} ` : ''}${product.name}`.trim()
  item.canonical_name = item.product_search
  if (!item.currency) item.currency = product.currency
  item.product_results = []
}

function clearProduct(item) {
  item.product_id = null
  item.product_search = ''
}

function addItem() { form.items.push(emptyItem()) }
function removeItem(index) { form.items.splice(index, 1) }

async function submit() {
  saving.value = true
  error.value = ''
  try {
    const payload = {
      account_id: form.account_id,
      contact_id: form.contact_id || null,
      inquiry_type: form.inquiry_type,
      status: form.status,
      summary: form.summary,
      remarks: form.remarks,
      items: form.items.map(item => ({
        product_id: item.product_id,
        canonical_name: item.canonical_name,
        quantity: item.quantity === '' ? null : item.quantity,
        price: item.price === '' ? null : item.price,
        currency: item.currency,
      })),
    }
    await tradingApi.createManualInquiry(payload)
    await router.push({ name: 'trading' })
  } catch (exc) {
    const data = exc.response?.data
    error.value = typeof data === 'string'
      ? data
      : (data?.detail || Object.values(data || {})[0] || 'Unable to create the inquiry.')
  } finally {
    saving.value = false
  }
}

onMounted(loadAccounts)
</script>

<template>
  <UiPage>
    <UiPageHeader eyebrow="Trading" title="Create inquiry" description="Manually record a WTB/WTS inquiry and place it on the Trading board.">
      <template #actions>
        <UiButton @click="router.push({ name: 'trading' })">Cancel</UiButton>
        <UiButton variant="primary" type="submit" form="manual-inquiry-form" :disabled="saving || loading">{{ saving ? 'Saving...' : 'Create inquiry' }}</UiButton>
      </template>
    </UiPageHeader>
    <UiNotice v-if="error" tone="danger">{{ error }}</UiNotice>

    <form id="manual-inquiry-form" class="inquiry-form" @submit.prevent="submit">
      <UiCard title="Inquiry source" subtitle="Which account and contact this inquiry is for.">
        <div class="form-grid">
          <UiRadioGroup v-model="form.inquiry_type" label="Inquiry type" :options="typeOptions" required class="wide" />
          <UiFormField label="Account"><UiSelect v-model="form.account_id" :options="accountOptions" placeholder="Select a WhatsApp account" searchable required /></UiFormField>
          <UiFormField label="Workflow status"><UiSelect v-model="form.status" :options="statusOptions" /></UiFormField>
          <UiFormField label="Contact" class="wide" hint="Search an existing WhatsApp contact on the selected account, or leave blank.">
            <div class="contact-picker">
              <input
                v-model="form.contact_search"
                :disabled="!form.account_id"
                placeholder="Search contacts"
                @input="searchContacts"
              />
              <UiButton v-if="form.contact_id" type="button" variant="outline" size="small" @click="clearContact">Clear</UiButton>
            </div>
            <div v-if="form.contact_results.length" class="results">
              <button v-for="contact in form.contact_results" :key="contact.id" type="button" @click="pickContact(contact)">
                <b>{{ contact.display_name || contact.push_name || contact.phone_number }}</b>
                <small>{{ contact.phone_number }}</small>
              </button>
            </div>
          </UiFormField>
          <UiFormField label="Summary" class="wide"><input v-model="form.summary" required placeholder="e.g. Buying 10x Phone X" /></UiFormField>
          <UiFormField label="Remarks" class="wide"><textarea v-model="form.remarks" rows="3" placeholder="Optional internal notes"></textarea></UiFormField>
        </div>
      </UiCard>

      <UiCard title="Products" subtitle="Match against existing inventory where possible, or type a free-text product name.">
        <div class="items">
          <article v-for="(item, index) in form.items" :key="index" class="item-row">
            <div class="form-grid">
              <UiFormField label="Product" class="wide" hint="Search inventory, or type a name below if there's no match.">
                <div class="contact-picker">
                  <input v-model="item.product_search" placeholder="Search products" @input="searchProducts(item)" />
                  <UiButton v-if="item.product_id" type="button" variant="outline" size="small" @click="clearProduct(item)">Clear match</UiButton>
                </div>
                <div v-if="item.product_results.length" class="results">
                  <button v-for="product in item.product_results" :key="product.id" type="button" @click="pickProduct(item, product)">
                    <b>{{ product.brand ? `${product.brand} ` : '' }}{{ product.name }}</b>
                    <small>Qty {{ product.qty }} · {{ product.currency }} {{ product.sale_price ?? '-' }}</small>
                  </button>
                </div>
              </UiFormField>
              <UiFormField label="Product name" hint="Prefilled from the matched product; edit for free-text entries."><input v-model="item.canonical_name" required /></UiFormField>
              <UiFormField label="Quantity"><input v-model="item.quantity" type="number" min="0" step="any" /></UiFormField>
              <UiFormField label="Price"><input v-model="item.price" type="number" min="0" step="any" /></UiFormField>
              <UiFormField label="Currency"><input v-model="item.currency" maxlength="10" placeholder="AED" /></UiFormField>
            </div>
            <UiButton v-if="form.items.length > 1" type="button" variant="outline" size="small" @click="removeItem(index)">Remove this line</UiButton>
          </article>
          <UiButton type="button" @click="addItem">+ Add another product line</UiButton>
        </div>
      </UiCard>

      <div class="footer-actions">
        <UiButton @click="router.push({ name: 'trading' })">Cancel</UiButton>
        <UiButton variant="primary" type="submit" :disabled="saving || loading">{{ saving ? 'Saving...' : 'Create inquiry' }}</UiButton>
      </div>
    </form>
  </UiPage>
</template>

<style scoped>
.inquiry-form,.items{display:grid;gap:20px}
.form-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}
.wide{grid-column:1/-1}
.item-row{display:grid;gap:12px;padding:16px;border:1px solid var(--ui-border);border-radius:var(--ui-radius-md);background:var(--ui-surface-muted)}
.contact-picker{position:relative;display:flex;gap:8px}
.contact-picker input{flex:1;min-width:0}
.results{position:relative;z-index:5;display:flex;max-height:210px;flex-direction:column;overflow:auto;border:1px solid var(--ui-border-strong);border-radius:var(--ui-radius-sm);background:var(--ui-surface);box-shadow:var(--ui-shadow-lg)}
.results button{display:flex;flex-direction:column;align-items:flex-start;padding:8px 10px;border:0;border-bottom:1px solid var(--ui-border);background:transparent;color:var(--ui-text);text-align:left;cursor:pointer}
.results button:hover{background:var(--ui-surface-muted)}
.results small{color:var(--ui-text-subtle)}
input,textarea{width:100%;padding:9px;border:1px solid var(--ui-border-strong);border-radius:var(--ui-radius-sm);background:var(--ui-surface);color:var(--ui-text);font:inherit}
input:focus,textarea:focus{border-color:var(--ui-primary);box-shadow:var(--ui-focus-ring);outline:0}
.footer-actions{display:flex;justify-content:flex-end;gap:10px;padding-bottom:24px}
@media(max-width:760px){.form-grid{grid-template-columns:1fr}.wide{grid-column:auto}}
</style>
