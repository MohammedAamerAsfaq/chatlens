<script setup>
import { ref } from 'vue'

const props = defineProps({ log: { type: Object, required: true } })
const emit = defineEmits(['open-message'])
const copied = ref(false)

function metadataRows() {
  const metadata = props.log.metadata || {}
  const labels = {
    provider_message_id: 'Message ID', chat_id: 'Chat JID', sender_jid: 'Sender JID',
    push_name: 'Push name', message_type: 'Message type', message_text: 'Text',
    direction: 'Direction', status: 'Status', phone_number: 'Phone', group_name: 'Group',
    total: 'Total messages', created: 'Created', skipped: 'Skipped', errors: 'Ingest errors',
    embedded: 'Embedded', embed_errors: 'Embedding errors', error: 'Error',
  }
  return Object.entries(metadata).filter(([key]) => key !== 'raw_payload').map(([key, value]) => ({
    key,
    label: labels[key] || key.replaceAll('_', ' '),
    value: typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value),
    isError: ['error', 'errors', 'embed_errors'].includes(key) && Boolean(value),
  }))
}

async function copyPayload() {
  if (!props.log.metadata?.raw_payload) return
  await navigator.clipboard.writeText(JSON.stringify(props.log.metadata.raw_payload, null, 2))
  copied.value = true
  setTimeout(() => { copied.value = false }, 1500)
}
</script>

<template>
  <div class="activity-detail">
    <header><div><strong>{{ log.account_name }}</strong><span>{{ new Date(log.created_at).toLocaleString() }}</span></div><button v-if="log.event_type === 'message_ingest' && log.metadata?.provider_message_id" class="ui-button ui-button--small" @click.stop="emit('open-message', log)">Open Message Logs</button></header>
    <dl v-if="metadataRows().length"><template v-for="row in metadataRows()" :key="row.key"><dt>{{ row.label }}</dt><dd :class="{ error: row.isError }">{{ row.value }}</dd></template></dl>
    <p v-else class="empty">No metadata recorded.</p>
    <div v-if="log.message" class="message"><strong>Message</strong><p>{{ log.message }}</p></div>
    <section v-if="log.metadata?.raw_payload" class="payload"><div><strong>Raw payload</strong><button class="ui-button ui-button--small" @click.stop="copyPayload">{{ copied ? 'Copied' : 'Copy' }}</button></div><pre>{{ JSON.stringify(log.metadata.raw_payload, null, 2) }}</pre></section>
  </div>
</template>

<style scoped>
.activity-detail { display:grid; gap:15px; }
header,.payload>div { display:flex; align-items:center; justify-content:space-between; gap:12px; }
header div { display:flex; flex-direction:column; gap:3px; }
header strong,.message strong,.payload strong { color:var(--ui-text-strong); }
header span,.empty { color:var(--ui-text-subtle); font-size:.74rem; }
dl { display:grid; grid-template-columns:minmax(120px, .3fr) 1fr; gap:1px 16px; margin:0; }
dt,dd { margin:0; padding:5px 0; border-bottom:1px solid var(--ui-border); font-size:.74rem; }
dt { color:var(--ui-text-muted); font-weight:750; text-transform:capitalize; }
dd { color:var(--ui-text); font-family:ui-monospace,Consolas,monospace; overflow-wrap:anywhere; white-space:pre-wrap; }
dd.error { color:var(--ui-danger); font-weight:750; }
.message { padding:10px 12px; border:1px solid var(--ui-border); border-radius:var(--ui-radius-sm); background:var(--ui-surface); }
.message p { margin:5px 0 0; color:var(--ui-text); font-size:.78rem; }
.payload { display:grid; gap:8px; }
pre { max-height:320px; margin:0; overflow:auto; padding:12px; border-radius:var(--ui-radius-sm); background:var(--ui-code-bg, #111827); color:var(--ui-code-text, #86efac); font-size:.72rem; line-height:1.5; }
@media(max-width:700px) { dl { grid-template-columns:1fr; } dt { border-bottom:0; padding-bottom:0; } }
</style>
