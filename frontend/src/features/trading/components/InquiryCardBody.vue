<script setup>
import InquiryStockHints from './InquiryStockHints.vue'

defineProps({
  inquiry: { type: Object, required: true },
  hints: { type: Array, default: () => [] },
  expandedRow: { type: String, default: '' },
  matchingPending: { type: Boolean, default: false },
})

defineEmits(['toggle-row', 'verify', 'create-inquiry', 'auto-match', 'fix-match'])
</script>

<template>
  <div class="inquiry-card-body">
    <div class="body-row" :class="{ expanded: expandedRow === 'summary' }" @click.stop="$emit('toggle-row', 'summary')">
      <div class="label">Summary</div><div class="content">{{ inquiry.summary || '—' }}</div>
    </div>
    <div class="body-row" :class="{ expanded: expandedRow === 'message' }" @click.stop="$emit('toggle-row', 'message')">
      <div class="label">Original Message</div><div class="content">{{ inquiry.source_message_text || '—' }}</div>
    </div>
    <div class="body-row" :class="{ expanded: expandedRow === 'stock' }" @click.stop="$emit('toggle-row', 'stock')">
      <div class="label">Stock Suggestion</div>
      <div class="content"><InquiryStockHints :hints="hints" @verify="$emit('verify', $event)" @create-inquiry="$emit('create-inquiry', $event)" @auto-match="$emit('auto-match', $event)" @fix-match="$emit('fix-match', $event)" /></div>
    </div>
    <div v-if="matchingPending" class="pending">Product matching in progress. Extracted inquiry products are available now; inventory match results will update after V2 pass 2 completes.</div>
  </div>
</template>

<style scoped>
.inquiry-card-body{position:relative;display:flex;min-height:0;flex:1;flex-direction:column;gap:3px}.body-row{min-height:0;flex:1;overflow:hidden;padding:3px 6px;border-radius:var(--ui-radius-xs);cursor:pointer;transition:background-color .15s}.body-row:hover{background:var(--ui-surface-muted)}.body-row.expanded{background:var(--ui-info-soft)}.label{margin-bottom:1px;color:var(--ui-text-subtle);font-size:.62rem;font-weight:800;letter-spacing:.04em;text-transform:uppercase}.content{display:-webkit-box;overflow:hidden;color:var(--ui-text);font-size:.8rem;line-height:1.35;-webkit-box-orient:vertical;-webkit-line-clamp:2}.pending{margin:4px 6px 0;padding:6px 8px;border:1px solid color-mix(in srgb,var(--ui-warning) 35%,white);border-radius:var(--ui-radius-xs);background:var(--ui-warning-soft);color:var(--ui-warning);font-size:.74rem;line-height:1.35}
</style>
