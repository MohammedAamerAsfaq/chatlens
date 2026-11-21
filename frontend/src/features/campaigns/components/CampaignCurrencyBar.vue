<script setup>
import { computed, ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import CampaignCurrencyForm from './CampaignCurrencyForm.vue'
import { DEFAULT_CURRENCY_SETTINGS, blankCurrencySettings, brandShown, formatCampaignPrice, settingsFor } from '../currency'

// How this campaign shows prices and product names (brand shown or not). The company settings
// (Campaigns > Settings) are the default;
// any choice made here gives the campaign its own copy, which "Use company default" discards.
// `save(currencySettings | null)` is the campaign's update request; its data is emitted as `saved`.
const props = defineProps({
  campaign: { type: Object, required: true },
  company: { type: Object, default: null },
  save: { type: Function, required: true },
})
const emit = defineEmits(['saved'])

const auth = useAuthStore()
const canEdit = computed(() => auth.hasPermission('campaigns.campaigns.update'))
const own = computed(() => props.campaign.currency_settings || null)
const companySettings = computed(() => props.company || DEFAULT_CURRENCY_SETTINGS)
const effective = computed(() => settingsFor(props.campaign, props.company))
const others = computed(() => effective.value.others || [])
const multiple = computed(() => others.value.some(row => row.enabled))
const sample = computed(() => formatCampaignPrice(27, effective.value.primary.code, effective.value))
const busy = ref(false)
const error = ref('')
const draft = ref(null)
const draftErrors = ref({})

function message(exc) {
  const data = exc?.response?.data
  if (data?.detail) return data.detail
  if (data && typeof data === 'object') return Object.values(data).flat(Infinity).map(String).join(' ')
  return 'Unable to save the currency settings.'
}
async function persist(settings) {
  busy.value = true; error.value = ''; draftErrors.value = {}
  try {
    const { data } = await props.save(settings)
    emit('saved', data)
    return true
  } catch (exc) {
    error.value = message(exc)
    // Invalid settings come back keyed by field ('primary.code', 'others.0.rate').
    const data = exc?.response?.data
    if (data && typeof data === 'object' && !data.detail) draftErrors.value = data
    return false
  } finally {
    busy.value = false
  }
}
// A change starts from what the campaign shows now, so switching to "This campaign" keeps the look.
const startingPoint = () => blankCurrencySettings(effective.value)

function useCompany() {
  if (own.value) { draft.value = null; persist(null) }
}
function useOwn() {
  if (!own.value) persist(blankCurrencySettings(companySettings.value))
}
function setCurrencies(value) {
  const settings = startingPoint()
  settings.others.forEach(row => { row.enabled = value === 'multiple' })
  persist(settings)
}
function setBrand(value) {
  const settings = startingPoint()
  settings.show_brand = value === 'show'
  persist(settings)
}
function setLabel(value) {
  const settings = startingPoint()
  settings.label = value
  persist(settings)
}
function toggleMore() {
  draft.value = draft.value ? null : startingPoint()
  draftErrors.value = {}
}
async function saveDraft() {
  if (await persist(draft.value)) draft.value = null
}
</script>

<template>
  <section class="currency-bar" aria-label="Campaign currency">
    <div class="currency-bar__row">
      <strong class="currency-bar__title">Message settings</strong>
      <div class="currency-bar__switch" role="group" aria-label="Message settings source">
        <button type="button" :class="{ active: !own }" :disabled="!canEdit || busy" @click="useCompany">Company default</button>
        <button type="button" :class="{ active: own }" :disabled="!canEdit || busy" @click="useOwn">This campaign</button>
      </div>
      <label>Currencies
        <select :value="multiple ? 'multiple' : 'one'" :disabled="!canEdit || busy" aria-label="Number of currencies" @change="setCurrencies($event.target.value)">
          <option value="one">One ({{ effective.primary.code }})</option>
          <option value="multiple" :disabled="!others.length">
            {{ others.length ? `Multiple (${[effective.primary.code, ...others.map(row => row.code)].join(', ')})` : 'Multiple (none set up)' }}
          </option>
        </select>
      </label>
      <label>Show as
        <select :value="effective.label" :disabled="!canEdit || busy" aria-label="Show currency as" @change="setLabel($event.target.value)">
          <option value="code">Code</option>
          <option value="symbol">Symbol</option>
          <option value="none">Hidden (amount only)</option>
        </select>
      </label>
      <label>Brand
        <select :value="brandShown(effective) ? 'show' : 'hide'" :disabled="!canEdit || busy" aria-label="Brand in product names" @change="setBrand($event.target.value)">
          <option value="show">Show (Apple iPhone 11)</option>
          <option value="hide">Hide (iPhone 11)</option>
        </select>
      </label>
      <button v-if="canEdit" type="button" class="currency-bar__more" :disabled="busy" @click="toggleMore">{{ draft ? 'Close options' : 'More options' }}</button>
      <span class="currency-bar__sample">e.g. <code>{{ sample }}</code></span>
    </div>
    <p class="currency-bar__hint">
      <template v-if="own">This campaign uses its own currency and brand settings.</template>
      <template v-else>Following the company settings; changing an option here gives this campaign its own.</template>
      <template v-if="!others.length"> Add other currencies and their rates in Campaigns &rsaquo; Settings, or under More options.</template>
    </p>
    <p v-if="error" class="currency-bar__error" role="alert">{{ error }}</p>
    <div v-if="draft" class="currency-bar__more-panel">
      <CampaignCurrencyForm :settings="draft" :errors="draftErrors" :disabled="busy" />
      <div class="currency-bar__actions">
        <button type="button" :disabled="busy" @click="draft = null">Cancel</button>
        <button type="button" class="primary" :disabled="busy" @click="saveDraft">{{ busy ? 'Saving...' : 'Save for this campaign' }}</button>
      </div>
    </div>
  </section>
</template>

<style scoped>
.currency-bar{display:grid;gap:6px;margin:10px 0;padding:10px 12px;border:1px solid var(--ui-border,#d0d7e2);border-radius:10px;background:var(--ui-surface-raised,#fff)}
.currency-bar__row{display:flex;flex-wrap:wrap;align-items:center;gap:10px}
.currency-bar__title{font-size:.86rem}
.currency-bar label{display:flex;align-items:center;gap:6px;color:var(--ui-text-muted,#64748b);font-size:.78rem;font-weight:600}
.currency-bar select{padding:5px 8px;border:1px solid var(--ui-border,#d0d7e2);border-radius:7px;background:var(--ui-surface,#fff);color:inherit;font:inherit;font-size:.8rem}
.currency-bar__switch{display:inline-flex;border:1px solid var(--ui-border,#d0d7e2);border-radius:8px;overflow:hidden}
.currency-bar__switch button{padding:5px 10px;border:0;background:var(--ui-surface,#fff);color:inherit;font-size:.78rem;font-weight:600;cursor:pointer}
.currency-bar__switch button+button{border-left:1px solid var(--ui-border,#d0d7e2)}
.currency-bar__switch button.active{background:var(--ui-primary,#2563eb);color:var(--ui-on-primary,#fff)}
.currency-bar button:disabled{opacity:.6;cursor:default}
.currency-bar__more,.currency-bar__actions button{padding:5px 10px;border:1px solid var(--ui-border,#d0d7e2);border-radius:7px;background:var(--ui-surface,#fff);color:inherit;font-size:.78rem;font-weight:600;cursor:pointer}
.currency-bar__actions{display:flex;justify-content:flex-end;gap:8px;margin-top:10px}
.currency-bar__actions .primary{border-color:var(--ui-primary,#2563eb);background:var(--ui-primary,#2563eb);color:var(--ui-on-primary,#fff)}
.currency-bar__sample{color:var(--ui-text-muted,#64748b);font-size:.78rem}
.currency-bar__hint{margin:0;color:var(--ui-text-muted,#64748b);font-size:.74rem}
.currency-bar__error{margin:0;color:var(--ui-danger,#dc2626);font-size:.78rem;font-weight:600}
.currency-bar__more-panel{padding-top:8px;border-top:1px solid var(--ui-border,#d0d7e2)}
</style>
