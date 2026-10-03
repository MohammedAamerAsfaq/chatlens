<script setup>
defineProps({ page: { type: Number, required: true }, totalPages: { type: Number, required: true }, loading: { type: Boolean, default: false } })
defineEmits(['change'])
</script>

<template>
  <nav class="feed-pager" aria-label="Inquiry feed pagination">
    <button type="button" :disabled="loading || page <= 1" @click="$emit('change', page - 1)">Previous</button><span>Page {{ page }} of {{ totalPages }}</span><button type="button" :disabled="loading || page >= totalPages" @click="$emit('change', page + 1)">Next</button>
  </nav>
</template>

<style scoped>
.feed-pager{display:flex;align-items:center;justify-content:center;gap:10px;padding:8px 12px;border-top:1px solid var(--ui-border);background:var(--ui-surface)}.feed-pager span{color:var(--ui-text-muted);font-size:.75rem}.feed-pager button{padding:5px 10px;border:1px solid var(--ui-border-strong);border-radius:var(--ui-radius-xs);background:var(--ui-surface);color:var(--ui-text);font:600 .75rem var(--ui-font-sans);cursor:pointer}.feed-pager button:disabled{opacity:.45;cursor:not-allowed}
</style>
