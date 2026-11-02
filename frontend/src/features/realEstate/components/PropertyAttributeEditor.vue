<script setup>
import { computed, reactive, watch } from 'vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiCard from '@/components/ui/UiCard.vue'
import UiCheckbox from '@/components/ui/UiCheckbox.vue'
import UiFormField from '@/components/ui/UiFormField.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiSelect from '@/components/ui/UiSelect.vue'

const props = defineProps({ record: { type: Object, default: null }, busy: Boolean })
const emit = defineEmits(['save', 'deactivate'])
const form = reactive(blankForm())
const dataTypes = ['text', 'number', 'boolean', 'select', 'list'].map(value => ({ value, label: title(value) }))
const strategies = [
  { value: 'exact', label: 'Exact' }, { value: 'numeric_distance', label: 'Numeric distance' },
  { value: 'taxonomy', label: 'Taxonomy' }, { value: 'semantic', label: 'Semantic' },
]
const supportsOptions = computed(() => ['number', 'select', 'boolean'].includes(form.data_type))

watch(() => props.record, value => Object.assign(form, value ? editForm(value) : blankForm()), { immediate: true })

function blankForm() {
  return { id: null, label: '', code: '', data_type: 'text', matching_strategy: 'exact', unit_hint: '', allow_multiple: false, sort_order: 0, is_system: false, is_active: true, aliases_text: '', options: [] }
}
function editForm(record) {
  return { ...record, aliases_text: (record.aliases || []).join(', '), options: (record.options || []).map(option => ({ ...option, numeric_value: option.numeric_value ?? '', aliases_text: (option.aliases || []).join(', ') })) }
}
function title(value) { return String(value).replaceAll('_', ' ').replace(/\b\w/g, letter => letter.toUpperCase()) }
function splitAliases(value) { return String(value || '').split(',').map(item => item.trim()).filter(Boolean) }
function addOption() { form.options.push({ code: '', label: '', numeric_value: '', sort_order: form.options.length * 10, is_active: true, aliases_text: '' }) }
function removeOption(index) { form.options.splice(index, 1) }
function save() {
  const payload = { ...form, aliases: splitAliases(form.aliases_text), options: supportsOptions.value ? form.options.map((option, index) => ({ code: option.code, label: option.label, numeric_value: option.numeric_value === '' ? null : option.numeric_value, sort_order: option.sort_order ?? index * 10, is_active: option.is_active !== false, aliases: splitAliases(option.aliases_text) })) : [] }
  delete payload.aliases_text
  emit('save', payload)
}
function reactivate() { form.is_active = true; save() }
</script>

<template>
  <UiCard :title="form.id ? `Edit attribute: ${form.label}` : 'New property attribute'" subtitle="Define the canonical field, its matching behavior, aliases, and permitted values.">
    <form class="attribute-editor" @submit.prevent="save">
      <div class="attribute-editor__grid">
        <UiFormField label="Label"><UiInput v-model="form.label" required /></UiFormField>
        <UiFormField label="Code"><UiInput v-model="form.code" required :disabled="Boolean(form.id)" /></UiFormField>
        <UiFormField label="Data type"><UiSelect v-model="form.data_type" :options="dataTypes" /></UiFormField>
        <UiFormField label="Matching strategy"><UiSelect v-model="form.matching_strategy" :options="strategies" /></UiFormField>
        <UiFormField label="Unit"><UiInput v-model="form.unit_hint" placeholder="AED, sqft, rooms..." /></UiFormField>
        <UiFormField label="Sort order"><UiInput v-model="form.sort_order" compact type="number" min="0" /></UiFormField>
      </div>
      <UiCheckbox v-model="form.allow_multiple" label="Allow multiple values" />
      <UiFormField label="Attribute aliases" hint="Alternative names used to identify this attribute, separated by commas."><UiInput v-model="form.aliases_text" /></UiFormField>
      <section v-if="supportsOptions" class="attribute-options">
        <header><div><strong>Canonical options</strong><small>Each option can have its own aliases.</small></div><UiButton size="small" @click="addOption">Add option</UiButton></header>
        <div v-for="(option, index) in form.options" :key="option.id || index" class="attribute-option">
          <UiInput v-model="option.label" placeholder="Label" required />
          <UiInput v-model="option.code" placeholder="code" required />
          <UiInput v-if="form.data_type === 'number'" v-model="option.numeric_value" compact type="number" placeholder="Value" />
          <UiInput v-model="option.aliases_text" placeholder="Aliases, comma separated" />
          <UiButton size="small" variant="danger" @click="removeOption(index)">Remove</UiButton>
        </div>
      </section>
      <footer class="attribute-editor__actions">
        <UiButton v-if="form.id && form.is_active && !form.is_system" variant="danger" :disabled="busy" @click="emit('deactivate', form)">Deactivate</UiButton>
        <UiButton v-if="form.id && !form.is_active" :disabled="busy" @click="reactivate">Reactivate</UiButton>
        <UiButton variant="primary" type="submit" :disabled="busy">{{ busy ? 'Saving...' : 'Save attribute' }}</UiButton>
      </footer>
    </form>
  </UiCard>
</template>

<style scoped>
.attribute-editor{display:grid;gap:14px}.attribute-editor__grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.attribute-options{display:grid;gap:10px;padding:14px;border-radius:var(--ui-radius-md);background:var(--ui-surface-muted)}.attribute-options header{display:flex;align-items:center;justify-content:space-between;gap:12px}.attribute-options small{display:block;margin-top:3px;color:var(--ui-text-subtle)}.attribute-option{display:grid;grid-template-columns:1fr .8fr 100px 1.4fr auto;gap:8px;align-items:center}.attribute-editor__actions{display:flex;justify-content:flex-end;gap:8px}@media(max-width:900px){.attribute-editor__grid{grid-template-columns:1fr 1fr}.attribute-option{grid-template-columns:1fr 1fr}}@media(max-width:600px){.attribute-editor__grid,.attribute-option{grid-template-columns:1fr}}
</style>
