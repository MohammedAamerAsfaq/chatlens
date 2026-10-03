<script setup>
defineProps({ label: { type: String, required: true }, hint: { type: String, default: '' }, error: { type: String, default: '' } })
</script>

<template><label class="ui-field"><span>{{label}}</span><slot /><small v-if="error" class="ui-field__error">{{error}}</small><small v-else-if="hint">{{hint}}</small></label></template>
