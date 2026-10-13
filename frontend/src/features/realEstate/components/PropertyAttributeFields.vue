<script setup>
import { computed } from 'vue'
import UiFormField from '@/components/ui/UiFormField.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiSelect from '@/components/ui/UiSelect.vue'

const props = defineProps({
  definitions: { type: Array, default: () => [] },
  modelValue: { type: Object, default: () => ({}) },
})
const emit = defineEmits(['update:modelValue'])
const booleanOptions = [{ value: true, label: 'Yes' }, { value: false, label: 'No' }]
const visibleDefinitions = computed(() => props.definitions.filter(definition => {
  if (!definition.is_active) return false
  if (!definition.condition_field) return true
  return String(props.modelValue?.[definition.condition_field] ?? '') === definition.condition_value
}))

function optionsFor(definition) {
  return (definition.options || []).map(value => ({
    value,
    label: String(value).replaceAll('_', ' ').replace(/\b\w/g, letter => letter.toUpperCase()),
  }))
}

function valueFor(definition) {
  const value = props.modelValue?.[definition.code]
  return definition.data_type === 'list' && Array.isArray(value) ? value.join(', ') : (value ?? '')
}

function update(definition, value) {
  const next = { ...(props.modelValue || {}) }
  next[definition.code] = definition.data_type === 'list'
    ? String(value).split(',').map(item => item.trim()).filter(Boolean)
    : value
  emit('update:modelValue', next)
}
</script>

<template>
  <template v-for="definition in visibleDefinitions" :key="definition.code">
    <UiFormField :label="definition.label" :hint="definition.unit_hint || (definition.data_type === 'list' ? 'Separate values with commas.' : '')">
      <UiSelect
        v-if="definition.data_type === 'select'"
        :model-value="valueFor(definition)"
        :options="optionsFor(definition)"
        :required="definition.is_required"
        @update:model-value="update(definition, $event)"
      />
      <UiSelect
        v-else-if="definition.data_type === 'boolean'"
        :model-value="valueFor(definition)"
        :options="booleanOptions"
        @update:model-value="update(definition, $event)"
      />
      <UiInput
        v-else
        :model-value="valueFor(definition)"
        :type="definition.data_type === 'number' ? 'number' : 'text'"
        :step="definition.data_type === 'number' ? 'any' : undefined"
        :required="definition.is_required"
        @update:model-value="update(definition, $event)"
      />
    </UiFormField>
  </template>
</template>
