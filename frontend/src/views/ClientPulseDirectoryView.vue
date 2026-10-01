<script setup>
import { onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { clientPulseApi } from '@/api'
import '@/assets/clientpulse.css'

const router = useRouter()
const clients = ref([]), owners = ref([])
const loading = ref(false), creating = ref(false), error = ref('')
const page = ref(1), pages = ref(1), count = ref(0), showCreate = ref(false)
const filters = reactive({ search: '', lifecycle_stage: '', owner_id: '', priority: '', status: 'active' })
const form = reactive({ display_name: '', phone: '', lifecycle_stage: 'lead', priority: 'normal', owner_id: null })
let searchTimer

function message(exc, fallback) { return exc.response?.data?.detail || fallback }
async function load() {
  loading.value = true; error.value = ''
  try {
    const { data } = await clientPulseApi.clients({ ...filters, page: page.value, page_size: 25 })
    clients.value = data.results; count.value = data.count; pages.value = Math.max(1, Math.ceil(data.count / 25))
  } catch (exc) { error.value = message(exc, 'Unable to load clients.') } finally { loading.value = false }
}
async function createClient() {
  creating.value = true; error.value = ''
  const payload = { display_name: form.display_name, lifecycle_stage: form.lifecycle_stage, priority: form.priority, owner_id: form.owner_id || null }
  if (form.phone) payload.identities = [{ identity_type: 'phone', value: form.phone, is_primary: true }]
  try { const { data } = await clientPulseApi.createClient(payload); router.push(`/clientpulse/${data.id}`) }
  catch (exc) { error.value = message(exc, 'Unable to create client.') } finally { creating.value = false }
}
function move(next) { page.value = next; load() }
watch(() => [filters.lifecycle_stage, filters.owner_id, filters.priority, filters.status], () => { page.value = 1; load() })
watch(() => filters.search, () => { clearTimeout(searchTimer); searchTimer = setTimeout(() => { page.value = 1; load() }, 350) })
onMounted(async () => {
  try { owners.value = (await clientPulseApi.options()).data.owners; await load() }
  catch (exc) { error.value = message(exc, 'Unable to initialize ClientPulse.') }
})
</script>

<template><main class="cp-page"><div class="cp-shell">
  <header class="cp-hero"><div><p class="cp-eyebrow">Customer intelligence</p><h1 class="cp-title">ClientPulse</h1><p class="cp-muted">Company-owned contacts, relationships, consent, and follow-up context.</p></div><button class="cp-button cp-primary" @click="showCreate=!showCreate">{{ showCreate?'Close':'New client' }}</button></header>
  <p v-if="error" class="cp-notice error">{{ error }}</p>
  <section v-if="showCreate" class="cp-panel cp-card"><h2>Create client</h2><form class="cp-form-grid" @submit.prevent="createClient"><label>Name<input v-model.trim="form.display_name" class="cp-input" required /></label><label>Phone<input v-model.trim="form.phone" class="cp-input" /></label><label>Owner<select v-model="form.owner_id" class="cp-select"><option :value="null">Unassigned</option><option v-for="owner in owners" :key="owner.id" :value="owner.id">{{ owner.username }}</option></select></label><label>Lifecycle<select v-model="form.lifecycle_stage" class="cp-select"><option value="lead">Lead</option><option value="prospect">Prospect</option><option value="active_customer">Active customer</option></select></label><label>Priority<select v-model="form.priority" class="cp-select"><option v-for="value in ['low','normal','high','critical']" :key="value">{{ value }}</option></select></label><div class="cp-actions"><button class="cp-button cp-primary" :disabled="creating">{{ creating?'Creating...':'Create' }}</button></div></form></section>
  <section class="cp-panel cp-toolbar"><input v-model="filters.search" class="cp-input" placeholder="Search name, phone, email..." /><select v-model="filters.lifecycle_stage" class="cp-select"><option value="">All lifecycle stages</option><option v-for="value in ['lead','prospect','active_customer','dormant','lost','blocked']" :key="value" :value="value">{{ value.replaceAll('_',' ') }}</option></select><select v-model="filters.owner_id" class="cp-select"><option value="">All owners</option><option v-for="owner in owners" :key="owner.id" :value="owner.id">{{ owner.username }}</option></select><select v-model="filters.priority" class="cp-select"><option value="">All priorities</option><option v-for="value in ['low','normal','high','critical']" :key="value">{{ value }}</option></select><select v-model="filters.status" class="cp-select"><option value="active">Active</option><option value="paused">Paused</option><option value="archived">Archived</option><option value="all">All</option></select><button class="cp-button" @click="load">Refresh</button></section>
  <section class="cp-panel cp-grid"><div v-if="loading" class="cp-empty">Loading clients...</div><table v-else class="cp-table"><thead><tr><th>Client</th><th>Lifecycle</th><th>Owner</th><th>Priority</th><th>Tags</th><th>Last contact</th><th>Next follow-up</th></tr></thead><tbody><tr v-for="client in clients" :key="client.id"><td><RouterLink class="cp-name" :to="`/clientpulse/${client.id}`">{{ client.display_name || client.legal_name }}</RouterLink><div class="cp-id">#{{ client.id }} · {{ client.source }}</div></td><td><span class="cp-badge">{{ client.lifecycle_stage.replaceAll('_',' ') }}</span></td><td>{{ client.owner?.user?.username || 'Unassigned' }}</td><td><span :class="['cp-badge',`priority-${client.priority}`]">{{ client.priority }}</span></td><td><div class="cp-tags"><span v-for="tag in client.tags" :key="tag.id" class="cp-tag" :style="{background:tag.color}">{{ tag.name }}</span></div></td><td>{{ client.last_contacted_at ? new Date(client.last_contacted_at).toLocaleDateString() : '—' }}</td><td>{{ client.next_follow_up_at ? new Date(client.next_follow_up_at).toLocaleDateString() : '—' }}</td></tr></tbody></table><div v-if="!loading&&!clients.length" class="cp-empty">No clients match these filters.</div><footer class="cp-pager"><span>{{ count }} clients</span><div><button class="cp-button" :disabled="page<=1" @click="move(page-1)">Previous</button> <span>Page {{ page }} of {{ pages }}</span> <button class="cp-button" :disabled="page>=pages" @click="move(page+1)">Next</button></div></footer></section>
</div></main></template>
