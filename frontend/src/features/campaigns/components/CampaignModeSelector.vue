<script setup>
defineProps({
  modelValue: { type: String, required: true },
  formattedDescription: { type: String, required: true },
  directDescription: { type: String, required: true },
})

defineEmits(['update:modelValue'])
</script>

<template>
  <div class="campaign-mode-selector" role="group" aria-label="Campaign message type">
    <button
      type="button"
      :class="{ active: modelValue === 'formatted' }"
      :aria-pressed="modelValue === 'formatted'"
      @click="$emit('update:modelValue', 'formatted')"
    >
      <strong>Preformatted Products</strong>
      <span>{{ formattedDescription }}</span>
    </button>
    <button
      type="button"
      :class="{ active: modelValue === 'direct' }"
      :aria-pressed="modelValue === 'direct'"
      @click="$emit('update:modelValue', 'direct')"
    >
      <strong>Direct Message</strong>
      <span>{{ directDescription }}</span>
    </button>
  </div>
</template>

<style scoped>
.campaign-mode-selector{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin:16px 0}.campaign-mode-selector button{min-height:76px;padding:14px;text-align:left;border:1px solid var(--ui-border);border-radius:var(--ui-radius-sm);background:var(--ui-surface-raised);color:var(--ui-text);cursor:pointer}.campaign-mode-selector button:hover{border-color:var(--ui-border-strong)}.campaign-mode-selector button.active{border-color:var(--ui-primary);background:var(--ui-primary-soft);box-shadow:inset 0 0 0 1px var(--ui-primary)}.campaign-mode-selector strong,.campaign-mode-selector span{display:block}.campaign-mode-selector span{margin-top:4px;color:var(--ui-text-muted);font-size:.78rem;line-height:1.4}@media(max-width:800px){.campaign-mode-selector{grid-template-columns:1fr}}
</style>
