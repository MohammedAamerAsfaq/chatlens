<script setup>
import { computed, reactive, watch } from 'vue'
import UiBadge from '@/components/ui/UiBadge.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiCheckbox from '@/components/ui/UiCheckbox.vue'
import UiFormField from '@/components/ui/UiFormField.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiModal from '@/components/ui/UiModal.vue'
import UiSelect from '@/components/ui/UiSelect.vue'

const props = defineProps({ open: Boolean, records: { type: Array, default: () => [] }, busy: Boolean })
const emit = defineEmits(['close', 'save', 'deactivate'])
const form = reactive(emptyForm())
const dataTypes = ['text', 'number', 'boolean', 'select', 'list'].map(value => ({ value, label: title(value) }))
const strategies = [
  { value: 'exact', label: 'Exact' }, { value: 'numeric_distance', label: 'Numeric distance' },
  { value: 'taxonomy', label: 'Taxonomy' }, { value: 'semantic', label: 'Semantic' },
]
const supportsOptions = computed(() => ['number', 'select', 'boolean'].includes(form.data_type))

watch(() => props.open, open => { if (open) reset() })
watch(() => props.records, records => {
  if (!form.id) return
  const current = records.find(record => record.id === form.id)
  if (current) edit(current)
}, { deep: true })

function emptyForm() {
  return {
    id: null, label: '', code: '', data_type: 'text', matching_strategy: 'exact',
    unit_hint: '', allow_multiple: false, sort_order: 0, is_system: false,
    is_active: true, aliases_text: '', options: [],
  }
}
function title(value) { return String(value).replaceAll('_', ' ').replace(/\b\w/g, letter => letter.toUpperCase()) }
function reset() { Object.assign(form, emptyForm()) }
function edit(record) {
  Object.assign(form, record, {
    aliases_text: (record.aliases || []).join(', '),
    options: (record.options || []).map(option => ({
      ...option, numeric_value: option.numeric_value ?? '',
      aliases_text: (option.aliases || []).join(', '),
    })),
  })
}
function addOption() {
  form.options.push({ code: '', label: '', numeric_value: '', sort_order: form.options.length * 10, is_active: true, aliases_text: '' })
}
function removeOption(index) { form.options.splice(index, 1) }
function reactivate() { form.is_active = true; save() }
function save() {
  const payload = {
    ...form,
    aliases: splitAliases(form.aliases_text),
    options: supportsOptions.value ? form.options.map((option, index) => ({
      code: option.code, label: option.label,
      numeric_value: option.numeric_value === '' ? null : option.numeric_value,
      sort_order: option.sort_order ?? index * 10, is_active: option.is_active !== false,
      aliases: splitAliases(option.aliases_text),
    })) : [],
  }
  delete payload.aliases_text
  emit('save', payload)
}
function splitAliases(value) { return String(value || '').split(',').map(item => item.trim()).filter(Boolean) }
</script>

<template>
  <UiModal :open="open" title="Property attribute master" subtitle="Maintain canonical values and aliases used by extraction and search." size="xlarge" tall @close="emit('close')">
    <div class="attribute-layout">
      <section class="attribute-list">
        <div v-for="record in records" :key="record.id" :class="['attribute-row', { inactive: !record.is_active }]" @click="edit(record)">
          <div><strong>{{ record.label }}</strong><small>{{ record.code }} - {{ title(record.data_type) }} - {{ title(record.matching_strategy) }}</small></div>
          <UiBadge :tone="record.is_system ? 'info' : 'neutral'">{{ record.is_system ? 'System' : 'Custom' }}</UiBadge>
          <UiBadge :tone="record.is_active ? 'success' : 'neutral'">{{ record.is_active ? 'Active' : 'Inactive' }}</UiBadge>
        </div>
      </section>
      <form class="attribute-form" @submit.prevent="save">
        <h3>{{ form.id ? 'Edit attribute' : 'Add attribute' }}</h3>
        <div class="form-grid">
          <UiFormField label="Label"><UiInput v-model="form.label" required /></UiFormField>
          <UiFormField label="Code"><UiInput v-model="form.code" required :disabled="Boolean(form.id)" /></UiFormField>
          <UiFormField label="Data type"><UiSelect v-model="form.data_type" :options="dataTypes" /></UiFormField>
          <UiFormField label="Matching strategy"><UiSelect v-model="form.matching_strategy" :options="strategies" /></UiFormField>
          <UiFormField label="Unit"><UiInput v-model="form.unit_hint" placeholder="AED, sqft, rooms..." /></UiFormField>
          <UiFormField label="Sort order"><UiInput v-model="form.sort_order" compact type="number" min="0" /></UiFormField>
        </div>
        <UiCheckbox v-model="form.allow_multiple" label="Allow multiple values" />
        <UiFormField label="Attribute aliases" hint="Names used to identify this attribute, separated by commas."><UiInput v-model="form.aliases_text" /></UiFormField>
        <section v-if="supportsOptions" class="options-panel">
          <div class="options-heading"><div><strong>Canonical options</strong><small>Each option can have its own aliases.</small></div><UiButton size="small" @click="addOption">Add option</UiButton></div>
          <div v-for="(option, index) in form.options" :key="option.id || index" class="option-row">
            <UiInput v-model="option.label" placeholder="Label" required />
            <UiInput v-model="option.code" placeholder="code" required />
            <UiInput v-if="form.data_type === 'number'" v-model="option.numeric_value" compact type="number" placeholder="Value" />
            <UiInput v-model="option.aliases_text" placeholder="Aliases, comma separated" />
            <UiButton size="small" variant="danger" title="Remove option" @click="removeOption(index)">Remove</UiButton>
          </div>
        </section>
        <div class="form-actions"><UiButton v-if="form.id" @click="reset">Add new</UiButton><UiButton variant="primary" type="submit" :disabled="busy">Save attribute</UiButton></div>
        <UiButton v-if="form.id && form.is_active && !form.is_system" variant="danger" :disabled="busy" @click="emit('deactivate', form)">Deactivate attribute</UiButton>
        <UiButton v-if="form.id && !form.is_active" :disabled="busy" @click="reactivate">Reactivate attribute</UiButton>
      </form>
    </div>
  </UiModal>
</template>

<style scoped>
.attribute-layout{display:grid;grid-template-columns:minmax(280px,.8fr) minmax(0,1.7fr);gap:20px}.attribute-list{display:grid;align-content:start;gap:8px}.attribute-row{display:grid;grid-template-columns:1fr auto auto;gap:8px;align-items:center;padding:12px;border:1px solid var(--ui-border);border-radius:10px;cursor:pointer}.attribute-row:hover{border-color:var(--ui-accent)}.attribute-row.inactive{opacity:.6}.attribute-row small,.options-heading small{display:block;color:var(--ui-text-subtle);margin-top:3px}.attribute-form{display:grid;align-content:start;gap:14px;padding:18px;border:1px solid var(--ui-border);border-radius:12px}.attribute-form h3{margin:0}.form-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}.options-panel{display:grid;gap:10px;padding:14px;background:var(--ui-surface-muted);border-radius:10px}.options-heading{display:flex;align-items:center;justify-content:space-between}.option-row{display:grid;grid-template-columns:1fr .8fr 90px 1.5fr auto;gap:8px;align-items:center}.form-actions{display:flex;justify-content:flex-end;gap:8px}@media(max-width:900px){.attribute-layout,.form-grid{grid-template-columns:1fr}.option-row{grid-template-columns:1fr 1fr}.option-row>*:nth-child(n+3){grid-column:auto}}
</style>
