<script setup>
defineProps({ label: { type: String, required: true }, value: { type: [String, Number], required: true }, hint: { type: String, default: '' }, tone: { type: String, default: 'neutral' } })
</script>

<template><article class="ui-metric" :class="`ui-metric--${tone}`"><span>{{ label }}</span><strong>{{ value }}</strong><small v-if="hint">{{ hint }}</small></article></template>
