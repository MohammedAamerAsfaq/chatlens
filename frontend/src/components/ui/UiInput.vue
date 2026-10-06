<script setup>
defineOptions({ inheritAttrs: false })
defineProps({
  modelValue: { default: '' },
  type: { type: String, default: 'text' },
  placeholder: { type: String, default: '' },
  disabled: { type: Boolean, default: false },
  multiline: { type: Boolean, default: false },
  rows: { type: Number, default: 4 },
})
defineEmits(['update:modelValue'])
</script>

<template>
  <div class="ui-input-wrap" :class="{ 'has-prefix': $slots.prefix }">
    <span v-if="$slots.prefix" class="ui-input__prefix"><slot name="prefix" /></span>
    <textarea
      v-if="multiline"
      v-bind="$attrs"
      class="ui-control ui-input ui-input--textarea"
      :value="modelValue"
      :placeholder="placeholder"
      :disabled="disabled"
      :rows="rows"
      @input="$emit('update:modelValue', $event.target.value)"
    />
    <input
      v-else
      v-bind="$attrs"
      class="ui-control ui-input"
      :type="type"
      :value="modelValue"
      :placeholder="placeholder"
      :disabled="disabled"
      @input="$emit('update:modelValue', $event.target.value)"
    />
  </div>
</template>
