<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { realEstateApi } from '@/api'
import { apiError } from '@/features/realEstate/apiErrors'

// Sale-or-rent price check used by Real Estate extraction (apps/real_estate/services/
// price_check.py): when a message does not say sale or rent, an amount far below the area's
// typical sale price is treated as a year's rent. The admin picks where that price comes from.
const DESCRIPTIONS = {
  off: 'No price check. Only the words in the message decide sale or rent.',
  model_knowledge: "The AI compares the amount with typical sale prices it knows for that area and unit type. No extra cost; good for big gaps (a year's rent vs a sale price), not exact current prices.",
  web_search: 'The AI searches the web for current prices before deciding. Extra cost on every message (OpenRouter web search) and slower; needs OpenRouter models with paid credit.',
  reference_table: "The AI uses the company's own sale price table below. Exact and free, but someone has to keep the prices up to date.",
}

const state = ref(null)
const mode = ref('')
const saving = ref(false)
const error = ref('')
const notice = ref('')
const rows = ref([])
const propertyTypes = ref([])
const rowError = ref('')
const busyRow = ref(null)
const blank = () => ({ location: '', property_type: null, bedrooms: null, sale_price_min: null, sale_price_max: null, currency: 'AED', notes: '' })
const draft = reactive(blank())
const editing = ref(null)

const changed = computed(() => state.value && mode.value !== state.value.mode)

async function load() {
  error.value = ''
  try {
    const [check, prices, types] = await Promise.all([
      realEstateApi.getPriceCheck(), realEstateApi.marketPrices(), realEstateApi.propertyTypes(),
    ])
    state.value = check.data
    mode.value = check.data.mode
    rows.value = prices.data
    propertyTypes.value = types.data.results || types.data
  } catch (exc) {
    error.value = apiError(exc, 'Unable to load the price check settings.')
  }
}

async function saveMode() {
  saving.value = true; error.value = ''; notice.value = ''
  try {
    state.value = (await realEstateApi.setPriceCheck(mode.value)).data
    notice.value = 'Saved. New messages use this price check.'
  } catch (exc) {
    error.value = apiError(exc, 'Unable to save the price check.')
  } finally {
    saving.value = false
  }
}

function payload(row) {
  const { location, property_type, bedrooms, sale_price_min, sale_price_max, currency, notes } = row
  return { location, property_type: property_type || null, bedrooms: bedrooms === '' ? null : bedrooms, sale_price_min, sale_price_max, currency, notes }
}

async function addRow() {
  busyRow.value = 'new'; rowError.value = ''
  try {
    rows.value = [...rows.value, (await realEstateApi.createMarketPrice(payload(draft))).data]
    Object.assign(draft, blank())
    if (state.value) state.value.table_rows = rows.value.length
  } catch (exc) {
    rowError.value = apiError(exc, 'Unable to add the price.')
  } finally {
    busyRow.value = null
  }
}

function startEdit(row) {
  editing.value = { ...row }
  rowError.value = ''
}

async function saveEdit() {
  busyRow.value = editing.value.id; rowError.value = ''
  try {
    const { data } = await realEstateApi.updateMarketPrice(editing.value.id, payload(editing.value))
    rows.value = rows.value.map(row => (row.id === data.id ? data : row))
    editing.value = null
  } catch (exc) {
    rowError.value = apiError(exc, 'Unable to save the price.')
  } finally {
    busyRow.value = null
  }
}

async function removeRow(row) {
  const inUse = state.value?.mode === 'reference_table' && rows.value.length === 1
  const message = inUse
    ? 'This is the last price and the price check uses this table: new messages will fail to process until you add a price or choose another check. Remove it?'
    : `Remove the price for ${row.location}?`
  if (!window.confirm(message)) return
  busyRow.value = row.id; rowError.value = ''
  try {
    await realEstateApi.deleteMarketPrice(row.id)
    rows.value = rows.value.filter(item => item.id !== row.id)
    if (state.value) state.value.table_rows = rows.value.length
  } catch (exc) {
    rowError.value = apiError(exc, 'Unable to remove the price.')
  } finally {
    busyRow.value = null
  }
}

function money(row) {
  const fmt = value => Number(value).toLocaleString('en-US', { maximumFractionDigits: 0 })
  return `${row.currency} ${fmt(row.sale_price_min)} to ${fmt(row.sale_price_max)}`
}

function bedroomsLabel(value) {
  if (value === null || value === undefined || value === '') return 'Any'
  return Number(value) === 0 ? 'Studio' : String(Number(value))
}

onMounted(load)
</script>

<template>
  <section class="price-check" aria-label="Sale or rent price check">
    <header>
      <h3>Sale or rent price check</h3>
      <p>
        Rent paid in cheques ("4 chqs") is always treated as leasing. When a message does not say sale
        or rent, an amount far below the area's typical sale price is treated as a year's rent. Choose
        where the typical sale price comes from.
      </p>
    </header>
    <p v-if="error" class="price-check__error" role="alert">{{ error }}</p>
    <p v-if="notice" class="price-check__notice">{{ notice }}</p>
    <template v-if="state">
      <div class="price-check__modes" role="radiogroup" aria-label="Price check source">
        <label v-for="choice in state.choices" :key="choice.value" :class="{ active: mode === choice.value }">
          <input v-model="mode" type="radio" name="price-check-mode" :value="choice.value" />
          <span>
            <strong>{{ choice.label }}</strong>
            <small>{{ DESCRIPTIONS[choice.value] }}</small>
            <small v-if="choice.value === 'web_search' && state.web_search_blockers.length" class="price-check__warn">
              Not available yet: the extraction AI uses {{ state.web_search_blockers.join(', ') }}.
            </small>
            <small v-if="choice.value === 'reference_table'" class="price-check__count">
              {{ rows.length }} price{{ rows.length === 1 ? '' : 's' }} in the table.
            </small>
          </span>
        </label>
      </div>
      <div class="price-check__actions">
        <button type="button" class="primary" :disabled="!changed || saving" @click="saveMode">{{ saving ? 'Saving...' : 'Save price check' }}</button>
      </div>

      <div class="price-check__table">
        <h4>Company sale price table</h4>
        <p>Typical sale prices by area. Leave the type or bedrooms empty to cover all of them.</p>
        <p v-if="rowError" class="price-check__error" role="alert">{{ rowError }}</p>
        <table>
          <thead>
            <tr><th>Area / building</th><th>Property type</th><th>Bedrooms</th><th>Sale price from</th><th>to</th><th>Currency</th><th>Notes</th><th></th></tr>
          </thead>
          <tbody>
            <tr v-for="row in rows" :key="row.id">
              <template v-if="editing?.id === row.id">
                <td><input v-model="editing.location" aria-label="Area" /></td>
                <td>
                  <select v-model="editing.property_type" aria-label="Property type">
                    <option :value="null">Any</option>
                    <option v-for="type in propertyTypes" :key="type.id" :value="type.id">{{ type.name }}</option>
                  </select>
                </td>
                <td><input v-model.number="editing.bedrooms" type="number" min="0" step="1" aria-label="Bedrooms" /></td>
                <td><input v-model.number="editing.sale_price_min" type="number" min="0" aria-label="Sale price from" /></td>
                <td><input v-model.number="editing.sale_price_max" type="number" min="0" aria-label="Sale price to" /></td>
                <td><input v-model="editing.currency" maxlength="3" aria-label="Currency" /></td>
                <td><input v-model="editing.notes" aria-label="Notes" /></td>
                <td class="price-check__row-actions">
                  <button type="button" :disabled="busyRow === row.id" @click="saveEdit">Save</button>
                  <button type="button" @click="editing = null">Cancel</button>
                </td>
              </template>
              <template v-else>
                <td>{{ row.location }}</td>
                <td>{{ row.property_type_name || 'Any' }}</td>
                <td>{{ bedroomsLabel(row.bedrooms) }}</td>
                <td colspan="3">{{ money(row) }}</td>
                <td>{{ row.notes }}</td>
                <td class="price-check__row-actions">
                  <button type="button" :disabled="busyRow === row.id" @click="startEdit(row)">Edit</button>
                  <button type="button" class="danger" :disabled="busyRow === row.id" @click="removeRow(row)">Remove</button>
                </td>
              </template>
            </tr>
            <tr class="price-check__new">
              <td><input v-model="draft.location" placeholder="e.g. Dubai Marina" aria-label="New area" /></td>
              <td>
                <select v-model="draft.property_type" aria-label="New property type">
                  <option :value="null">Any</option>
                  <option v-for="type in propertyTypes" :key="type.id" :value="type.id">{{ type.name }}</option>
                </select>
              </td>
              <td><input v-model.number="draft.bedrooms" type="number" min="0" step="1" placeholder="Any" aria-label="New bedrooms" /></td>
              <td><input v-model.number="draft.sale_price_min" type="number" min="0" placeholder="1800000" aria-label="New sale price from" /></td>
              <td><input v-model.number="draft.sale_price_max" type="number" min="0" placeholder="2600000" aria-label="New sale price to" /></td>
              <td><input v-model="draft.currency" maxlength="3" aria-label="New currency" /></td>
              <td><input v-model="draft.notes" placeholder="Optional" aria-label="New notes" /></td>
              <td class="price-check__row-actions">
                <button type="button" class="primary" :disabled="busyRow === 'new'" @click="addRow">Add price</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
  </section>
</template>

<style scoped>
.price-check{margin:0 0 16px;padding:16px;border:1px solid var(--ui-border,#e5e7eb);border-radius:10px;background:var(--ui-surface,#fff)}
.price-check h3{margin:0 0 4px;font-size:1rem}
.price-check h4{margin:18px 0 4px;font-size:.9rem}
.price-check header p,.price-check__table>p{margin:0 0 10px;color:var(--ui-text-muted,#6b7280);font-size:.82rem}
.price-check__modes{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:8px}
.price-check__modes label{display:flex;gap:8px;padding:10px;border:1px solid var(--ui-border,#e5e7eb);border-radius:8px;cursor:pointer}
.price-check__modes label.active{border-color:var(--ui-primary,#2563eb);background:var(--ui-primary-soft,#eff6ff)}
.price-check__modes span{display:flex;flex-direction:column;gap:3px}
.price-check__modes small{color:var(--ui-text-muted,#6b7280);font-size:.75rem;line-height:1.35}
.price-check__modes .price-check__warn{color:var(--ui-warning,#b45309);font-weight:600}
.price-check__modes .price-check__count{font-weight:600}
.price-check__actions{display:flex;justify-content:flex-end;margin-top:10px}
.price-check button{padding:5px 10px;border:1px solid var(--ui-border,#d1d5db);border-radius:6px;background:var(--ui-surface,#fff);color:inherit;font-size:.8rem;cursor:pointer}
.price-check button.primary{border-color:var(--ui-primary,#2563eb);background:var(--ui-primary,#2563eb);color:var(--ui-on-primary,#fff)}
.price-check button.danger{color:var(--ui-danger,#dc2626)}
.price-check button:disabled{opacity:.6;cursor:default}
.price-check__error{margin:6px 0;color:var(--ui-danger,#dc2626);font-size:.82rem;font-weight:600}
.price-check__notice{margin:6px 0;color:var(--ui-success,#16a34a);font-size:.82rem;font-weight:600}
.price-check table{width:100%;border-collapse:collapse;font-size:.8rem}
.price-check th{padding:6px;border-bottom:1px solid var(--ui-border,#e5e7eb);color:var(--ui-text-muted,#6b7280);font-weight:600;text-align:left}
.price-check td{padding:5px 6px;border-bottom:1px solid var(--ui-border,#f1f5f9);vertical-align:middle}
.price-check td input,.price-check td select{width:100%;min-width:70px;padding:4px 6px;border:1px solid var(--ui-border,#d1d5db);border-radius:5px;background:var(--ui-surface,#fff);color:inherit;font:inherit}
.price-check__row-actions{display:flex;gap:6px;justify-content:flex-end;white-space:nowrap}
.price-check__table{overflow-x:auto}
</style>
