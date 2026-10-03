<script setup>
defineProps({ open: { type: Boolean, default: false } })
</script>

<template>
  <svg class="navigation-chevron" :class="{ open }" viewBox="0 0 20 20" aria-hidden="true">
    <path d="m6 8 4 4 4-4" />
  </svg>
</template>

<style scoped>
.navigation-chevron{width:16px;height:16px;fill:none;stroke:currentColor;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round;transition:transform .18s ease}
.navigation-chevron.open{transform:rotate(180deg)}
</style>
