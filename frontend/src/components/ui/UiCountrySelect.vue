<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { integrationsApi } from '@/api'
import UiSelect from './UiSelect.vue'

// Country picker backed by the country master: shows 10 countries, then fetches matches as you type.
// v-model is the country object ({ id, iso2, name }) or null.
const props = defineProps({
  modelValue: { type: Object, default: null },
  disabled: { type: Boolean, default: false },
  placeholder: { type: String, default: 'Select a country' },
})
const emit = defineEmits(['update:modelValue'])

const results = ref([])
const error = ref('')
let timer, request = 0

const options = computed(() => {
  const list = props.modelValue && !results.value.some(item => item.id === props.modelValue.id)
    ? [props.modelValue, ...results.value] : results.value
  return [
    ...(props.modelValue ? [{ value: '', label: 'No country' }] : []),
    ...list.map(item => ({ value: item.id, label: item.name, country: item })),
  ]
})

async function load(search = '') {
  const current = ++request
  try {
    const { data } = await integrationsApi.countries(search)
    if (current === request) { results.value = data; error.value = '' }
  } catch {
    if (current === request) error.value = 'Unable to load countries.'
  }
}
function search(value) {
  clearTimeout(timer)
  timer = setTimeout(() => load(value.trim()), 250)
}
function select(value) {
  if (value === '' || value == null) return emit('update:modelValue', null)
  const option = options.value.find(item => String(item.value) === String(value))
  emit('update:modelValue', option ? { id: option.country.id, iso2: option.country.iso2, name: option.country.name } : null)
}

onMounted(() => load())
onBeforeUnmount(() => clearTimeout(timer))
</script>

<template>
  <div class="ui-country-select">
    <UiSelect
      :model-value="modelValue ? modelValue.id : ''" :options="options" :placeholder="modelValue ? '' : placeholder"
      :disabled="disabled" searchable remote @search="search" @update:model-value="select"
    />
    <small v-if="error" class="ui-country-select__error" role="alert">{{ error }}</small>
  </div>
</template>

<style scoped>
.ui-country-select__error{display:block;margin-top:4px;color:var(--ui-danger);font-size:.72rem}
</style>
