<script setup>
import { computed, reactive, watch } from 'vue'
import { FontAwesomeIcon } from '@fortawesome/vue-fontawesome'
import { faTrashCan } from '@fortawesome/free-solid-svg-icons'
import UiButton from '@/components/ui/UiButton.vue'
import UiCard from '@/components/ui/UiCard.vue'
import UiCheckbox from '@/components/ui/UiCheckbox.vue'
import UiFormField from '@/components/ui/UiFormField.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiSelect from '@/components/ui/UiSelect.vue'
import UiTagInput from '@/components/ui/UiTagInput.vue'

const props = defineProps({ record: { type: Object, default: null }, busy: Boolean })
const emit = defineEmits(['save'])
const form = reactive(blankForm())
const dataTypes = ['text', 'number', 'boolean', 'select', 'list'].map(value => ({ value, label: title(value) }))
const strategies = [
  { value: 'exact', label: 'Exact' }, { value: 'numeric_distance', label: 'Numeric distance' },
  { value: 'taxonomy', label: 'Taxonomy' }, { value: 'semantic', label: 'Semantic' },
]
const supportsOptions = computed(() => ['number', 'select', 'boolean'].includes(form.data_type))

watch(() => props.record, value => Object.assign(form, value ? editForm(value) : blankForm()), { immediate: true })

function blankForm() {
  return { id: null, label: '', code: '', data_type: 'text', matching_strategy: 'exact', unit_hint: '', allow_multiple: false, sort_order: 0, is_system: false, is_active: true, aliases: [], options: [] }
}
function editForm(record) {
  return { ...record, aliases: [...(record.aliases || [])], options: (record.options || []).map(option => ({ ...option, numeric_value: option.numeric_value ?? '', aliases: [...(option.aliases || [])] })) }
}
function title(value) { return String(value).replaceAll('_', ' ').replace(/\b\w/g, letter => letter.toUpperCase()) }
function addOption() { form.options.push({ code: '', label: '', numeric_value: '', sort_order: form.options.length * 10, is_active: true, aliases: [] }) }
function removeOption(index) { form.options.splice(index, 1) }
function save() {
  const payload = { ...form, aliases: [...form.aliases], options: supportsOptions.value ? form.options.map((option, index) => ({ code: option.code, label: option.label, numeric_value: option.numeric_value === '' ? null : option.numeric_value, sort_order: option.sort_order ?? index * 10, is_active: option.is_active !== false, aliases: [...option.aliases] })) : [] }
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
      <UiFormField label="Attribute aliases" hint="Press Enter or comma after each alternative name. Paste a comma-separated list to add several."><UiTagInput v-model="form.aliases" placeholder="Add an attribute alias" /></UiFormField>
      <section v-if="supportsOptions" class="attribute-options">
        <header><div><strong>Canonical options</strong><small>Each option can have its own aliases.</small></div><UiButton size="small" @click="addOption">Add option</UiButton></header>
        <div v-for="(option, index) in form.options" :key="option.id || index" class="attribute-option" :class="{ 'has-numeric-value': form.data_type === 'number' }">
          <UiInput v-model="option.label" placeholder="Label" required />
          <UiInput v-model="option.code" placeholder="code" required />
          <UiInput v-if="form.data_type === 'number'" v-model="option.numeric_value" compact type="number" placeholder="Value" />
          <UiTagInput v-model="option.aliases" placeholder="Add option aliases" />
          <UiButton class="attribute-option__remove" size="small" variant="danger" title="Remove option" aria-label="Remove option" @click="removeOption(index)"><FontAwesomeIcon :icon="faTrashCan" /></UiButton>
        </div>
      </section>
      <footer class="attribute-editor__actions">
        <UiButton v-if="form.id && !form.is_active" :disabled="busy" @click="reactivate">Reactivate</UiButton>
        <UiButton variant="primary" type="submit" :disabled="busy">{{ busy ? 'Saving...' : 'Save attribute' }}</UiButton>
      </footer>
    </form>
  </UiCard>
</template>

<style scoped>
.attribute-editor{display:grid;gap:14px}.attribute-editor__grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.attribute-options{display:grid;gap:10px;padding:14px;border-radius:var(--ui-radius-md);background:var(--ui-surface-muted)}.attribute-options header{display:flex;align-items:center;justify-content:space-between;gap:12px}.attribute-options small{display:block;margin-top:3px;color:var(--ui-text-subtle)}.attribute-option{display:grid;grid-template-columns:minmax(180px,1fr) minmax(150px,.8fr) minmax(260px,1.4fr) 36px;gap:8px;align-items:center}.attribute-option.has-numeric-value{grid-template-columns:minmax(180px,1fr) minmax(150px,.8fr) 100px minmax(260px,1.4fr) 36px}.attribute-option__remove{width:36px;min-width:36px;height:36px;padding:0}.attribute-editor__actions{display:flex;justify-content:flex-end;gap:8px}@media(max-width:1000px){.attribute-editor__grid{grid-template-columns:1fr 1fr}.attribute-option,.attribute-option.has-numeric-value{grid-template-columns:1fr 1fr}.attribute-option__remove{justify-self:end}}@media(max-width:600px){.attribute-editor__grid,.attribute-option,.attribute-option.has-numeric-value{grid-template-columns:1fr}}
</style>
