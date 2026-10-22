<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { realEstateApi } from '@/api'
import UiButton from '@/components/ui/UiButton.vue'
import UiDatePicker from '@/components/ui/UiDatePicker.vue'
import UiFormField from '@/components/ui/UiFormField.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiModal from '@/components/ui/UiModal.vue'
import UiNotice from '@/components/ui/UiNotice.vue'
import UiSelect from '@/components/ui/UiSelect.vue'
import { apiError } from '../apiErrors'

const props = defineProps({ open: Boolean, property: { type: Object, default: null } })
const emit = defineEmits(['close', 'changed', 'manage-parties'])
const rows = ref([]), parties = ref([]), busy = ref(false), error = ref('')
const blank = () => ({ party: '', relationship_type: 'current_owner', ownership_percentage: '', started_on: '', ended_on: '', notes: '' })
const form = reactive(blank())
const roles = [
  ['current_owner', 'Current owner'], ['previous_owner', 'Previous owner'], ['landlord', 'Landlord'],
  ['tenant', 'Tenant'], ['authorized_representative', 'Authorized representative'],
  ['developer', 'Developer'], ['broker', 'Broker'], ['other', 'Other'],
].map(([value, label]) => ({ value, label }))
const partyOptions = computed(() => parties.value.map(row => ({ value: row.id, label: `${row.display_name}${row.phone ? ` - ${row.phone}` : ''}` })))

async function load() {
  if (!props.property?.id) return
  busy.value = true; error.value = ''
  try {
    const [links, partyRows] = await Promise.all([
      realEstateApi.propertyPartyAssociations({ property: props.property.id, page_size: 100 }),
      realEstateApi.parties({ page_size: 100 }),
    ])
    rows.value = links.data.results; parties.value = partyRows.data.results
  } catch (exc) { error.value = apiError(exc, 'Unable to load property parties.') }
  finally { busy.value = false }
}
async function add() {
  busy.value = true; error.value = ''
  const payload = { ...form, property: props.property.id, ownership_percentage: form.ownership_percentage || null, started_on: form.started_on || null, ended_on: form.ended_on || null }
  try { await realEstateApi.createPropertyPartyAssociation(payload); Object.assign(form, blank()); await load(); emit('changed') }
  catch (exc) { error.value = apiError(exc, 'Unable to associate the party.') }
  finally { busy.value = false }
}
async function remove(row) {
  busy.value = true; error.value = ''
  try { await realEstateApi.deletePropertyPartyAssociation(row.id); await load(); emit('changed') }
  catch (exc) { error.value = apiError(exc, 'Unable to remove the association.') }
  finally { busy.value = false }
}
watch(() => [props.open, props.property?.id], ([open]) => { if (open) { Object.assign(form, blank()); load() } })
</script>

<template><UiModal :open="open" :title="`Parties - ${property?.title || 'Property'}`" subtitle="Associate owners and other parties without changing the physical property record." size="large" tall @close="emit('close')">
  <UiNotice v-if="error" tone="danger">{{ error }}</UiNotice>
  <div class="links"><article v-for="row in rows" :key="row.id"><div><strong>{{ row.party_name }}</strong><span>{{ row.relationship_label }}<template v-if="row.ownership_percentage"> - {{ row.ownership_percentage }}%</template></span><small>{{ row.party_phone || row.notes || '' }}</small></div><UiButton size="small" variant="danger" :disabled="busy" @click="remove(row)">Remove</UiButton></article><p v-if="!rows.length && !busy" class="empty">No parties are associated with this property.</p></div>
  <form class="link-form" @submit.prevent="add"><div class="form-heading"><h3>Add association</h3><UiButton size="small" @click="emit('manage-parties')">Manage party master</UiButton></div><div class="form-grid">
    <UiFormField label="Party" class="wide"><UiSelect v-model="form.party" :options="partyOptions" searchable placeholder="Select a party" /></UiFormField><UiFormField label="Role"><UiSelect v-model="form.relationship_type" :options="roles" /></UiFormField><UiFormField label="Ownership %"><UiInput v-model="form.ownership_percentage" compact type="number" min="0" max="100" step="0.01" /></UiFormField><UiFormField label="Start date"><UiDatePicker v-model="form.started_on" /></UiFormField><UiFormField label="End date"><UiDatePicker v-model="form.ended_on" /></UiFormField><UiFormField label="Notes" class="wide"><UiInput v-model="form.notes" multiline :rows="2" /></UiFormField>
  </div><div class="submit"><UiButton variant="primary" type="submit" :disabled="busy || !form.party">Associate party</UiButton></div></form>
  <template #footer><UiButton @click="emit('close')">Close</UiButton></template>
</UiModal></template>

<style scoped>
.links{display:grid;gap:8px}.links article{display:flex;align-items:center;justify-content:space-between;gap:12px;border:1px solid var(--ui-border);padding:12px}.links article div{display:flex;flex-direction:column;gap:2px}.links span,.links small,.empty{color:var(--ui-text-subtle)}.link-form{border-top:1px solid var(--ui-border);margin-top:18px;padding-top:16px}.form-heading,.submit{display:flex;align-items:center;justify-content:space-between}.form-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.wide{grid-column:1/-1}.submit{justify-content:flex-end;margin-top:14px}@media(max-width:700px){.form-grid{grid-template-columns:1fr}.wide{grid-column:auto}}
</style>
