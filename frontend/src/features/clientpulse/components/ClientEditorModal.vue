<script setup>
import { computed } from 'vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiFormField from '@/components/ui/UiFormField.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiModal from '@/components/ui/UiModal.vue'
import UiSelect from '@/components/ui/UiSelect.vue'

const props = defineProps({
  open: { type: Boolean, default: false },
  busy: { type: Boolean, default: false },
  form: { type: Object, required: true },
  owners: { type: Array, default: () => [] },
  contacts: { type: Array, default: () => [] },
  contactCount: { type: Number, default: 0 },
  contactsLoading: { type: Boolean, default: false },
})
const emit = defineEmits(['close', 'submit', 'search-contacts'])

const ownerOptions = computed(() => [
  { value: '', label: 'Unassigned' },
  ...props.owners.map(owner => ({ value: owner.id, label: owner.username })),
])
const lifecycleOptions = [
  { value: 'lead', label: 'Lead' },
  { value: 'prospect', label: 'Prospect' },
  { value: 'active_customer', label: 'Active customer' },
]
const priorityOptions = ['low', 'normal', 'high', 'critical'].map(value => ({
  value,
  label: value[0].toUpperCase() + value.slice(1),
}))
const creationOptions = [
  { value: 'manual', label: 'Create manually' },
  { value: 'whatsapp', label: 'Use existing WhatsApp contact' },
]
const contactOptions = computed(() => props.contacts.map(contact => ({
  value: contact.id,
  label: [
    contact.display_name || contact.phone_number || `Contact ${contact.id}`,
    contact.phone_number,
    contact.account_name,
    contact.profile_id ? 'Already in ClientPulse' : '',
  ].filter(Boolean).join(' - '),
  disabled: Boolean(contact.profile_id),
})))
function searchContacts(value) { emit('search-contacts', value) }
</script>

<template>
  <UiModal
    :open="open"
    title="Create client"
    subtitle="Add a company-owned relationship record to ClientPulse."
    size="full"
    tall
    :closeable="!busy"
    @close="$emit('close')"
  >
    <form id="client-editor-form" class="client-form" @submit.prevent="$emit('submit')">
      <UiFormField class="wide" label="Create from">
        <UiSelect v-model="form.creation_mode" :options="creationOptions" />
      </UiFormField>
      <UiFormField v-if="form.creation_mode === 'whatsapp'" class="wide" label="WhatsApp contact" :hint="contactsLoading ? 'Searching contacts...' : `${contactCount} contacts found in accounts available to you`">
        <UiSelect v-model="form.whatsapp_contact_id" :options="contactOptions" placeholder="Search by name or phone number" searchable required @search="searchContacts" />
      </UiFormField>
      <UiFormField v-if="form.creation_mode === 'manual'" class="wide" label="Client name">
        <UiInput v-model="form.display_name" placeholder="Person or company name" required autofocus />
      </UiFormField>
      <UiFormField v-if="form.creation_mode === 'manual'" label="Phone number" hint="Optional. Include the country code when known.">
        <UiInput v-model="form.phone" type="tel" placeholder="e.g. 971501234567" />
      </UiFormField>
      <UiFormField v-if="form.creation_mode === 'manual'" label="Owner">
        <UiSelect v-model="form.owner_id" :options="ownerOptions" searchable />
      </UiFormField>
      <UiFormField label="Lifecycle stage">
        <UiSelect v-model="form.lifecycle_stage" :options="lifecycleOptions" />
      </UiFormField>
      <UiFormField v-if="form.creation_mode === 'manual'" label="Priority">
        <UiSelect v-model="form.priority" :options="priorityOptions" />
      </UiFormField>
    </form>
    <template #footer>
      <UiButton :disabled="busy" @click="$emit('close')">Cancel</UiButton>
      <UiButton form="client-editor-form" type="submit" variant="primary" :disabled="busy">
        {{ busy ? 'Creating...' : form.creation_mode === 'whatsapp' ? 'Create from WhatsApp' : 'Create client' }}
      </UiButton>
    </template>
  </UiModal>
</template>

<style scoped>
.client-form{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}.wide{grid-column:1/-1}@media(max-width:700px){.client-form{grid-template-columns:1fr}.wide{grid-column:auto}}
</style>
