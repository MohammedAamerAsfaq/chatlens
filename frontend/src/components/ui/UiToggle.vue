<script setup>
defineProps({
  modelValue: { type: Boolean, default: false },
  label: { type: String, default: '' },
  description: { type: String, default: '' },
  disabled: { type: Boolean, default: false },
})
defineEmits(['update:modelValue'])
</script>

<template>
  <label class="ui-toggle" :class="{ 'is-disabled': disabled }">
    <button type="button" role="switch" :aria-checked="modelValue" :disabled="disabled" @click="$emit('update:modelValue', !modelValue)"><span /></button>
    <span v-if="label || description" class="ui-toggle__copy"><strong v-if="label">{{ label }}</strong><small v-if="description">{{ description }}</small></span>
  </label>
</template>
