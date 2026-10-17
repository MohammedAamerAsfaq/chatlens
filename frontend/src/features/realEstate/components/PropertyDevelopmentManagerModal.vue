<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { integrationsApi, realEstateApi } from '@/api'
import UiBadge from '@/components/ui/UiBadge.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiCheckbox from '@/components/ui/UiCheckbox.vue'
import UiFormField from '@/components/ui/UiFormField.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiModal from '@/components/ui/UiModal.vue'
import UiRadioGroup from '@/components/ui/UiRadioGroup.vue'
import UiSelect from '@/components/ui/UiSelect.vue'

const props = defineProps({ open: Boolean })
const emit = defineEmits(['close', 'changed', 'error'])
const rows = ref([]), localities = ref([]), busy = ref(false)
const form = reactive(emptyForm())
const types = [{ value: 'project', label: 'Project' }, { value: 'building', label: 'Building' }]
const localityOptions = computed(() => [
  { value: null, label: 'Not mapped' },
  ...localities.value.map(row => ({ value: row.id, label: hierarchyLabel(row) })),
])
const parentOptions = computed(() => [
  { value: null, label: 'No parent project' },
  ...rows.value.filter(row => row.is_active && row.development_type === 'project')
    .map(row => ({ value: row.id, label: row.name })),
])

function emptyForm() {
  return {
    id: null, development_type: 'project', name: '', developer_name: '',
    locality: null, parent: null, alternate_names_text: '', is_verified: false, is_active: true,
  }
}
function hierarchyLabel(row) {
  return [row.name, row.city_name, row.administrative_area_name].filter(Boolean).join(', ')
}
function reset() { Object.assign(form, emptyForm()) }
function edit(row) {
  Object.assign(form, row, { alternate_names_text: (row.alternate_names || []).join(', ') })
}
async function load() {
  busy.value = true
  try {
    const [records, places] = await Promise.all([
      realEstateApi.propertyDevelopments({ include_inactive: true, page_size: 100 }),
      integrationsApi.locations({ level: 'locality', country_code: 'AE', page_size: 3000 }),
    ])
    rows.value = records.data.results
    localities.value = places.data.results
  } catch (error) { emit('error', error) }
  finally { busy.value = false }
}
async function save() {
  busy.value = true
  const payload = {
    development_type: form.development_type,
    name: form.name,
    developer_name: form.developer_name,
    locality: form.locality || null,
    parent: form.development_type === 'building' ? (form.parent || null) : null,
    alternate_names: form.alternate_names_text.split(',').map(value => value.trim()).filter(Boolean),
    is_verified: form.is_verified,
    is_active: form.is_active,
  }
  try {
    if (form.id) await realEstateApi.updatePropertyDevelopment(form.id, payload)
    else await realEstateApi.createPropertyDevelopment(payload)
    reset(); await load(); emit('changed')
  } catch (error) { emit('error', error) }
  finally { busy.value = false }
}
async function deactivate() {
  busy.value = true
  try { await realEstateApi.deactivatePropertyDevelopment(form.id); reset(); await load(); emit('changed') }
  catch (error) { emit('error', error) }
  finally { busy.value = false }
}

watch(() => props.open, open => { if (open) { reset(); load() } })
watch(() => form.development_type, value => { if (value !== 'building') form.parent = null })
</script>

<template>
  <UiModal :open="open" title="Projects and buildings" subtitle="Maintain company-owned development names below canonical localities." size="xlarge" tall @close="emit('close')">
    <div class="manager-layout">
      <section class="record-list">
        <button v-for="row in rows" :key="row.id" type="button" :class="['record-row', { inactive: !row.is_active }]" @click="edit(row)">
          <span><strong>{{ row.name }}</strong><small>{{ row.development_type }} · {{ row.locality_name || 'unmapped locality' }}</small></span>
          <UiBadge :tone="row.is_verified ? 'success' : 'neutral'">{{ row.is_verified ? 'Verified' : 'Unverified' }}</UiBadge>
        </button>
        <p v-if="!rows.length && !busy" class="empty-state">No projects or buildings configured.</p>
      </section>
      <form id="development-form" class="record-form" @submit.prevent="save">
        <h3>{{ form.id ? 'Edit record' : 'Add record' }}</h3>
        <UiRadioGroup v-model="form.development_type" label="Type" :options="types" />
        <UiFormField label="Name"><UiInput v-model="form.name" required /></UiFormField>
        <UiFormField label="Developer"><UiInput v-model="form.developer_name" /></UiFormField>
        <UiFormField label="Locality / community"><UiSelect v-model="form.locality" :options="localityOptions" /></UiFormField>
        <UiFormField v-if="form.development_type === 'building'" label="Parent project"><UiSelect v-model="form.parent" :options="parentOptions" /></UiFormField>
        <UiFormField label="Aliases" hint="Separate alternate names with commas."><UiInput v-model="form.alternate_names_text" /></UiFormField>
        <UiCheckbox v-model="form.is_verified" label="Verified master record" />
        <div class="form-actions"><UiButton v-if="form.id" @click="reset">Add new</UiButton><UiButton variant="primary" type="submit" :disabled="busy">Save</UiButton></div>
        <UiButton v-if="form.id && form.is_active" variant="danger" :disabled="busy" @click="deactivate">Deactivate</UiButton>
        <UiButton v-if="form.id && !form.is_active" :disabled="busy" @click="form.is_active = true; save()">Reactivate</UiButton>
      </form>
    </div>
  </UiModal>
</template>

<style scoped>
.manager-layout{display:grid;grid-template-columns:minmax(0,1.35fr) minmax(320px,1fr);gap:20px}.record-list{display:grid;align-content:start;gap:8px;max-height:62vh;overflow:auto}.record-row{display:flex;align-items:center;justify-content:space-between;gap:12px;width:100%;padding:12px;border:1px solid var(--ui-border);border-radius:10px;background:var(--ui-surface);color:var(--ui-text);text-align:left}.record-row.inactive{opacity:.6}.record-row small{display:block;margin-top:3px;color:var(--ui-text-subtle)}.record-form{display:grid;align-content:start;gap:14px;padding:18px;border:1px solid var(--ui-border);border-radius:12px}.record-form h3{margin:0}.form-actions{display:flex;justify-content:flex-end;gap:8px}.empty-state{color:var(--ui-text-muted)}@media(max-width:800px){.manager-layout{grid-template-columns:1fr}}
</style>
