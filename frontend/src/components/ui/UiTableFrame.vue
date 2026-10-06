<script setup>
defineProps({ compact: { type: Boolean, default: false }, gridKey: { type: String, default: 'table' } })
</script>

<template><div class="ui-table-frame"><table v-ui-data-table="gridKey" class="ui-table" :class="{'ui-table--compact':compact}"><slot /></table></div></template>
