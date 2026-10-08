<script setup>
defineProps({ name: { type: String, required: true } })
</script>

<template>
  <svg viewBox="0 0 24 24" aria-hidden="true">
    <template v-if="name === 'conversations'">
      <path d="M5 17.5 3 21l4.5-1.5A9 9 0 1 0 5 17.5Z"/><path d="M8 10h8M8 14h5"/>
    </template>
    <template v-else-if="name === 'trading'">
      <path d="M4 19V9m5 10V5m5 14v-7m5 7V3"/>
    </template>
    <template v-else-if="name === 'automation'">
      <path d="M12 3v3m0 12v3M3 12h3m12 0h3M5.6 5.6l2.1 2.1m8.6 8.6 2.1 2.1m0-12.8-2.1 2.1m-8.6 8.6-2.1 2.1"/><circle cx="12" cy="12" r="4"/>
    </template>
    <template v-else-if="name === 'clientpulse'">
      <circle cx="9" cy="8" r="3"/><path d="M3.5 19a5.5 5.5 0 0 1 11 0M16 8h5m-2.5-2.5v5"/>
    </template>
    <template v-else-if="name === 'campaigns'">
      <path d="m4 13 12-5v8L4 11v2Zm12-3 3-2v8l-3-2M6 13l1.5 6H11l-1-5"/>
    </template>
    <template v-else-if="name === 'reports'">
      <path d="M4 20V10h4v10H4Zm6 0V4h4v16h-4Zm6 0v-7h4v7h-4Z"/>
    </template>
    <template v-else-if="name === 'directory'">
      <path d="M4 5h16v14H4V5Zm4 4h8M8 13h8M8 17h5"/>
    </template>
    <template v-else-if="name === 'settings'">
      <circle cx="12" cy="12" r="3"/><path d="M19 14.5 21 16l-2 3-2.4-1a8 8 0 0 1-2.1 1.2L14 22h-4l-.5-2.8A8 8 0 0 1 7.4 18L5 19l-2-3 2-1.5a8 8 0 0 1 0-5L3 8l2-3 2.4 1a8 8 0 0 1 2.1-1.2L10 2h4l.5 2.8A8 8 0 0 1 16.6 6L19 5l2 3-2 1.5a8 8 0 0 1 0 5Z"/>
    </template>
    <template v-else>
      <path d="M4 19V9m5 10V5m5 14v-7m5 7V3"/>
    </template>
  </svg>
</template>

<style scoped>
svg{width:20px;height:20px;fill:none;stroke:currentColor;stroke-width:1.7;stroke-linecap:round;stroke-linejoin:round}
</style>
