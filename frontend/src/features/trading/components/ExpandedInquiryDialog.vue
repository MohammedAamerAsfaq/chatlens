<script setup>
import InquiryStockHints from './InquiryStockHints.vue'
defineProps({ inquiry: { type: Object, default: null }, row: { type: String, default: '' }, title: { type: String, default: '' }, drag: { type: Object, required: true }, hints: { type: Array, default: () => [] } })
defineEmits(['close', 'start-drag', 'verify', 'create-inquiry', 'auto-match', 'fix-match'])
</script>

<template><Teleport to="#ui-teleport-host"><div v-if="inquiry" class="backdrop"><section class="dialog" :style="{ transform: `translate(${drag.x}px, ${drag.y}px)` }" role="dialog" aria-modal="true"><header @mousedown="$emit('start-drag', $event)"><strong>{{ title }}</strong><button type="button" @mousedown.stop @click="$emit('close')">×</button></header><div class="content"><template v-if="row === 'summary'">{{ inquiry.summary || '—' }}</template><template v-else-if="row === 'message'">{{ inquiry.source_message_text || '—' }}</template><InquiryStockHints v-else-if="row === 'stock'" :hints="hints" @verify="$emit('verify', $event)" @create-inquiry="$emit('create-inquiry', $event)" @auto-match="$emit('auto-match', $event)" @fix-match="$emit('fix-match', $event)" /></div></section></div></Teleport></template>

<style scoped>
.backdrop{position:fixed;z-index:1200;inset:0;display:grid;place-items:center;padding:20px;background:var(--ui-overlay)}.dialog{width:min(720px,94vw);max-height:80vh;overflow:auto;border:1px solid var(--ui-border);border-radius:var(--ui-radius-lg);background:var(--ui-surface);box-shadow:var(--ui-shadow-popover)}header{display:flex;align-items:center;justify-content:space-between;padding:12px 16px;border-bottom:1px solid var(--ui-border);cursor:move;user-select:none}header strong{color:var(--ui-text-strong)}header button{border:0;background:transparent;color:var(--ui-text-muted);font-size:1.3rem;cursor:pointer}.content{padding:16px;color:var(--ui-text);font-size:.88rem;line-height:1.55;white-space:pre-wrap}
</style>
