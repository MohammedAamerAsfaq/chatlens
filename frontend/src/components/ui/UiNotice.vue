<script setup>
defineProps({ tone: { type: String, default: 'info' } })
</script>

<template><div class="ui-notice" :class="`ui-notice--${tone}`" role="status"><slot /></div></template>
