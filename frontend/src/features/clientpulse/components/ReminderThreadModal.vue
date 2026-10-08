<script setup>
import UiButton from '@/components/ui/UiButton.vue'
import UiModal from '@/components/ui/UiModal.vue'

defineProps({
  open: { type: Boolean, default: false },
  loading: { type: Boolean, default: false },
  error: { type: String, default: '' },
  thread: { type: Object, default: null },
})
defineEmits(['close', 'follow-up'])

function dueAt(item) {
  return new Date(item.snoozed_until || item.due_at).toLocaleString()
}
</script>

<template>
  <UiModal
    :open="open"
    title="Reminder thread"
    :subtitle="thread?.profile?.display_name || 'Follow-up history'"
    size="large"
    tall
    @close="$emit('close')"
  >
    <div v-if="loading" class="thread-state">Loading reminder thread...</div>
    <div v-else-if="error" class="thread-state error">{{ error }}</div>
    <div v-else-if="!thread?.results?.length" class="thread-state">No reminder history found.</div>
    <ol v-else class="thread-list">
      <li v-for="(item, index) in thread.results" :key="item.id">
        <span class="thread-node">{{ index + 1 }}</span>
        <article>
          <header><div><strong>{{ item.title }}</strong><small>#{{ item.id }} - {{ item.linked_from ? `Linked from #${item.linked_from.id}` : 'Thread started' }}</small></div><span class="status" :class="`status-${item.status}`">{{ item.status }}</span></header>
          <p v-if="item.description">{{ item.description }}</p>
          <div class="thread-meta"><span>Due {{ dueAt(item) }}</span><span>{{ item.assigned_to?.username || 'Unassigned' }}</span><span>{{ item.priority }} priority</span></div>
          <UiButton v-if="item.status === 'completed'" size="small" variant="outline" @click="$emit('follow-up', item)">Add follow-up</UiButton>
        </article>
      </li>
    </ol>
    <template #footer><UiButton @click="$emit('close')">Close</UiButton></template>
  </UiModal>
</template>

<style scoped>
.thread-state{padding:36px;color:var(--ui-text-muted);text-align:center}.thread-state.error{color:var(--ui-danger)}.thread-list{display:grid;margin:0;padding:0;list-style:none}.thread-list li{position:relative;display:grid;grid-template-columns:34px 1fr;gap:12px;padding-bottom:18px}.thread-list li:not(:last-child)::before{position:absolute;top:30px;bottom:0;left:14px;width:2px;background:var(--ui-border);content:""}.thread-node{z-index:1;display:grid;width:30px;height:30px;place-items:center;border-radius:50%;background:var(--ui-primary);color:var(--ui-on-primary);font-size:.75rem;font-weight:800}.thread-list article{padding:13px;border:1px solid var(--ui-border);border-radius:var(--ui-radius-md);background:var(--ui-surface)}.thread-list header{display:flex;align-items:flex-start;justify-content:space-between;gap:12px}.thread-list header div{display:flex;min-width:0;flex-direction:column;gap:3px}.thread-list small,.thread-meta{color:var(--ui-text-muted);font-size:.7rem}.thread-list p{margin:10px 0;color:var(--ui-text)}.thread-meta{display:flex;gap:10px;flex-wrap:wrap;margin:8px 0}.status{padding:4px 7px;border-radius:999px;background:var(--ui-surface-muted);font-size:.66rem;font-weight:800;text-transform:uppercase}.status-completed{background:var(--ui-success-soft);color:var(--ui-success)}.status-due{background:var(--ui-danger-soft);color:var(--ui-danger)}
</style>
