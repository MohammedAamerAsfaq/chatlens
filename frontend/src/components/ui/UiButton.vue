<script setup>
defineProps({ variant: { type: String, default: 'default' }, size: { type: String, default: 'medium' }, type: { type: String, default: 'button' } })
</script>

<template><button :type="type" class="ui-button" :class="[`ui-button--${variant}`,`ui-button--${size}`]"><slot /></button></template>
