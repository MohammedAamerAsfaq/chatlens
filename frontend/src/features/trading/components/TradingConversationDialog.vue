<script setup>
import MessagePanel from '@/components/MessagePanel.vue'
defineProps({ open: { type: Boolean, default: false }, title: { type: String, default: '' }, inquiry: { type: Object, default: null }, loading: { type: Boolean, default: false }, error: { type: String, default: '' }, draft: { type: String, default: '' } })
defineEmits(['close'])
</script>

<template><Teleport to="body"><div v-if="open" class="backdrop" @click.self="$emit('close')"><section class="dialog" role="dialog" aria-modal="true" :aria-label="`${title} conversation`"><header><div><strong>{{ title }}</strong><span>{{ inquiry?.contact_name || inquiry?.contact_phone || 'Conversation' }}</span></div><button type="button" @click="$emit('close')">×</button></header><div v-if="loading" class="state">Loading conversation...</div><div v-else-if="error" class="state error">{{ error }}</div><MessagePanel v-else class="panel" :initial-draft="draft" :composer-rows="5" /></section></div></Teleport></template>

<style scoped>
.backdrop{position:fixed;z-index:1200;inset:0;display:grid;place-items:center;padding:20px;background:var(--ui-overlay)}.dialog{display:flex;width:min(1000px,96vw);height:min(780px,92vh);flex-direction:column;overflow:hidden;border:1px solid var(--ui-border);border-radius:var(--ui-radius-lg);background:var(--ui-surface);box-shadow:var(--ui-shadow-popover)}header{display:flex;align-items:center;justify-content:space-between;padding:12px 16px;border-bottom:1px solid var(--ui-border)}header strong,header span{display:block}header span{margin-top:2px;color:var(--ui-text-muted);font-size:.75rem}header button{border:0;background:transparent;color:var(--ui-text-muted);font-size:1.3rem;cursor:pointer}.state{display:grid;flex:1;place-items:center;color:var(--ui-text-muted)}.state.error{color:var(--ui-danger)}.panel{min-height:0;flex:1}
</style>
