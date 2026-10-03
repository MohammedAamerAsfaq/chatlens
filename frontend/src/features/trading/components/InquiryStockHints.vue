<script setup>
defineProps({ hints: { type: Array, default: () => [] } })
defineEmits(['verify', 'create-inquiry', 'auto-match', 'fix-match'])
</script>

<template>
  <div v-if="hints.length" class="stock-hints">
    <div v-for="hint in hints" :key="hint.index ?? hint.name" class="stock-hint" :class="hint.presentationClass">
      <span class="stock-icon">{{ hint.icon }}</span>
      {{ hint.product.name }} {{ hint.availabilityLabel }}
      <span v-if="hint.mismatch" class="mismatch">— not "{{ hint.name }}", closest match only</span>
      <span v-if="hint.product.sale_price"> · Sale: {{ hint.product.currency || 'USD' }} {{ hint.product.sale_price }}</span>
      <span> · Qty: {{ hint.product.qty }}</span>
      <span v-if="hint.product.cost_price"> · <span :class="{ loss: hint.product.sale_price != null && hint.product.sale_price < hint.product.cost_price }">Cost: {{ hint.product.currency || 'USD' }} {{ hint.product.cost_price }}</span></span>
      <span class="actions">
        <button type="button" class="verify" :disabled="hint.verification?.loading" title="Ask AI to compare the source and this stock suggestion" @click.stop="$emit('verify', hint)">{{ hint.verification?.loading ? 'Checking' : 'Verify' }}</button>
        <button type="button" class="create" :disabled="hint.createState?.loading || hint.createState?.saved" title="Save this stock suggestion as an inquiry product trace" @click.stop="$emit('create-inquiry', hint)">{{ hint.createLabel }}</button>
        <button v-if="hint.mismatch" type="button" class="auto" title="Auto-search inventory for the correct product" @click.stop="$emit('auto-match', hint)">Auto</button>
        <button v-if="hint.mismatch" type="button" title="Pick the correct product" @click.stop="$emit('fix-match', hint)">Fix</button>
      </span>
      <div v-if="hint.verification" class="verification" :class="`verdict-${hint.verification.verdict || 'unknown'}`">
        <strong>{{ hint.verificationLabel }}</strong><span v-if="hint.verification.reason"> - {{ hint.verification.reason }}</span><span v-if="hint.verification.error"> - {{ hint.verification.error }}</span>
      </div>
      <div v-if="hint.createState?.error" class="create-error">{{ hint.createState.error }}</div>
    </div>
  </div>
  <span v-else class="empty">No matching stock found</span>
</template>

<style scoped>
.stock-hints{display:flex;flex-direction:column;gap:3px}.stock-hint{padding:4px 8px;border:1px solid color-mix(in srgb,var(--ui-success) 30%,white);border-radius:var(--ui-radius-xs);background:var(--ui-success-soft);color:var(--ui-success);font-size:.75rem;line-height:1.4}.stock-hint.stock-hint-mismatch{border-color:color-mix(in srgb,var(--ui-warning) 35%,white);background:var(--ui-warning-soft);color:var(--ui-warning)}.stock-hint.stock-hint-out{border-color:#fdba74;background:#fff7ed;color:#9a3412}.stock-icon{font-weight:800}.mismatch{font-weight:700}.loss{color:var(--ui-danger);font-weight:800}.actions{float:right;display:inline-flex;gap:4px}.actions button{padding:1px 5px;border:1px solid var(--ui-warning);border-radius:var(--ui-radius-xs);background:var(--ui-surface);color:var(--ui-warning);font:700 .66rem var(--ui-font-sans);cursor:pointer}.actions button.auto{border-color:var(--ui-info);color:var(--ui-info)}.actions button.verify{border-color:var(--ui-text-muted);color:var(--ui-text)}.actions button.create{border-color:var(--ui-success);color:var(--ui-success)}.actions button:disabled{opacity:.65;cursor:wait}.verification,.create-error{clear:both;margin-top:4px;padding:3px 6px;border-radius:var(--ui-radius-xs);background:var(--ui-surface);font-size:.7rem}.create-error,.verdict-rejected{color:var(--ui-danger)}.verdict-accepted{color:var(--ui-success)}.empty{color:var(--ui-text-subtle);font-style:italic}
</style>
