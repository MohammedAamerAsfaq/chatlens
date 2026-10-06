<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { clientPulseApi } from '@/api'
import { useAuthStore } from '@/stores/auth.js'
import ClientPulseFollowUpComposer from '@/components/ClientPulseFollowUpComposer.vue'
import ClientConversationHistory from '@/features/clientpulse/components/ClientConversationHistory.vue'
import ClientTagManager from '@/features/clientpulse/components/ClientTagManager.vue'
import UiBadge from '@/components/ui/UiBadge.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiCard from '@/components/ui/UiCard.vue'
import UiCheckbox from '@/components/ui/UiCheckbox.vue'
import UiEmptyState from '@/components/ui/UiEmptyState.vue'
import UiFormField from '@/components/ui/UiFormField.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiNotice from '@/components/ui/UiNotice.vue'
import UiPageHeader from '@/components/ui/UiPageHeader.vue'
import UiSelect from '@/components/ui/UiSelect.vue'
import { channelOptions, consentChannelOptions, consentPurposeOptions, consentStatusOptions, contactTypeOptions, identityTypeOptions, lifecycleOptions, ownerOption, priorityOptions } from '@/features/clientpulse/clientProfileOptions.js'
const route = useRoute()
const auth = useAuthStore()
const id = Number(route.params.id)
const client = ref(null), notes = ref([]), timeline = ref([]), consents = ref([]), tags = ref([]), owners = ref([])
const loading = ref(true), busy = ref(''), error = ref(''), success = ref(''), noteBody = ref('')
// Kept available for a later rollout without exposing outbound follow-up in the profile UI.
const showWhatsappFollowUp = false
const canEdit = computed(() => auth.hasPermission('clientpulse.clients.update'))
const canNotes = computed(() => auth.hasPermission('clientpulse.notes.manage'))
const canConsent = computed(() => auth.hasPermission('clientpulse.consent.manage'))
const form = reactive({
  display_name: '', legal_name: '', contact_type: 'person', lifecycle_stage: 'lead',
  priority: 'normal', source: 'manual', owner_id: '', preferred_channel: '',
  preferred_language: '', timezone: 'Asia/Dubai', company_name: '', job_title: '',
  website: '', address_line1: '', address_line2: '', city: '', state_region: '',
  postal_code: '', country: '', notes: '', do_not_contact: false,
  do_not_contact_reason: '', tag_ids: [],
})
const identity = reactive({ identity_type: 'phone', value: '', label: '' })
const consent = reactive({ channel: 'whatsapp', purpose: 'follow_up', status: 'unknown', source: 'manual' })
const ownerOptions = computed(() => [ownerOption('', 'Unassigned'), ...owners.value.map(owner => ownerOption(owner.id, owner.username))])
function apiMessage(exc, fallback) {
  const data = exc.response?.data
  return data?.detail || (data ? JSON.stringify(data) : fallback)
}
function syncForm() {
  const value = client.value
  Object.assign(form, {
    display_name: value.display_name || '', legal_name: value.legal_name || '', contact_type: value.contact_type,
    lifecycle_stage: value.lifecycle_stage, priority: value.priority, source: value.source, owner_id: value.owner?.id || '',
    preferred_channel: value.preferred_channel || '', preferred_language: value.preferred_language || '',
    timezone: value.timezone || 'Asia/Dubai', company_name: value.company_name || '',
    job_title: value.job_title || '', website: value.website || '',
    address_line1: value.address_line1 || '', address_line2: value.address_line2 || '',
    city: value.city || '', state_region: value.state_region || '',
    postal_code: value.postal_code || '', country: value.country || '',
    notes: value.notes || '', do_not_contact: value.do_not_contact,
    do_not_contact_reason: value.do_not_contact_reason || '', tag_ids: value.tags.map(tag => tag.id),
  })
}
async function load() {
  loading.value = true; error.value = ''
  try {
    const responses = await Promise.all([clientPulseApi.client(id), clientPulseApi.notes(id), clientPulseApi.timeline(id), clientPulseApi.consents(id), clientPulseApi.tags(), clientPulseApi.options()])
    client.value = responses[0].data; notes.value = responses[1].data; timeline.value = responses[2].data
    consents.value = responses[3].data; tags.value = responses[4].data; owners.value = responses[5].data.owners
    syncForm()
  } catch (exc) { error.value = apiMessage(exc, 'Unable to load client.') }
  finally { loading.value = false }
}
async function save() {
  busy.value = 'save'; error.value = ''; success.value = ''
  try {
    client.value = (await clientPulseApi.updateClient(id, { ...form, owner_id: form.owner_id || null })).data
    syncForm(); success.value = 'Client profile updated.'; timeline.value = (await clientPulseApi.timeline(id)).data
  } catch (exc) { error.value = apiMessage(exc, 'Unable to update client.') }
  finally { busy.value = '' }
}
async function addIdentity() {
  busy.value = 'identity'
  try { await clientPulseApi.addIdentity(id, { ...identity }); Object.assign(identity, { identity_type: 'phone', value: '', label: '' }); await load() }
  catch (exc) { error.value = apiMessage(exc, 'Unable to add identity.') }
  finally { busy.value = '' }
}
async function removeIdentity(item) {
  if (!confirm(`Remove ${item.value}?`)) return
  await clientPulseApi.deleteIdentity(id, item.id); await load()
}
async function addNote() {
  busy.value = 'note'
  try { await clientPulseApi.addNote(id, { body: noteBody.value }); noteBody.value = ''; notes.value = (await clientPulseApi.notes(id)).data; timeline.value = (await clientPulseApi.timeline(id)).data }
  catch (exc) { error.value = apiMessage(exc, 'Unable to add note.') }
  finally { busy.value = '' }
}
async function saveConsent() {
  busy.value = 'consent'
  try { consents.value = (await clientPulseApi.saveConsent(id, { ...consent })).data; timeline.value = (await clientPulseApi.timeline(id)).data }
  catch (exc) { error.value = apiMessage(exc, 'Unable to save consent.') }
  finally { busy.value = '' }
}
async function loadTags() { tags.value = (await clientPulseApi.tags()).data }
async function setActive(active) {
  const action = active ? 'reactivate' : 'deactivate'
  if (!confirm(`${action[0].toUpperCase() + action.slice(1)} this ClientPulse contact?`)) return
  busy.value = action; error.value = ''; success.value = ''
  try { await (active ? clientPulseApi.activateClient(id) : clientPulseApi.deactivateClient(id)); await load(); success.value = `Client ${active ? 'reactivated' : 'deactivated'}.` }
  catch (exc) { error.value = apiMessage(exc, `Unable to ${action} client.`) }
  finally { busy.value = '' }
}
async function followUpQueued() { timeline.value = (await clientPulseApi.timeline(id)).data }
onMounted(load)
</script>
<template>
  <main class="ui-page client-profile-page"><div class="ui-page__inner ui-page__inner--wide client-profile">
    <RouterLink class="client-profile__back" to="/clientpulse">&larr; Customer directory</RouterLink>
    <UiEmptyState v-if="loading" title="Loading profile" description="Retrieving relationship and activity data." busy />
    <template v-else-if="client">
      <UiPageHeader eyebrow="Client profile" :title="client.display_name || client.legal_name" :description="`#${client.id} / ${client.lifecycle_stage.replaceAll('_', ' ')} / ${client.owner?.user?.username || 'Unassigned'} / ${client.status === 'active' ? 'Active' : 'Inactive'}`">
        <template #actions>
          <RouterLink v-if="auth.hasPermission('clientpulse.reminders.manage')" class="ui-button ui-button--primary ui-button--medium" :to="`/clientpulse-reminders?profile_id=${id}&create=1`">Create reminder</RouterLink>
          <UiButton v-if="auth.hasPermission('clientpulse.clients.archive') && client.status === 'active'" variant="danger" :disabled="busy === 'deactivate'" @click="setActive(false)">Deactivate</UiButton>
          <UiButton v-else-if="auth.hasPermission('clientpulse.clients.archive')" variant="primary" :disabled="busy === 'reactivate'" @click="setActive(true)">Reactivate</UiButton>
        </template>
      </UiPageHeader>
      <UiNotice v-if="error" tone="danger">{{ error }}</UiNotice>
      <UiNotice v-if="success" tone="success">{{ success }}</UiNotice>
      <ClientPulseFollowUpComposer v-if="showWhatsappFollowUp && auth.hasPermission('clientpulse.messages.send_manual')" :client="client" @queued="followUpQueued" />

      <div class="client-profile__grid">
        <UiCard title="Relationship profile" subtitle="Core ownership, lifecycle, preferences, and contact policy.">
          <form class="client-profile__form" @submit.prevent="save">
            <UiFormField label="Name"><UiInput v-model="form.display_name" :disabled="!canEdit" /></UiFormField>
            <UiFormField label="Legal name"><UiInput v-model="form.legal_name" :disabled="!canEdit" /></UiFormField>
            <UiFormField label="Type"><UiSelect v-model="form.contact_type" :options="contactTypeOptions" :disabled="!canEdit" /></UiFormField>
            <UiFormField label="Company name"><UiInput v-model="form.company_name" :disabled="!canEdit" /></UiFormField>
            <UiFormField label="Job title"><UiInput v-model="form.job_title" :disabled="!canEdit" /></UiFormField>
            <UiFormField label="Website"><UiInput v-model="form.website" type="url" :disabled="!canEdit" /></UiFormField>
            <UiFormField label="Lifecycle"><UiSelect v-model="form.lifecycle_stage" :options="lifecycleOptions" :disabled="!canEdit" /></UiFormField>
            <UiFormField label="Priority"><UiSelect v-model="form.priority" :options="priorityOptions" :disabled="!canEdit" /></UiFormField>
            <UiFormField label="Owner"><UiSelect v-model="form.owner_id" :options="ownerOptions" :disabled="!canEdit" /></UiFormField>
            <UiFormField label="Preferred channel"><UiSelect v-model="form.preferred_channel" :options="channelOptions" :disabled="!canEdit" /></UiFormField>
            <UiFormField label="Language"><UiInput v-model="form.preferred_language" :disabled="!canEdit" /></UiFormField>
            <UiFormField label="Timezone"><UiInput v-model="form.timezone" :disabled="!canEdit" /></UiFormField>
            <div class="client-profile__wide"><UiCheckbox v-model="form.do_not_contact" label="Do not contact" description="Block manual and automated communication for this client." :disabled="!canEdit" /></div>
            <UiFormField v-if="form.do_not_contact" class="client-profile__wide" label="Do-not-contact reason"><UiInput v-model="form.do_not_contact_reason" multiline :rows="3" :disabled="!canEdit" /></UiFormField>
            <div v-if="canEdit" class="client-profile__wide client-profile__actions"><UiButton type="submit" variant="primary" :disabled="busy === 'save'">{{ busy === 'save' ? 'Saving...' : 'Save profile' }}</UiButton></div>
          </form>
        </UiCard>

        <UiCard title="Address Info" subtitle="Postal and physical location details for this customer.">
          <form class="client-profile__form" @submit.prevent="save">
            <UiFormField class="client-profile__wide" label="Address line 1"><UiInput v-model="form.address_line1" :disabled="!canEdit" /></UiFormField>
            <UiFormField class="client-profile__wide" label="Address line 2"><UiInput v-model="form.address_line2" :disabled="!canEdit" /></UiFormField>
            <UiFormField label="City"><UiInput v-model="form.city" :disabled="!canEdit" /></UiFormField>
            <UiFormField label="State / region"><UiInput v-model="form.state_region" :disabled="!canEdit" /></UiFormField>
            <UiFormField label="Postal code"><UiInput v-model="form.postal_code" :disabled="!canEdit" /></UiFormField>
            <UiFormField label="Country"><UiInput v-model="form.country" :disabled="!canEdit" /></UiFormField>
            <div v-if="canEdit" class="client-profile__wide client-profile__actions"><UiButton type="submit" variant="primary" :disabled="busy === 'save'">{{ busy === 'save' ? 'Saving...' : 'Save address' }}</UiButton></div>
          </form>
        </UiCard>

        <UiCard title="Notes" subtitle="Internal relationship context and operator observations.">
          <form class="client-profile__stack" @submit.prevent="save"><UiFormField label="Customer overview"><UiInput v-model="form.notes" multiline :rows="4" placeholder="Persistent background, preferences, and context" :disabled="!canEdit" /></UiFormField><div v-if="canEdit" class="client-profile__actions"><UiButton type="submit" variant="primary" :disabled="busy === 'save'">Save overview</UiButton></div></form>
          <form v-if="canNotes" class="client-profile__stack client-profile__subform" @submit.prevent="addNote"><UiFormField label="New timeline note"><UiInput v-model="noteBody" multiline :rows="4" placeholder="Add a dated relationship note..." required /></UiFormField><div class="client-profile__actions"><UiButton type="submit" variant="primary" :disabled="busy === 'note'">Add note</UiButton></div></form>
          <div class="client-profile__list"><article v-for="note in notes" :key="note.id" class="client-profile__item client-profile__item--block"><p>{{ note.body }}</p><small>{{ note.created_by?.username }} / {{ new Date(note.created_at).toLocaleString() }}</small></article><UiEmptyState v-if="!notes.length" title="No notes yet" description="Relationship notes will appear here." /></div>
        </UiCard>

        <ClientTagManager v-model="form.tag_ids" :tags="tags" :can-edit="canEdit" @tags-changed="loadTags" />

        <UiCard title="Consent" subtitle="Channel and purpose-specific communication consent.">
          <form v-if="canConsent" class="client-profile__form" @submit.prevent="saveConsent">
            <UiFormField label="Channel"><UiSelect v-model="consent.channel" :options="consentChannelOptions" /></UiFormField>
            <UiFormField label="Purpose"><UiSelect v-model="consent.purpose" :options="consentPurposeOptions" /></UiFormField>
            <UiFormField label="Status"><UiSelect v-model="consent.status" :options="consentStatusOptions" /></UiFormField>
            <div class="client-profile__wide client-profile__actions"><UiButton type="submit" variant="primary" :disabled="busy === 'consent'">Save consent</UiButton></div>
          </form>
          <div class="client-profile__list"><div v-for="item in consents" :key="item.id" class="client-profile__item"><strong>{{ item.channel }} / {{ item.purpose }}</strong><UiBadge :tone="item.status === 'granted' ? 'success' : item.status === 'denied' || item.status === 'revoked' ? 'danger' : 'warning'">{{ item.status }}</UiBadge></div><UiEmptyState v-if="!consents.length" title="No consent records" description="Consent decisions will appear here." /></div>
        </UiCard>

        <UiCard title="Contact identities" subtitle="Direct identities and linked WhatsApp contacts.">
          <div class="client-profile__list">
            <div v-for="item in client.identities" :key="item.id" class="client-profile__item"><div><strong>{{ item.value }}</strong><small>{{ item.identity_type }} {{ item.label }}</small></div><UiButton v-if="canEdit" variant="danger" size="small" @click="removeIdentity(item)">Remove</UiButton></div>
            <div v-for="item in client.whatsapp_contacts" :key="`wa-${item.id}`" class="client-profile__item"><div><strong>{{ item.display_name || item.phone_number }}</strong><small>Linked WhatsApp / {{ item.account_name }}</small></div><UiBadge tone="success">Linked</UiBadge></div>
            <UiEmptyState v-if="!client.identities.length && !client.whatsapp_contacts.length" title="No identities linked" description="Add a direct identity below." />
          </div>
          <form v-if="canEdit" class="client-profile__form client-profile__subform" @submit.prevent="addIdentity">
            <UiFormField label="Type"><UiSelect v-model="identity.identity_type" :options="identityTypeOptions" /></UiFormField>
            <UiFormField label="Value"><UiInput v-model="identity.value" required /></UiFormField>
            <UiFormField label="Label"><UiInput v-model="identity.label" /></UiFormField>
            <div class="client-profile__wide client-profile__actions"><UiButton type="submit" variant="primary" :disabled="busy === 'identity'">Add identity</UiButton></div>
          </form>
        </UiCard>
      </div>

      <UiCard title="Activity timeline" subtitle="Relationship, consent, reminder, and outbound activity.">
        <div class="client-profile__timeline"><article v-for="item in timeline" :key="item.id" class="client-profile__timeline-item"><div><strong>{{ item.title }}</strong><p v-if="item.summary">{{ item.summary }}</p><small>{{ new Date(item.occurred_at).toLocaleString() }} / {{ item.created_by?.username || 'system' }}</small></div><UiBadge v-if="item.outbound" :tone="item.outbound.status === 'sent' ? 'success' : item.outbound.status === 'failed' ? 'danger' : 'info'">{{ item.outbound.status.replaceAll('_', ' ') }}</UiBadge></article><UiEmptyState v-if="!timeline.length" title="No activity recorded" description="Client activity will appear here." /></div>
      </UiCard>
      <ClientConversationHistory :profile-id="id" />
    </template>
  </div></main>
</template>

<style scoped>
.client-profile { display: grid; gap: 16px; }
.client-profile-page { box-sizing: border-box; height: 100%; min-height: 0; overflow-x: hidden; overflow-y: auto; overscroll-behavior: contain; }
:global(.theme-inspinia.layout-position-scrollable) .client-profile-page { height: auto; min-height: 0; overflow: visible; }
.client-profile__back { width: fit-content; color: var(--ui-primary); font-size: .78rem; font-weight: 750; text-decoration: none; }
.client-profile__grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; align-items: start; }
.client-profile__grid :deep(.tag-manager__list) { grid-template-columns: 1fr; }
.client-profile__form { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; }
.client-profile__subform { margin-top: 18px; padding-top: 18px; border-top: 1px solid var(--ui-border); }
.client-profile__wide { grid-column: 1 / -1; }
.client-profile__actions { display: flex; justify-content: flex-end; gap: 8px; }
.client-profile__list,.client-profile__timeline,.client-profile__stack { display: grid; gap: 10px; }
.client-profile__item,.client-profile__timeline-item { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 11px 12px; border: 1px solid var(--ui-border); border-radius: var(--ui-radius-sm); background: var(--ui-surface-muted); }
.client-profile__item div,.client-profile__timeline-item div { min-width: 0; }
.client-profile__item strong,.client-profile__timeline-item strong { color: var(--ui-text-strong); font-size: .82rem; }
.client-profile__item small,.client-profile__timeline-item small { display: block; margin-top: 3px; color: var(--ui-text-subtle); font-size: .7rem; }
.client-profile__item p,.client-profile__timeline-item p { margin: 5px 0 0; color: var(--ui-text-muted); font-size: .78rem; line-height: 1.45; }
.client-profile__item--block { display: block; }
@media (max-width: 1050px) { .client-profile__grid { grid-template-columns: 1fr; } }
@media (max-width: 760px) { .client-profile__form { grid-template-columns: 1fr; } }
</style>
