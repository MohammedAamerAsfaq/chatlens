<script setup>
defineProps({ title: { type: String, default: '' }, subtitle: { type: String, default: '' } })
</script>

<template>
  <section class="ui-card">
    <header v-if="title || subtitle || $slots.actions" class="ui-card__header">
      <div><h2 v-if="title">{{title}}</h2><p v-if="subtitle">{{subtitle}}</p></div><div v-if="$slots.actions"><slot name="actions" /></div>
    </header>
    <div class="ui-card__body"><slot /></div>
  </section>
</template>
