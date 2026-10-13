<script setup>
import { reactive, watch } from 'vue'
import UiBadge from '@/components/ui/UiBadge.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiFormField from '@/components/ui/UiFormField.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiModal from '@/components/ui/UiModal.vue'
import UiRadioGroup from '@/components/ui/UiRadioGroup.vue'

const props = defineProps({ open: Boolean, records: { type: Array, default: () => [] }, busy: Boolean })
const emit = defineEmits(['close', 'save', 'deactivate'])
const form = reactive(emptyForm())
const categories = ['residential', 'commercial', 'land', 'other'].map(value => ({
  value, label: value.charAt(0).toUpperCase() + value.slice(1),
}))

watch(() => props.open, open => { if (open) Object.assign(form, emptyForm()) })
watch(() => props.records, records => {
  if (!form.id) return
  const current = records.find(record => record.id === form.id)
  if (current) Object.assign(form, current)
}, { deep: true })

function emptyForm() {
  return { id: null, name: '', code: '', category: 'residential', aliases_text: '', description: '', sort_order: 0, is_active: true }
}

function edit(record) { Object.assign(form, record, { aliases_text: (record.aliases || []).join(', ') }) }
function reset() { Object.assign(form, emptyForm()) }
function save() {
  const values = { ...form, aliases: form.aliases_text.split(',').map(value => value.trim()).filter(Boolean) }
  delete values.aliases_text
  emit('save', values)
}
</script>

<template>
  <UiModal :open="open" title="Property type master" subtitle="Maintain company-owned types used by inventory, imports, and AI extraction." size="xlarge" tall @close="emit('close')">
    <div class="type-layout">
      <section class="type-list">
        <div v-for="record in records" :key="record.id" :class="['type-row', { inactive: !record.is_active }]">
          <div><strong>{{ record.name }}</strong><small>{{ record.code }} · {{ record.category }}</small></div>
          <UiBadge :tone="record.is_active ? 'success' : 'neutral'">{{ record.is_active ? 'Active' : 'Inactive' }}</UiBadge>
          <UiButton size="small" @click="edit(record)">Edit</UiButton>
        </div>
      </section>
      <form id="property-type-form" class="type-form" @submit.prevent="save">
        <h3>{{ form.id ? 'Edit type' : 'Add type' }}</h3>
        <UiFormField label="Name"><UiInput v-model="form.name" required /></UiFormField>
        <UiFormField label="Code" hint="Lowercase letters, numbers, and underscores."><UiInput v-model="form.code" required :disabled="Boolean(form.id)" /></UiFormField>
        <UiRadioGroup v-model="form.category" label="Category" :options="categories" />
        <UiFormField label="Aliases" hint="Import and AI labels, separated by commas."><UiInput v-model="form.aliases_text" /></UiFormField>
        <UiFormField label="Sort order"><UiInput v-model="form.sort_order" compact type="number" min="0" /></UiFormField>
        <UiFormField label="Description"><UiInput v-model="form.description" multiline :rows="3" /></UiFormField>
        <div class="form-actions"><UiButton v-if="form.id" @click="reset">Add new</UiButton><UiButton variant="primary" type="submit" :disabled="busy">Save type</UiButton></div>
        <UiButton v-if="form.id && form.is_active" variant="danger" :disabled="busy" @click="emit('deactivate', form)">Deactivate type</UiButton>
        <UiButton v-if="form.id && !form.is_active" :disabled="busy" @click="emit('save', { ...form, is_active: true })">Reactivate type</UiButton>
      </form>
    </div>
  </UiModal>
</template>

<style scoped>
.type-layout{display:grid;grid-template-columns:minmax(0,1.4fr) minmax(300px,1fr);gap:20px}.type-list{display:grid;align-content:start;gap:8px}.type-row{display:grid;grid-template-columns:1fr auto auto;gap:10px;align-items:center;padding:12px;border:1px solid var(--ui-border);border-radius:10px}.type-row.inactive{opacity:.65}.type-row small{display:block;color:var(--ui-text-subtle);margin-top:3px}.type-form{display:grid;align-content:start;gap:14px;padding:18px;border:1px solid var(--ui-border);border-radius:12px}.type-form h3{margin:0}.form-actions{display:flex;justify-content:flex-end;gap:8px}@media(max-width:800px){.type-layout{grid-template-columns:1fr}}
</style>
