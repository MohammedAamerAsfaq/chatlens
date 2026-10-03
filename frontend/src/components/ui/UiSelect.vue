<script setup>
defineProps({
  modelValue: { default: '' },
  options: { type: Array, default: () => [] },
  valueKey: { type: String, default: 'value' },
  labelKey: { type: String, default: 'label' },
  placeholder: { type: String, default: '' },
  disabled: { type: Boolean, default: false },
})
defineEmits(['update:modelValue'])
</script>

<template>
  <div class="ui-select-wrap">
    <select class="ui-control ui-select" :value="modelValue" :disabled="disabled" @change="$emit('update:modelValue', $event.target.value)">
      <option v-if="placeholder" disabled value="">{{ placeholder }}</option>
      <slot><option v-for="option in options" :key="option[valueKey]" :value="option[valueKey]">{{ option[labelKey] }}</option></slot>
    </select>
  </div>
</template>
