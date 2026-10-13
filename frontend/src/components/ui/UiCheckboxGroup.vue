<script setup>
const props = defineProps({
  modelValue: { type: Array, default: () => [] },
  label: { type: String, default: '' },
  hint: { type: String, default: '' },
  options: { type: Array, default: () => [] },
  disabled: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue'])

function selected(value) {
  return props.modelValue.some(item => String(item) === String(value))
}

function toggle(value, checked) {
  const next = props.modelValue.filter(item => String(item) !== String(value))
  if (checked) next.push(value)
  emit('update:modelValue', next)
}
</script>

<template>
  <fieldset class="ui-choice-field" :disabled="disabled">
    <legend v-if="label">{{ label }}</legend>
    <div class="ui-choice-list">
      <label v-for="option in options" :key="String(option.value)" class="ui-choice">
        <input
          type="checkbox"
          :checked="selected(option.value)"
          :disabled="option.disabled"
          @change="toggle(option.value, $event.target.checked)"
        />
        <span class="ui-choice__indicator ui-choice__indicator--checkbox" aria-hidden="true"></span>
        <span>{{ option.label }}</span>
      </label>
    </div>
    <small v-if="hint" class="ui-choice-field__hint">{{ hint }}</small>
  </fieldset>
</template>
