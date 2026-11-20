<script setup>
import { computed } from 'vue'
import { formatCampaignPrice, suggestSymbol } from '../currency'
import { formatDateTime } from '@/utils/dateFormat'

// Edits campaign currency settings in place (the company's on Campaigns > Settings, or a
// campaign's own override). The parent saves; errors come back from the server by field.
const props = defineProps({
  settings: { type: Object, required: true },
  disabled: { type: Boolean, default: false },
  errors: { type: Object, default: () => ({}) },
})

const sample = computed(() => formatCampaignPrice(27, props.settings.primary.code, props.settings))

function codeChanged(currency) {
  currency.code = (currency.code || '').toUpperCase()
  const suggestion = suggestSymbol(currency.code)
  if (!currency.symbol || currency.symbol === currency._suggested) currency.symbol = suggestion || currency.code
  currency._suggested = currency.symbol
}
function addCurrency() {
  props.settings.others.push({ code: '', symbol: '', rate: null, enabled: true })
}
function removeCurrency(index) {
  props.settings.others.splice(index, 1)
}
const error = key => {
  const value = props.errors?.[key]
  return Array.isArray(value) ? value.join(' ') : value || ''
}
</script>

<template>
  <fieldset class="currency-form" :disabled="disabled">
    <div class="currency-form__row">
      <label>Primary currency
        <input v-model="settings.primary.code" maxlength="3" placeholder="AED" aria-label="Primary currency code" @change="codeChanged(settings.primary)" />
        <small v-if="error('primary.code')" class="currency-form__error">{{ error('primary.code') }}</small>
      </label>
      <label>Symbol
        <input v-model="settings.primary.symbol" maxlength="8" aria-label="Primary currency symbol" />
      </label>
      <label>Show currency as
        <select v-model="settings.label" aria-label="Show currency as">
          <option value="code">Code (AED)</option>
          <option value="symbol">Symbol</option>
          <option value="none">Amount only</option>
        </select>
      </label>
      <label>Position
        <select v-model="settings.label_position" :disabled="settings.label === 'none'" aria-label="Currency position">
          <option value="prefix">Before amount</option>
          <option value="suffix">After amount</option>
        </select>
      </label>
      <label>Decimals
        <input v-model.number="settings.decimals" type="number" min="0" max="4" aria-label="Decimal places" />
        <small v-if="error('decimals')" class="currency-form__error">{{ error('decimals') }}</small>
      </label>
      <label class="currency-form__check">
        <input v-model="settings.trim_zeros" type="checkbox" /> Hide trailing zeros
      </label>
      <label>Between currencies
        <input v-model="settings.separator" maxlength="10" aria-label="Separator between currencies" />
      </label>
    </div>

    <div class="currency-form__others">
      <div class="currency-form__others-head">
        <strong>Other currencies</strong>
        <small>Rate = how much of that currency one {{ settings.primary.code || 'primary' }} buys.</small>
      </div>
      <p v-if="!settings.others.length" class="currency-form__hint">None — prices show in {{ settings.primary.code || 'the primary currency' }} only.</p>
      <div v-for="(currency, index) in settings.others" :key="index" class="currency-form__other">
        <label class="currency-form__check"><input v-model="currency.enabled" type="checkbox" :aria-label="`Show ${currency.code || 'currency'}`" /> Show</label>
        <label>Code<input v-model="currency.code" maxlength="3" placeholder="USD" :aria-label="`Currency ${index + 1} code`" @change="codeChanged(currency)" /></label>
        <label>Symbol<input v-model="currency.symbol" maxlength="8" :aria-label="`Currency ${index + 1} symbol`" /></label>
        <label>Rate
          <input v-model.number="currency.rate" type="number" min="0" step="any" placeholder="0.2723" :aria-label="`Currency ${index + 1} rate`" />
        </label>
        <small v-if="currency.rate_updated_at" class="currency-form__hint">Rate set {{ formatDateTime(currency.rate_updated_at) }}</small>
        <button type="button" class="currency-form__remove" :aria-label="`Remove ${currency.code || 'currency'}`" @click="removeCurrency(index)">Remove</button>
        <small v-if="error(`others.${index}.code`) || error(`others.${index}.rate`)" class="currency-form__error">
          {{ error(`others.${index}.code`) || error(`others.${index}.rate`) }}
        </small>
      </div>
      <button type="button" class="currency-form__add" @click="addCurrency">+ Add currency</button>
    </div>

    <p class="currency-form__sample">Example: <code>{{ sample }}</code></p>
  </fieldset>
</template>

<style scoped>
.currency-form{display:grid;gap:12px;margin:0;padding:0;border:0;min-width:0}
.currency-form label{display:grid;gap:4px;color:var(--ui-text-muted,#64748b);font-size:.72rem;font-weight:700;text-transform:uppercase}
.currency-form input,.currency-form select{min-width:0;padding:7px 9px;border:1px solid var(--ui-border,#d0d7e2);border-radius:8px;background:var(--ui-surface,#fff);color:inherit;font:inherit;font-size:.84rem;text-transform:none}
.currency-form__row{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:10px;align-items:end}
.currency-form__check{display:flex!important;align-items:center;gap:6px;text-transform:none!important;font-size:.8rem!important}
.currency-form__others{display:grid;gap:8px}
.currency-form__others-head{display:flex;flex-wrap:wrap;align-items:baseline;gap:8px}
.currency-form__others-head small,.currency-form__hint{color:var(--ui-text-muted,#64748b);font-size:.74rem}
.currency-form__hint{margin:0}
.currency-form__other{display:grid;grid-template-columns:auto repeat(3,minmax(90px,1fr)) auto auto;gap:8px;align-items:end;padding:8px;border:1px solid var(--ui-border,#d0d7e2);border-radius:8px}
.currency-form__remove,.currency-form__add{justify-self:start;padding:6px 10px;border:1px solid var(--ui-border,#d0d7e2);border-radius:7px;background:var(--ui-surface,#fff);color:inherit;font-size:.78rem;cursor:pointer}
.currency-form__remove{color:var(--ui-danger,#dc2626)}
.currency-form__error{grid-column:1/-1;color:var(--ui-danger,#dc2626);font-size:.74rem;text-transform:none}
.currency-form__sample{margin:0;font-size:.82rem}
@media(max-width:720px){.currency-form__other{grid-template-columns:1fr 1fr}}
</style>
