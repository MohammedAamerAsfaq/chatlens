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
  <label class="ui-checkbox" :class="{ 'is-disabled': disabled }">
    <input type="checkbox" :checked="modelValue" :disabled="disabled" @change="$emit('update:modelValue', $event.target.checked)" />
    <span class="ui-checkbox__box" aria-hidden="true">✓</span>
    <span v-if="label || description" class="ui-checkbox__copy"><strong v-if="label">{{ label }}</strong><small v-if="description">{{ description }}</small></span>
  </label>
</template>
