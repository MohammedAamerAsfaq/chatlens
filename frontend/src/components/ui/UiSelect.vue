<script setup>
import Choices from 'choices.js'
import 'choices.js/public/assets/styles/choices.min.css'
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = defineProps({
  modelValue: { default: '' },
  options: { type: Array, default: () => [] },
  valueKey: { type: String, default: 'value' },
  labelKey: { type: String, default: 'label' },
  placeholder: { type: String, default: '' },
  disabled: { type: Boolean, default: false },
  searchable: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue', 'search'])
const select = ref(null)
let control

function optionValue(option) { return option[props.valueKey] }
function selectedValue(raw) {
  const match = props.options.find(option => String(optionValue(option)) === raw)
  return match ? optionValue(match) : raw
}
function onChange(event) { emit('update:modelValue', selectedValue(event.target.value)) }
function onSearch(event) { emit('search', event.detail?.value || '') }

function choices() {
  return [
    ...(props.placeholder ? [{ value: '', label: props.placeholder, selected: props.modelValue == null || props.modelValue === '', disabled: true }] : []),
    ...props.options.map(option => ({
      value: String(optionValue(option)),
      label: option[props.labelKey],
      selected: String(optionValue(option)) === String(props.modelValue ?? ''),
      disabled: Boolean(option.disabled),
    })),
  ]
}

async function refreshChoices() {
  if (!control) return
  await control.setChoices(choices(), 'value', 'label', true)
  if (props.modelValue != null && props.modelValue !== '') control.setChoiceByValue(String(props.modelValue))
}

onMounted(async () => {
  await nextTick()
  control = new Choices(select.value, {
    allowHTML: false,
    itemSelectText: '',
    placeholder: Boolean(props.placeholder),
    placeholderValue: props.placeholder,
    searchEnabled: props.searchable,
    searchPlaceholderValue: 'Type to search...',
    shouldSort: false,
  })
  if (props.modelValue != null && props.modelValue !== '') control.setChoiceByValue(String(props.modelValue))
  if (props.disabled) control.disable()
})
watch(() => props.options, refreshChoices, { deep: true })
watch(() => props.modelValue, value => {
  if (!control || value == null || value === '') return
  control.setChoiceByValue(String(value))
})
watch(() => props.disabled, value => value ? control?.disable() : control?.enable())
onBeforeUnmount(() => {
  control?.destroy()
})
</script>

<template>
  <select ref="select" class="ui-control ui-select" :value="modelValue ?? ''" :disabled="disabled" @change="onChange" @search="onSearch">
    <option v-if="placeholder" disabled value="">{{ placeholder }}</option>
    <option v-for="option in options" :key="optionValue(option)" :value="optionValue(option)">{{ option[labelKey] }}</option>
  </select>
</template>
