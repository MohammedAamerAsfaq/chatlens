<script setup>
import { reactive, ref, watch } from 'vue'
import { realEstateApi } from '@/api'
import UiButton from '@/components/ui/UiButton.vue'
import UiFormField from '@/components/ui/UiFormField.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiModal from '@/components/ui/UiModal.vue'
import UiNotice from '@/components/ui/UiNotice.vue'
import UiRadioGroup from '@/components/ui/UiRadioGroup.vue'
import { apiError } from '../apiErrors'

const props = defineProps({ open: Boolean })
const emit = defineEmits(['close', 'changed'])
const rows = ref([]), busy = ref(false), error = ref('')
const blank = () => ({
  id: null, party_kind: 'person', first_name: '', middle_name: '', last_name: '',
  organization_name: '', phone: '', alternate_phone: '', email: '', address_line_1: '',
  address_line_2: '', city: '', state_region: '', postal_code: '', country: '', notes: '', is_active: true,
})
const form = reactive(blank())
const kinds = [{ value: 'person', label: 'Person' }, { value: 'organization', label: 'Organization' }]

function reset() { Object.assign(form, blank()) }
function edit(row) { Object.assign(form, blank(), row) }
async function load() {
  busy.value = true; error.value = ''
  try { rows.value = (await realEstateApi.parties({ include_inactive: true, page_size: 100 })).data.results }
  catch (exc) { error.value = apiError(exc, 'Unable to load parties.') }
  finally { busy.value = false }
}
async function save() {
  busy.value = true; error.value = ''
  const payload = { ...form }; delete payload.id; delete payload.display_name; delete payload.created_at; delete payload.updated_at
  try {
    if (form.id) await realEstateApi.updateParty(form.id, payload)
    else await realEstateApi.createParty(payload)
    reset(); await load(); emit('changed')
  } catch (exc) { error.value = apiError(exc, 'Unable to save the party.') }
  finally { busy.value = false }
}
async function deactivate(row) {
  busy.value = true; error.value = ''
  try { await realEstateApi.deactivateParty(row.id); reset(); await load(); emit('changed') }
  catch (exc) { error.value = apiError(exc, 'Unable to deactivate the party.') }
  finally { busy.value = false }
}
watch(() => props.open, value => { if (value) { reset(); load() } })
</script>

<template><UiModal :open="open" title="Parties" subtitle="Maintain people and organizations that can be associated with properties." size="xlarge" tall @close="emit('close')">
  <UiNotice v-if="error" tone="danger">{{ error }}</UiNotice>
  <div class="party-layout">
    <section class="party-list"><div class="section-title"><h3>Party master</h3><UiButton size="small" @click="reset">Add new</UiButton></div>
      <button v-for="row in rows" :key="row.id" type="button" :class="['party-row', { inactive: !row.is_active }]" @click="edit(row)">
        <strong>{{ row.display_name }}</strong><span>{{ row.phone || row.email || row.party_kind }}</span>
      </button><p v-if="!rows.length && !busy" class="empty">No parties have been created.</p>
    </section>
    <form class="party-form" @submit.prevent="save"><h3>{{ form.id ? 'Edit party' : 'Add party' }}</h3>
      <UiRadioGroup v-model="form.party_kind" label="Party type" :options="kinds" />
      <div class="form-grid">
        <template v-if="form.party_kind === 'person'"><UiFormField label="First name"><UiInput v-model="form.first_name" /></UiFormField><UiFormField label="Middle name"><UiInput v-model="form.middle_name" /></UiFormField><UiFormField label="Last name"><UiInput v-model="form.last_name" /></UiFormField></template>
        <UiFormField v-else label="Organization name" class="wide"><UiInput v-model="form.organization_name" /></UiFormField>
        <UiFormField label="Phone"><UiInput v-model="form.phone" /></UiFormField><UiFormField label="Alternate phone"><UiInput v-model="form.alternate_phone" /></UiFormField><UiFormField label="Email"><UiInput v-model="form.email" type="email" /></UiFormField>
        <UiFormField label="Address line 1" class="wide"><UiInput v-model="form.address_line_1" /></UiFormField><UiFormField label="Address line 2" class="wide"><UiInput v-model="form.address_line_2" /></UiFormField>
        <UiFormField label="City"><UiInput v-model="form.city" /></UiFormField><UiFormField label="State / region"><UiInput v-model="form.state_region" /></UiFormField><UiFormField label="Country"><UiInput v-model="form.country" /></UiFormField><UiFormField label="Postal code"><UiInput v-model="form.postal_code" /></UiFormField>
        <UiFormField label="Notes" class="wide"><UiInput v-model="form.notes" multiline :rows="3" /></UiFormField>
      </div><div class="form-actions"><UiButton v-if="form.id && form.is_active" variant="danger" :disabled="busy" @click="deactivate(form)">Deactivate</UiButton><span></span><UiButton variant="primary" type="submit" :disabled="busy">{{ busy ? 'Saving...' : 'Save party' }}</UiButton></div>
    </form>
  </div>
  <template #footer><UiButton @click="emit('close')">Close</UiButton></template>
</UiModal></template>

<style scoped>
.party-layout{display:grid;grid-template-columns:minmax(240px,.7fr) minmax(0,1.6fr);gap:18px}.party-list,.party-form{border:1px solid var(--ui-border);padding:16px;background:var(--ui-surface)}.section-title,.form-actions{display:flex;align-items:center;justify-content:space-between;gap:10px}.party-row{display:flex;width:100%;flex-direction:column;align-items:flex-start;gap:3px;border:0;border-bottom:1px solid var(--ui-border);background:transparent;padding:12px;text-align:left;cursor:pointer}.party-row:hover{background:var(--ui-surface-muted)}.party-row span,.empty{color:var(--ui-text-subtle)}.party-row.inactive{opacity:.55}.form-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.wide{grid-column:1/-1}.form-actions{margin-top:18px}.form-actions span{flex:1}@media(max-width:800px){.party-layout{grid-template-columns:1fr}.form-grid{grid-template-columns:1fr}.wide{grid-column:auto}}
</style>
