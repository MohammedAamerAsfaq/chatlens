<script setup>
defineProps({
  eyebrow: { type: String, default: '' },
  title: { type: String, required: true },
  description: { type: String, default: '' },
})
</script>

<template>
  <header class="ui-page-header">
    <div><p v-if="eyebrow" class="ui-eyebrow">{{eyebrow}}</p><h1>{{title}}</h1><p v-if="description" class="ui-page-header__description">{{description}}</p></div>
    <div v-if="$slots.actions" class="ui-page-header__actions"><slot name="actions" /></div>
  </header>
</template>
