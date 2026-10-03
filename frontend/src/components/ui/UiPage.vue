<script setup>
defineProps({ width: { type: String, default: 'standard' } })
</script>

<template>
  <main class="ui-page"><div class="ui-page__inner" :class="`ui-page__inner--${width}`"><slot /></div></main>
</template>
