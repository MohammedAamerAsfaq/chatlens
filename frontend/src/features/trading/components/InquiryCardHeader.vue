<script setup>
import { FontAwesomeIcon } from '@fortawesome/vue-fontawesome'
import { faXmark } from '@fortawesome/free-solid-svg-icons'

defineProps({
  inquiry: { type: Object, required: true },
  categoryValue: { type: String, default: '' },
  suggestionAvailable: { type: Boolean, default: false },
  fresh: { type: Boolean, default: false },
})

const emit = defineEmits(['set-category', 'apply-suggestion', 'set-status', 'close'])

const statusOptions = [
  ['requested_price', 'Requested Price'], ['quoted_waiting', 'Quoted - Waiting'],
  ['no_response', 'No Response'], ['price_high', 'Price High'], ['no_stock', 'No Stock'],
  ['currently_in_stock', 'Currently In Stock'], ['not_dealing', 'Not Dealing ATM'],
  ['irrelevant', 'Irrelevant'], ['closed', 'Close'], ['tracking', 'Tracking'],
  ['incorrect_match', 'Incorrect Match'],
]

function categoryLabel(value) {
  return { supplier: 'Supplier', customer: 'Customer', both: 'Both' }[value] || value
}

function formatAge(seconds) {
  const value = Number(seconds || 0)
  if (value < 60) return `${value}s`
  if (value < 3600) return `${Math.floor(value / 60)}m`
  return `${Math.floor(value / 3600)}h`
}

function selectStatus(event) {
  const value = event.target.value
  event.target.value = ''
  emit('set-status', value)
}
</script>

<template>
  <header class="inquiry-card-header">
    <div class="header-row">
      <span class="contact-name">
        {{ inquiry.contact_name || inquiry.contact_phone || 'Unknown' }}
        <span v-if="inquiry.contact_name && inquiry.contact_phone" class="contact-phone">{{ inquiry.contact_phone }}</span>
      </span>
      <select v-if="inquiry.contact" class="category-select" :class="{ suggested: suggestionAvailable }" :value="categoryValue" aria-label="Contact category" @change="$emit('set-category', $event.target.value)">
        <option value="">Uncategorized</option><option value="supplier">Supplier</option><option value="customer">Customer</option><option value="both">Both</option>
      </select>
      <button v-if="suggestionAvailable" type="button" class="suggestion" :title="`AI suggests: ${categoryLabel(inquiry.suggested_contact_category)} - click to confirm`" @click="$emit('apply-suggestion')">✓ Apply</button>
      <span class="source">{{ inquiry.source_type }}</span>
      <span v-if="inquiry.account_name" class="account">{{ inquiry.account_name }}</span>
      <select class="status-select" aria-label="Set inquiry status" @change="selectStatus">
        <option value="" disabled selected>Set status...</option>
        <option v-for="option in statusOptions" :key="option[0]" :value="option[0]">{{ option[1] }}</option>
      </select>
      <span class="age" :class="{ overdue: inquiry.age_seconds > 60 }">{{ formatAge(inquiry.age_seconds) }}</span>
      <button type="button" class="close" :disabled="fresh" :title="fresh ? 'Just appeared - wait a moment to avoid closing it by accident' : 'Close inquiry'" @click.stop="$emit('close')"><FontAwesomeIcon :icon="faXmark" /></button>
    </div>
  </header>
</template>

<style scoped>
.inquiry-card-header{flex-shrink:0;margin-bottom:8px;padding-bottom:8px;border-bottom:1px solid var(--ui-border)}.header-row{display:flex;flex-wrap:nowrap;align-items:center;gap:6px}.contact-name{min-width:0;flex-shrink:1;overflow:hidden;color:var(--ui-text-strong);font-size:.88rem;font-weight:700;text-overflow:ellipsis;white-space:nowrap}.contact-phone{margin-left:6px;color:var(--ui-text-muted);font-size:.78rem;font-weight:400}.category-select,.status-select{flex-shrink:0;padding:2px 6px;border:1px solid var(--ui-border-strong);border-radius:var(--ui-radius-xs);background:var(--ui-surface);color:var(--ui-text);font:500 .72rem var(--ui-font-sans);cursor:pointer}.category-select.suggested{border-color:var(--ui-warning);background:var(--ui-warning-soft);color:var(--ui-warning);font-weight:700}.suggestion{flex-shrink:0;padding:2px 8px;border:1px solid var(--ui-warning);border-radius:var(--ui-radius-pill);background:var(--ui-warning-soft);color:var(--ui-warning);font:700 .72rem var(--ui-font-sans);cursor:pointer}.source{flex-shrink:0;color:var(--ui-text-subtle);font-size:.73rem;text-transform:capitalize;white-space:nowrap}.account{flex-shrink:0;padding:1px 7px;border-radius:var(--ui-radius-pill);background:var(--ui-primary-soft);color:var(--ui-primary);font-size:.7rem;font-weight:700;white-space:nowrap}.status-select{padding:4px 8px;font-size:.78rem}.age{flex-shrink:0;color:var(--ui-text-muted);font-size:.78rem;white-space:nowrap}.age.overdue{color:var(--ui-danger);font-weight:700}.close{display:grid;width:25px;height:25px;flex-shrink:0;place-items:center;border:1px solid transparent;border-radius:var(--ui-radius-xs);background:transparent;color:var(--ui-text-subtle);cursor:pointer}.close:hover:not(:disabled){border-color:color-mix(in srgb,var(--ui-danger) 35%,white);background:var(--ui-danger-soft);color:var(--ui-danger)}.close:disabled{opacity:.45;cursor:not-allowed}@media(max-width:900px){.header-row{flex-wrap:wrap}}
</style>
