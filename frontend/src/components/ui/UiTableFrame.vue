<script setup>
defineProps({ compact: { type: Boolean, default: false } })
</script>

<template><div class="ui-table-frame"><table class="ui-table" :class="{'ui-table--compact':compact}"><slot /></table></div></template>
