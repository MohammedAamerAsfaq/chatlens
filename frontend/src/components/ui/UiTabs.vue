<script setup>
import UiBadge from './UiBadge.vue'

defineProps({ modelValue: { type: [String, Number], required: true }, tabs: { type: Array, required: true } })
defineEmits(['update:modelValue'])
</script>

<template>
  <div class="ui-tabs" role="tablist"><button v-for="tab in tabs" :key="tab.value" type="button" role="tab" :aria-selected="modelValue === tab.value" :class="{ active: modelValue === tab.value }" @click="$emit('update:modelValue', tab.value)">{{ tab.label }}<UiBadge v-if="tab.count !== undefined">{{ tab.count }}</UiBadge></button></div>
</template>
