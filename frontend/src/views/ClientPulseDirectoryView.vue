<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { clientPulseApi } from '@/api'
import UiButton from '@/components/ui/UiButton.vue'
import UiCard from '@/components/ui/UiCard.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiSelect from '@/components/ui/UiSelect.vue'
import ClientEditorModal from '@/features/clientpulse/components/ClientEditorModal.vue'
import '@/assets/clientpulse.css'

const router = useRouter()
const clients = ref([]), owners = ref([])
const loading = ref(false), creating = ref(false), error = ref(''), showCreate = ref(false)
const conversationContacts = ref([]), contactCount = ref(0), contactsLoading = ref(false)
const page = ref(1), pages = ref(1), count = ref(0)
const filters = reactive({ search: '', lifecycle_stage: '', owner_id: '', priority: '', status: 'active' })
const emptyClientForm = () => ({
  creation_mode: 'manual', whatsapp_contact_id: '', contact_search: '',
  display_name: '', company_name: '', job_title: '', phone: '', email: '', website: '',
  address_line1: '', address_line2: '', city: '', state_region: '', postal_code: '',
  country: '', notes: '', lifecycle_stage: 'lead', priority: 'normal', owner_id: '',
})
const form = reactive(emptyClientForm())
let searchTimer, contactSearchTimer, contactRequest = 0

const lifecycleOptions = [
  { value: '', label: 'All lifecycle stages' },
  ...['lead', 'prospect', 'active_customer', 'dormant', 'lost', 'blocked'].map(value => ({ value, label: value.replaceAll('_', ' ') })),
]
const priorityOptions = [
  { value: '', label: 'All priorities' },
  ...['low', 'normal', 'high', 'critical'].map(value => ({ value, label: value[0].toUpperCase() + value.slice(1) })),
]
const statusOptions = [
  { value: 'active', label: 'Active clients' }, { value: 'paused', label: 'Inactive clients' },
  { value: 'archived', label: 'Archived (legacy)' }, { value: 'all', label: 'All clients' },
]
const ownerOptions = computed(() => [
  { value: '', label: 'All owners' },
  ...owners.value.map(owner => ({ value: owner.id, label: owner.username })),
])

function message(exc, fallback) { return exc.response?.data?.detail || fallback }
function resetForm() { Object.assign(form, emptyClientForm()) }
function openCreate() { resetForm(); showCreate.value = true }
function closeCreate() { if (!creating.value) showCreate.value = false }
function searchConversationContacts(value) {
  clearTimeout(contactSearchTimer)
  form.contact_search = value
  form.whatsapp_contact_id = ''
  contactSearchTimer = setTimeout(loadConversationContacts, 300)
}
async function loadConversationContacts() {
  const request = ++contactRequest
  contactsLoading.value = true
  try {
    const { data } = await clientPulseApi.conversationContacts({ search: form.contact_search.trim(), page_size: 50 })
    if (request !== contactRequest) return
    conversationContacts.value = data.results
    contactCount.value = data.count
  } catch (exc) {
    if (request === contactRequest) error.value = message(exc, 'Unable to load WhatsApp contacts.')
  } finally {
    if (request === contactRequest) contactsLoading.value = false
  }
}
async function load() {
  loading.value = true; error.value = ''
  try {
    const { data } = await clientPulseApi.clients({ ...filters, page: page.value, page_size: 25 })
    clients.value = data.results; count.value = data.count
    pages.value = Math.max(1, Math.ceil(data.count / 25))
  } catch (exc) { error.value = message(exc, 'Unable to load clients.') }
  finally { loading.value = false }
}
async function createClient() {
  creating.value = true; error.value = ''
  if (form.creation_mode === 'whatsapp') {
    if (!form.whatsapp_contact_id) {
      error.value = 'Select a WhatsApp contact.'; creating.value = false; return
    }
    try {
      const { data } = await clientPulseApi.convertConversationContact(form.whatsapp_contact_id, {
        lifecycle_stage: form.lifecycle_stage,
      })
      showCreate.value = false; router.push(`/clientpulse/${data.profile.id}`)
    } catch (exc) { error.value = message(exc, 'Unable to create client from WhatsApp.') }
    finally { creating.value = false }
    return
  }
  const payload = {
    display_name: form.display_name.trim(), lifecycle_stage: form.lifecycle_stage,
    priority: form.priority, owner_id: form.owner_id || null,
    company_name: form.company_name.trim(), job_title: form.job_title.trim(),
    website: form.website.trim(), address_line1: form.address_line1.trim(),
    address_line2: form.address_line2.trim(), city: form.city.trim(),
    state_region: form.state_region.trim(), postal_code: form.postal_code.trim(),
    country: form.country.trim(), notes: form.notes.trim(),
  }
  payload.identities = []
  if (form.phone.trim()) payload.identities.push({ identity_type: 'phone', value: form.phone.trim(), is_primary: true })
  if (form.email.trim()) payload.identities.push({ identity_type: 'email', value: form.email.trim(), is_primary: !payload.identities.length })
  try {
    const { data } = await clientPulseApi.createClient(payload)
    showCreate.value = false; router.push(`/clientpulse/${data.id}`)
  } catch (exc) { error.value = message(exc, 'Unable to create client.') }
  finally { creating.value = false }
}
function move(next) { page.value = next; load() }
watch(() => [filters.lifecycle_stage, filters.owner_id, filters.priority, filters.status], () => { page.value = 1; load() })
watch(() => filters.search, () => {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => { page.value = 1; load() }, 350)
})
watch(() => form.creation_mode, mode => {
  if (showCreate.value && mode === 'whatsapp') loadConversationContacts()
})
onMounted(async () => {
  try { owners.value = (await clientPulseApi.options()).data.owners; await load() }
  catch (exc) { error.value = message(exc, 'Unable to initialize ClientPulse.') }
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
      <template #actions><UiButton size="small" variant="outline" :disabled="loading" @click="load">Refresh</UiButton></template>
      <div class="directory-toolbar">
        <div class="directory-search">
          <UiInput v-model="filters.search" type="search" placeholder="Search name, phone, or email..."><template #prefix>&#128269;</template></UiInput>
        </div>
        <UiSelect v-model="filters.lifecycle_stage" :options="lifecycleOptions" />
        <UiSelect v-model="filters.owner_id" :options="ownerOptions" searchable />
        <UiSelect v-model="filters.priority" :options="priorityOptions" />
        <UiSelect v-model="filters.status" :options="statusOptions" />
      </div>

      <div class="directory-table-wrap">
        <div v-if="loading" class="cp-empty">Loading clients...</div>
        <table v-else v-ui-data-table="'clientpulse-directory'" class="cp-table"><thead><tr><th>Client</th><th>Communication account</th><th>Lifecycle</th><th>Owner</th><th>Priority</th><th>Tags</th><th>Last contact</th><th>Next follow-up</th></tr></thead><tbody>
          <tr v-for="client in clients" :key="client.id">
            <td><RouterLink class="cp-name" :to="`/clientpulse/${client.id}`">{{ client.display_name || client.legal_name }}</RouterLink><div class="cp-id">#{{ client.id }} &middot; {{ client.source }}</div></td>
            <td><div v-if="client.communication_accounts.length" class="cp-account-list"><span v-for="account in client.communication_accounts" :key="account.id" class="cp-account"><strong>{{ account.name }}</strong><small>{{ account.phone_number || account.session_status }}</small></span></div><span v-else class="cp-muted">Not linked</span></td>
            <td><span class="cp-badge">{{ client.lifecycle_stage.replaceAll('_', ' ') }}</span></td>
            <td>{{ client.owner?.user?.username || 'Unassigned' }}</td>
            <td><span :class="['cp-badge', `priority-${client.priority}`]">{{ client.priority }}</span></td>
            <td><div class="cp-tags"><span v-for="tag in client.tags" :key="tag.id" class="cp-tag" :style="{ background: tag.color }">{{ tag.name }}</span></div></td>
            <td>{{ client.last_contacted_at ? new Date(client.last_contacted_at).toLocaleDateString() : '-' }}</td>
            <td>{{ client.next_follow_up_at ? new Date(client.next_follow_up_at).toLocaleDateString() : '-' }}</td>
          </tr>
        </tbody></table>
        <div v-if="!loading && !clients.length" class="cp-empty">No clients match these filters.</div>
      </div>
      <footer class="cp-pager"><span>{{ count }} clients</span><div><UiButton size="small" :disabled="page <= 1" @click="move(page - 1)">Previous</UiButton><span>Page {{ page }} of {{ pages }}</span><UiButton size="small" :disabled="page >= pages" @click="move(page + 1)">Next</UiButton></div></footer>
    </UiCard>

    <ClientEditorModal :open="showCreate" :busy="creating" :form="form" :owners="owners" :contacts="conversationContacts" :contact-count="contactCount" :contacts-loading="contactsLoading" @close="closeCreate" @submit="createClient" @search-contacts="searchConversationContacts" />
  </div></main>
</template>

<style scoped>
.directory-page{background:var(--ui-bg)}.directory-hero{align-items:center;padding-bottom:16px;border-bottom:1px solid var(--ui-border)}.directory-panel{margin-top:18px}.directory-toolbar{display:grid;grid-template-columns:minmax(260px,1.5fr) repeat(4,minmax(145px,.7fr));gap:10px;padding:14px;border-bottom:1px solid var(--ui-border);background:var(--ui-surface-muted)}.directory-toolbar :deep(.choices){min-width:0}.directory-table-wrap{overflow:auto}.cp-pager>div{display:flex;align-items:center;gap:8px}@media(max-width:1100px){.directory-toolbar{grid-template-columns:repeat(2,minmax(0,1fr))}.directory-search{grid-column:1/-1}}@media(max-width:650px){.directory-toolbar{grid-template-columns:1fr}.directory-search{grid-column:auto}.cp-pager{align-items:flex-start;gap:10px;flex-direction:column}}
</style>
