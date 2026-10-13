<script setup>
import { useId } from 'vue'

const props = defineProps({
  modelValue: { default: '' },
  label: { type: String, default: '' },
  hint: { type: String, default: '' },
  options: { type: Array, default: () => [] },
  disabled: { type: Boolean, default: false },
  required: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue'])
const name = `radio-${useId()}`

function selected(value) {
  return String(props.modelValue ?? '') === String(value ?? '')
}
</script>

<template>
  <fieldset class="ui-choice-field" :disabled="disabled">
    <legend v-if="label">{{ label }}</legend>
    <div class="ui-choice-list" role="radiogroup">
      <label v-for="(option, index) in options" :key="String(option.value)" class="ui-choice">
        <input
          type="radio"
          :name="name"
          :value="option.value"
          :checked="selected(option.value)"
          :required="required && index === 0"
          :disabled="option.disabled"
          @change="emit('update:modelValue', option.value)"
        />
        <span class="ui-choice__indicator" aria-hidden="true"></span>
        <span>{{ option.label }}</span>
      </label>
    </div>
    <small v-if="hint" class="ui-choice-field__hint">{{ hint }}</small>
  </fieldset>
</template>
