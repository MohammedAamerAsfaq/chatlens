<script setup>
defineProps({ tone: { type: String, default: 'neutral' }, dot: { type: Boolean, default: false } })
</script>

<template><span class="ui-badge" :class="`ui-badge--${tone}`"><i v-if="dot"></i><slot /></span></template>
