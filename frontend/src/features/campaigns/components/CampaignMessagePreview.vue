<script setup>
defineProps({
  title: { type: String, default: 'Message Preview' },
  description: { type: String, default: '' },
  message: { type: String, default: '' },
  note: { type: String, default: '' },
})
</script>

<template>
  <section class="campaign-preview">
    <header>
      <h2>{{ title }}</h2>
      <p v-if="description">{{ description }}</p>
    </header>
    <pre>{{ message }}</pre>
    <p v-if="note" class="campaign-preview-note">{{ note }}</p>
  </section>
</template>

<style scoped>
.campaign-preview header h2,.campaign-preview header p{margin:0}.campaign-preview header p{margin-top:4px;color:var(--ui-text-muted)}.campaign-preview pre{min-height:150px;margin:16px 0 0;padding:16px;overflow:auto;white-space:pre-wrap;border:1px solid var(--ui-border);border-radius:var(--ui-radius-lg);background:var(--ui-chat-canvas);color:var(--ui-text);font:inherit;line-height:1.55}.campaign-preview-note{margin:12px 0 0;padding:12px;border-radius:var(--ui-radius-sm);background:var(--ui-info-soft);color:var(--ui-text);font-size:.82rem}
</style>
