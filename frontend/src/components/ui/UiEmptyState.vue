<script setup>
defineProps({ title: { type: String, required: true }, description: { type: String, default: '' }, busy: { type: Boolean, default: false } })
</script>

<template><div class="ui-empty"><span v-if="busy" class="ui-spinner"></span><strong>{{title}}</strong><p v-if="description">{{description}}</p><slot /></div></template>
