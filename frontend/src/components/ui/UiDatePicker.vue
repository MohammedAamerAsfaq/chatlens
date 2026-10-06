<script setup>
import flatpickr from 'flatpickr'
import 'flatpickr/dist/flatpickr.min.css'
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = defineProps({
  modelValue: { type: String, default: '' },
  mode: { type: String, default: 'date' },
  placeholder: { type: String, default: 'Select date' },
  disabled: { type: Boolean, default: false },
  minDate: { type: String, default: '' },
  maxDate: { type: String, default: '' },
})
const emit = defineEmits(['update:modelValue'])
const input = ref(null)
let picker

function modelValueFor(dates, text, instance) {
  if (!dates.length) return ''
  if (props.mode === 'datetime') return instance.formatDate(dates[0], 'Y-m-d\\TH:i')
  if (props.mode === 'range') return dates.map(date => instance.formatDate(date, 'Y-m-d')).join(' to ')
  return text
}

onMounted(() => {
  picker = flatpickr(input.value, {
    altInput: true,
    altFormat: props.mode === 'datetime' ? 'd M Y, h:i K' : 'd M Y',
    appendTo: document.querySelector('#ui-teleport-host') || document.body,
    dateFormat: props.mode === 'datetime' ? 'Y-m-d\\TH:i' : 'Y-m-d',
    defaultDate: props.modelValue || undefined,
    enableTime: props.mode === 'datetime',
    minDate: props.minDate || undefined,
    maxDate: props.maxDate || undefined,
    mode: props.mode === 'range' ? 'range' : 'single',
    onChange: (dates, text, instance) => emit('update:modelValue', modelValueFor(dates, text, instance)),
  })
  picker.altInput?.classList.add('ui-control', 'ui-date-picker__input')
  picker.altInput?.setAttribute('placeholder', props.placeholder)
})

watch(() => props.modelValue, value => picker?.setDate(value || null, false))
watch(() => props.disabled, value => { if (picker?.altInput) picker.altInput.disabled = value })
onBeforeUnmount(() => picker?.destroy())
</script>

<template><div class="ui-date-picker"><input ref="input" type="text" :disabled="disabled" /><span aria-hidden="true">&#128197;</span></div></template>
