<script setup>
defineProps({
  visibleCount: { type: Number, default: 0 },
  totalCount: { type: Number, default: 0 },
  page: { type: Number, default: 1 },
  totalPages: { type: Number, default: 1 },
  busy: { type: Boolean, default: false },
})

defineEmits(['add-view', 'add-all', 'previous', 'next'])
</script>

<template>
  <div class="search-actions">
    <div class="result-summary">
      <span>{{ totalCount }} results</span>
      <button :disabled="busy || !visibleCount" @click="$emit('add-view')">
        Add All Results in View
      </button>
      <button :disabled="busy || !totalCount" @click="$emit('add-all')">
        Add All Results Returned
      </button>
    </div>
    <div class="pager" v-if="totalPages > 1">
      <button :disabled="busy || page <= 1" @click="$emit('previous')">Previous</button>
      <span>Page {{ page }} of {{ totalPages }}</span>
      <button :disabled="busy || page >= totalPages" @click="$emit('next')">Next</button>
    </div>
  </div>
</template>

<style scoped>
.search-actions{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:9px 10px;border-bottom:1px solid var(--ui-border,#dfe7e2);background:var(--ui-bg-soft,#f8fafc);flex-wrap:wrap}.result-summary,.pager{display:flex;align-items:center;gap:8px;flex-wrap:wrap}.result-summary>span,.pager>span{color:var(--ui-text-muted,#64748b);font-size:.78rem}.search-actions button{border:1px solid var(--ui-border,#d7e2dc);border-radius:7px;padding:6px 9px;background:var(--ui-surface,#fff);color:var(--ui-info,#2563eb);font:inherit;font-size:.76rem;font-weight:700;cursor:pointer}.search-actions button:disabled{cursor:not-allowed;opacity:.5}
</style>
