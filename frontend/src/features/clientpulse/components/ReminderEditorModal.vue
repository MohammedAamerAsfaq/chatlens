<script setup>
import { computed } from 'vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiDatePicker from '@/components/ui/UiDatePicker.vue'
import UiFormField from '@/components/ui/UiFormField.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiModal from '@/components/ui/UiModal.vue'
import UiSelect from '@/components/ui/UiSelect.vue'

const props = defineProps({
  open: { type: Boolean, default: false },
  editing: { type: Boolean, default: false },
  busy: { type: Boolean, default: false },
  form: { type: Object, required: true },
  clients: { type: Array, default: () => [] },
  owners: { type: Array, default: () => [] },
  linkedFrom: { type: Object, default: null },
  phrases: { type: Array, default: () => [] },
  error: { type: String, default: '' },
})
defineEmits(['close', 'submit'])

const clientOptions = computed(() => props.clients.map(client => ({
  value: client.id,
  label: client.display_name || client.legal_name,
})))
const ownerOptions = computed(() => [
  { value: '', label: 'Unassigned' },
  ...props.owners.map(owner => ({ value: owner.id, label: owner.username })),
])
// Choosing a preset action copies its text into the title, which stays editable.
// The dropdown shows the action whose text the title currently matches.
const phraseOptions = computed(() => [
  { value: '', label: props.phrases.length ? 'Custom title' : 'No preset actions' },
  ...props.phrases.map(phrase => ({ value: phrase.id, label: phrase.text })),
])
const action = computed({
  get: () => props.phrases.find(phrase => phrase.text === props.form.title?.trim())?.id ?? '',
  set: id => {
    const phrase = props.phrases.find(item => String(item.id) === String(id))
    props.form.title = phrase ? phrase.text : ''
  },
})
const priorities = ['low', 'normal', 'high', 'critical'].map(value => ({ value, label: value[0].toUpperCase() + value.slice(1) }))
const recurrences = ['none', 'daily', 'weekly', 'monthly', 'custom'].map(value => ({ value, label: value[0].toUpperCase() + value.slice(1) }))
</script>

<template>
  <UiModal
    :open="open"
    :title="editing ? 'Edit reminder' : linkedFrom ? 'Create linked follow-up' : 'Create reminder'"
    :subtitle="linkedFrom ? 'Continue the selected reminder thread for the same client.' : 'Schedule an internal follow-up. No customer message will be sent.'"
    size="full"
    tall
    :closeable="!busy"
    @close="$emit('close')"
  >
    <form id="reminder-editor-form" class="reminder-form" @submit.prevent="$emit('submit')">
      <p v-if="error" class="editor-error wide" role="alert">{{ error }}</p>
      <div v-if="linkedFrom" class="thread-context wide">
        <span>Following completed reminder</span>
        <strong>{{ linkedFrom.title }}</strong>
      </div>
      <UiFormField label="Client">
        <UiSelect v-model="form.profile_id" :options="clientOptions" placeholder="Select client" searchable required :disabled="Boolean(linkedFrom)" />
      </UiFormField>
      <UiFormField label="Assigned to">
        <UiSelect v-model="form.assigned_to_id" :options="ownerOptions" />
      </UiFormField>
      <UiFormField label="Due date and time">
        <UiDatePicker v-model="form.due_at" mode="datetime" placeholder="Choose due date and time" />
      </UiFormField>
      <UiFormField label="Action" hint="Preset actions are managed in ClientPulse settings.">
        <UiSelect v-model="action" :options="phraseOptions" searchable :disabled="!phrases.length" />
      </UiFormField>
      <UiFormField class="span-2" label="Title">
        <UiInput v-model="form.title" placeholder="What needs follow-up?" required />
      </UiFormField>
      <UiFormField class="wide" label="Description" hint="Optional internal context for the assigned user.">
        <UiInput v-model="form.description" multiline :rows="4" placeholder="Add useful context..." />
      </UiFormField>
      <UiFormField label="Priority">
        <UiSelect v-model="form.priority" :options="priorities" />
      </UiFormField>
      <UiFormField label="Repeat">
        <UiSelect v-model="form.recurrence_type" :options="recurrences" />
      </UiFormField>
      <UiFormField v-if="form.recurrence_type === 'custom'" label="Repeat every (days)">
        <UiInput v-model="form.interval_days" type="number" min="1" />
      </UiFormField>
    </form>
    <template #footer>
      <UiButton :disabled="busy" @click="$emit('close')">Cancel</UiButton>
      <UiButton form="reminder-editor-form" type="submit" variant="primary" :disabled="busy">
        {{ busy ? 'Saving...' : editing ? 'Save changes' : linkedFrom ? 'Create linked follow-up' : 'Create reminder' }}
      </UiButton>
    </template>
  </UiModal>
</template>

<style scoped>
.reminder-form{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}.wide{grid-column:1/-1}.editor-error{margin:0;padding:9px 12px;border-radius:var(--ui-radius-sm);background:var(--ui-danger-soft);color:var(--ui-danger);font-size:.8rem;font-weight:600}.span-2{grid-column:span 2}.thread-context{display:flex;flex-direction:column;gap:4px;padding:12px 14px;border-left:4px solid var(--ui-primary);border-radius:var(--ui-radius-sm);background:var(--ui-primary-soft)}.thread-context span{color:var(--ui-text-muted);font-size:.7rem;font-weight:700;text-transform:uppercase}.thread-context strong{color:var(--ui-text-strong)}@media(max-width:760px){.reminder-form{grid-template-columns:1fr}.wide,.span-2{grid-column:auto}}
</style>
