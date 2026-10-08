<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { clientPulseApi } from '@/api'
import UiButton from '@/components/ui/UiButton.vue'
import UiCard from '@/components/ui/UiCard.vue'
import UiDataTable from '@/components/ui/UiDataTable.vue'
import UiDataTableInlineEditor from '@/components/ui/UiDataTableInlineEditor.vue'
import UiSelect from '@/components/ui/UiSelect.vue'
import ClientEditorModal from '@/features/clientpulse/components/ClientEditorModal.vue'
import { useAuthStore } from '@/stores/auth'
import '@/assets/clientpulse.css'

const router = useRouter()
const auth = useAuthStore()
const clients = ref([]), owners = ref([]), tags = ref([])
const loading = ref(false), creating = ref(false), error = ref(''), showCreate = ref(false)
const conversationContacts = ref([]), contactCount = ref(0), contactsLoading = ref(false)
const page = ref(1), pageSize = ref(25), count = ref(0)
const sortKey = ref('updated_at'), sortDirection = ref('desc'), savingCell = ref('')
const filters = reactive({ search: '', lifecycle_stage: '', owner_id: '', priority: '', status: 'active' })
const canEdit = computed(() => auth.hasPermission('clientpulse.clients.update'))
const emptyClientForm = () => ({
  creation_mode: 'manual', whatsapp_contact_id: '', contact_search: '',
  display_name: '', company_name: '', job_title: '', phone: '', email: '', website: '',
  address_line1: '', address_line2: '', city: '', state_region: '', postal_code: '',
  country: '', notes: '', lifecycle_stage: 'lead', priority: 'normal', owner_id: '',
})
const form = reactive(emptyClientForm())
let contactSearchTimer, contactRequest = 0

const lifecycleValues = ['lead', 'prospect', 'active_customer', 'dormant', 'lost', 'blocked']
const lifecycleEditOptions = lifecycleValues.map(value => ({ value, label: title(value) }))
const lifecycleOptions = [{ value: '', label: 'All lifecycle stages' }, ...lifecycleEditOptions]
const priorityOptions = [
  { value: '', label: 'All priorities' },
  ...['low', 'normal', 'high', 'critical'].map(value => ({ value, label: title(value) })),
]
const statusOptions = [
  { value: 'active', label: 'Active clients' }, { value: 'paused', label: 'Inactive clients' },
  { value: 'archived', label: 'Archived (legacy)' }, { value: 'all', label: 'All clients' },
]
const ownerOptions = computed(() => [
  { value: '', label: 'All owners' },
  ...owners.value.map(owner => ({ value: owner.id, label: owner.username })),
])
const ownerEditOptions = computed(() => [
  { value: '', label: 'Unassigned' },
  ...owners.value.map(owner => ({ value: owner.id, label: owner.username })),
])
const tagEditOptions = computed(() => tags.value.map(tag => ({ value: tag.id, label: tag.name })))
const columns = [
  { key: 'display_name', label: 'Client', width: '16rem', sortable: true, exportValue: row => row.display_name || row.legal_name },
  { key: 'communication_accounts', label: 'Communication account', width: '13rem', exportValue: row => row.communication_accounts.map(account => account.name).join(', ') },
  { key: 'lifecycle_stage', label: 'Lifecycle', width: '10rem' },
  { key: 'owner', label: 'Owner', width: '10rem', exportValue: row => row.owner?.user?.username || 'Unassigned' },
  { key: 'priority', label: 'Priority', width: '7rem' },
  { key: 'tags', label: 'Tags', width: '12rem', exportValue: row => row.tags.map(tag => tag.name).join(', ') },
  { key: 'last_contacted_at', label: 'Last contact', width: '11rem', sortable: true, exportValue: row => formatDateTime(row.last_contacted_at) },
  { key: 'last_replied_at', label: 'Last replied', width: '11rem', sortable: true, exportValue: row => formatDateTime(row.last_replied_at) },
  { key: 'next_follow_up_at', label: 'Next follow-up', width: '11rem', sortable: true, exportValue: row => formatDateTime(row.next_follow_up_at) },
]

function title(value) { return value.replaceAll('_', ' ').replace(/\b\w/g, letter => letter.toUpperCase()) }
function message(exc, fallback) { return exc.response?.data?.detail || fallback }
function formatDateTime(value) { return value ? new Date(value).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' }) : '-' }
function resetForm() { Object.assign(form, emptyClientForm()) }
function openCreate() { resetForm(); showCreate.value = true }
function closeCreate() { if (!creating.value) showCreate.value = false }
function searchConversationContacts(value) {
  clearTimeout(contactSearchTimer); form.contact_search = value; form.whatsapp_contact_id = ''
  contactSearchTimer = setTimeout(loadConversationContacts, 300)
}
async function loadConversationContacts() {
  const request = ++contactRequest; contactsLoading.value = true
  try {
    const { data } = await clientPulseApi.conversationContacts({ search: form.contact_search.trim(), page_size: 50 })
    if (request === contactRequest) { conversationContacts.value = data.results; contactCount.value = data.count }
  } catch (exc) { if (request === contactRequest) error.value = message(exc, 'Unable to load WhatsApp contacts.') }
  finally { if (request === contactRequest) contactsLoading.value = false }
}
async function load() {
  loading.value = true; error.value = ''
  try {
    const ordering = `${sortDirection.value === 'desc' ? '-' : ''}${sortKey.value}`
    const { data } = await clientPulseApi.clients({ ...filters, ordering, page: page.value, page_size: pageSize.value })
    clients.value = data.results; count.value = data.count
  } catch (exc) { error.value = message(exc, 'Unable to load clients.') }
  finally { loading.value = false }
}
async function saveInline(client, field, value) {
  const key = `${client.id}:${field}`
  if (!canEdit.value || savingCell.value) return
  savingCell.value = key; error.value = ''
  const payload = field === 'tags' ? { tag_ids: value } : field === 'owner' ? { owner_id: value || null } : { lifecycle_stage: value }
  try {
    const { data } = await clientPulseApi.updateClient(client.id, payload)
    client.lifecycle_stage = data.lifecycle_stage; client.owner = data.owner; client.tags = data.tags
  } catch (exc) { error.value = message(exc, `Unable to update ${field}.`) }
  finally { savingCell.value = '' }
}
async function createClient() {
  creating.value = true; error.value = ''
  if (form.creation_mode === 'whatsapp') {
    if (!form.whatsapp_contact_id) { error.value = 'Select a WhatsApp contact.'; creating.value = false; return }
    try {
      const { data } = await clientPulseApi.convertConversationContact(form.whatsapp_contact_id, { lifecycle_stage: form.lifecycle_stage })
      showCreate.value = false; router.push(`/clientpulse/${data.profile.id}`)
    } catch (exc) { error.value = message(exc, 'Unable to create client from WhatsApp.') }
    finally { creating.value = false }
    return
  }
  const payload = {
    display_name: form.display_name.trim(), lifecycle_stage: form.lifecycle_stage,
    priority: form.priority, owner_id: form.owner_id || null,
    company_name: form.company_name.trim(), job_title: form.job_title.trim(), website: form.website.trim(),
    address_line1: form.address_line1.trim(), address_line2: form.address_line2.trim(), city: form.city.trim(),
    state_region: form.state_region.trim(), postal_code: form.postal_code.trim(), country: form.country.trim(), notes: form.notes.trim(), identities: [],
  }
  if (form.phone.trim()) payload.identities.push({ identity_type: 'phone', value: form.phone.trim(), is_primary: true })
  if (form.email.trim()) payload.identities.push({ identity_type: 'email', value: form.email.trim(), is_primary: !payload.identities.length })
  try {
    const { data } = await clientPulseApi.createClient(payload)
    showCreate.value = false; router.push(`/clientpulse/${data.id}`)
  } catch (exc) { error.value = message(exc, 'Unable to create client.') }
  finally { creating.value = false }
}
function resetAndLoad() { if (page.value !== 1) page.value = 1; else load() }
watch(() => [filters.lifecycle_stage, filters.owner_id, filters.priority, filters.status, filters.search], resetAndLoad)
watch([page, pageSize, sortKey, sortDirection], load)
watch(() => form.creation_mode, mode => { if (showCreate.value && mode === 'whatsapp') loadConversationContacts() })
onMounted(async () => {
  try {
    const [optionsResponse, tagsResponse] = await Promise.all([clientPulseApi.options(), clientPulseApi.tags()])
    owners.value = optionsResponse.data.owners; tags.value = tagsResponse.data
    await load()
  } catch (exc) { error.value = message(exc, 'Unable to initialize ClientPulse.') }
})
</script>

<template>
  <main class="cp-page directory-page"><div class="cp-shell">
    <header class="cp-hero directory-hero">
      <div><p class="cp-eyebrow">Customer intelligence</p><h1 class="cp-title">Customers</h1><p class="cp-muted">Company-owned contacts, relationships, consent, and follow-up context.</p></div>
      <UiButton variant="primary" @click="openCreate">+ New client</UiButton>
    </header>
    <p v-if="error" class="cp-notice error">{{ error }}</p>

    <UiCard title="Client directory" :subtitle="`${count} clients match the current filters`" flush class="directory-panel">
      <UiDataTable
        :columns="columns" :rows="clients" :loading="loading" :total="count"
        :page="page" :page-size="pageSize" :sort-key="sortKey" :sort-direction="sortDirection"
        :search="filters.search" search-placeholder="Search name, phone, or email..."
        persist-key="clientpulse-directory" export-filename="clientpulse-customers.csv"
        empty-title="No clients match these filters."
        @update:page="page = $event" @update:page-size="pageSize = $event; page = 1"
        @update:sort-key="sortKey = $event" @update:sort-direction="sortDirection = $event"
        @update:search="filters.search = $event" @refresh="load"
      >
        <template #filters>
          <UiSelect v-model="filters.lifecycle_stage" :options="lifecycleOptions" />
          <UiSelect v-model="filters.owner_id" :options="ownerOptions" searchable />
          <UiSelect v-model="filters.priority" :options="priorityOptions" />
          <UiSelect v-model="filters.status" :options="statusOptions" />
        </template>
        <template #cell-display_name="{ row }">
          <RouterLink class="cp-name" :to="`/clientpulse/${row.id}`">{{ row.display_name || row.legal_name }}</RouterLink>
          <div class="cp-id">#{{ row.id }} &middot; {{ row.source }}</div>
        </template>
        <template #cell-communication_accounts="{ row }">
          <div v-if="row.communication_accounts.length" class="cp-account-list"><span v-for="account in row.communication_accounts" :key="account.id" class="cp-account"><strong>{{ account.name }}</strong><small>{{ account.phone_number || account.session_status }}</small></span></div><span v-else class="cp-muted">Not linked</span>
        </template>
        <template #cell-lifecycle_stage="{ row }">
          <UiDataTableInlineEditor :model-value="row.lifecycle_stage" :options="lifecycleEditOptions" :disabled="!canEdit" :saving="savingCell === `${row.id}:lifecycle_stage`" @save="saveInline(row, 'lifecycle_stage', $event)"><span class="cp-badge">{{ title(row.lifecycle_stage) }}</span></UiDataTableInlineEditor>
        </template>
        <template #cell-owner="{ row }">
          <UiDataTableInlineEditor :model-value="row.owner?.id || ''" :options="ownerEditOptions" :disabled="!canEdit" :saving="savingCell === `${row.id}:owner`" @save="saveInline(row, 'owner', $event)" />
        </template>
        <template #cell-priority="{ row }"><span :class="['cp-badge', `priority-${row.priority}`]">{{ row.priority }}</span></template>
        <template #cell-tags="{ row }">
          <UiDataTableInlineEditor :model-value="row.tags.map(tag => tag.id)" :options="tagEditOptions" multiple empty-label="No tags" :disabled="!canEdit" :saving="savingCell === `${row.id}:tags`" @save="saveInline(row, 'tags', $event)">
            <div class="cp-tags"><span v-for="tag in row.tags" :key="tag.id" class="cp-tag" :style="{ background: tag.color }">{{ tag.name }}</span><span v-if="!row.tags.length" class="cp-muted">No tags</span></div>
          </UiDataTableInlineEditor>
        </template>
        <template #cell-last_contacted_at="{ row }">{{ formatDateTime(row.last_contacted_at) }}</template>
        <template #cell-last_replied_at="{ row }">{{ formatDateTime(row.last_replied_at) }}</template>
        <template #cell-next_follow_up_at="{ row }">{{ formatDateTime(row.next_follow_up_at) }}</template>
      </UiDataTable>
    </UiCard>

    <ClientEditorModal :open="showCreate" :busy="creating" :form="form" :owners="owners" :contacts="conversationContacts" :contact-count="contactCount" :contacts-loading="contactsLoading" @close="closeCreate" @submit="createClient" @search-contacts="searchConversationContacts" />
  </div></main>
</template>

<style scoped>
.directory-page{background:var(--ui-bg)}.directory-hero{align-items:center;padding-bottom:16px;border-bottom:1px solid var(--ui-border)}.directory-panel{margin-top:18px}.directory-panel :deep(.ui-card__body){overflow:visible}.directory-panel :deep(.ui-data-table){border:0;border-radius:0;box-shadow:none}.directory-panel :deep(.ui-data-table__filters .choices){width:180px;min-width:150px;margin:0}.directory-panel :deep(.ui-data-table__viewport){min-height:300px}.cp-account-list{display:grid;gap:3px}.cp-account{display:grid}.cp-account small{color:var(--ui-text-subtle)}.cp-tags{display:flex;flex-wrap:wrap;gap:4px}@media(max-width:900px){.directory-panel :deep(.ui-data-table__filters .choices){width:100%}}
</style>
