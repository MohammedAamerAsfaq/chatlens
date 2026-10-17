<script setup>
import { computed, onMounted, ref } from 'vue'
import { apiConsumerApi } from '@/api'
import UiBadge from '@/components/ui/UiBadge.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiCard from '@/components/ui/UiCard.vue'
import UiCheckboxGroup from '@/components/ui/UiCheckboxGroup.vue'
import UiConfirmModal from '@/components/ui/UiConfirmModal.vue'
import UiDataTable from '@/components/ui/UiDataTable.vue'
import UiFormField from '@/components/ui/UiFormField.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiModal from '@/components/ui/UiModal.vue'
import UiNotice from '@/components/ui/UiNotice.vue'
import UiPage from '@/components/ui/UiPage.vue'
import UiPageHeader from '@/components/ui/UiPageHeader.vue'

const SCOPE_OPTIONS = [
  { value: 'data:read', label: 'Read company data' },
  { value: 'messages:send', label: 'Send outbound messages' },
  { value: 'webhooks:manage', label: 'Manage webhook subscriptions' },
]
const SCOPE_LABELS = { 'data:read': 'Read', 'messages:send': 'Send', 'webhooks:manage': 'Webhooks' }

const columns = [
  { key: 'name', label: 'Name' },
  { key: 'key_prefix', label: 'Key' },
  { key: 'scopes', label: 'Scopes' },
  { key: 'status', label: 'Status' },
  { key: 'last_used_at', label: 'Last used' },
  { key: 'created_at', label: 'Created' },
  { key: 'expires_at', label: 'Expires' },
  { key: 'actions', label: '', headerClass: 'ui-data-table__actions-header' },
]

const keys = ref([])
const loading = ref(false)
const notice = ref(null)
const createOpen = ref(false)
const creating = ref(false)
const name = ref('')
const scopes = ref([])
const expiresAt = ref('')
const createdKey = ref(null)
const copied = ref(false)
const revokeTarget = ref(null)
const revoking = ref(false)

const rows = computed(() => keys.value.map(key => ({
  ...key,
  created_at: formatDate(key.created_at),
  last_used_at: formatDate(key.last_used_at),
  expires_at: key.expires_at ? formatDate(key.expires_at) : 'Never',
})))

function errorMessage(error, fallback) {
  const data = error.response?.data
  if (typeof data?.detail === 'string') return data.detail
  if (data && typeof data === 'object') return Object.values(data).flat().join(' ')
  return fallback
}
function formatDate(value) {
  return value ? new Intl.DateTimeFormat(undefined, { dateStyle: 'short', timeStyle: 'short' }).format(new Date(value)) : '-'
}
function showNotice(tone, message) { notice.value = { tone, message } }

async function loadKeys() {
  loading.value = true
  try {
    const { data } = await apiConsumerApi.list()
    keys.value = data
  } catch (error) {
    showNotice('danger', errorMessage(error, 'Unable to load API keys.'))
  } finally { loading.value = false }
}

function openCreate() {
  name.value = ''
  scopes.value = []
  expiresAt.value = ''
  createOpen.value = true
}

async function submitCreate() {
  creating.value = true
  try {
    const payload = { name: name.value, scopes: scopes.value }
    if (expiresAt.value) payload.expires_at = `${expiresAt.value}T23:59:59`
    const { data } = await apiConsumerApi.create(payload)
    createOpen.value = false
    createdKey.value = data
    copied.value = false
    await loadKeys()
  } catch (error) {
    showNotice('danger', errorMessage(error, 'Unable to create API key.'))
  } finally { creating.value = false }
}

async function copySecret() {
  await navigator.clipboard.writeText(createdKey.value.secret)
  copied.value = true
  setTimeout(() => { copied.value = false }, 1500)
}
function dismissCreatedKey() { createdKey.value = null }

function requestRevoke(key) { revokeTarget.value = key }
async function confirmRevoke() {
  revoking.value = true
  try {
    await apiConsumerApi.revoke(revokeTarget.value.id)
    revokeTarget.value = null
    await loadKeys()
  } catch (error) {
    showNotice('danger', errorMessage(error, 'Unable to revoke API key.'))
  } finally { revoking.value = false }
}

onMounted(loadKeys)
</script>

<template>
  <UiPage width="wide">
    <UiPageHeader eyebrow="External access" title="API Consumer" description="Issue API keys so external parties can read company data, send messages, and receive webhooks from ChatLens." />
    <UiNotice v-if="notice" :tone="notice.tone">{{ notice.message }}</UiNotice>

    <UiCard v-if="createdKey" title="New API key created" subtitle="Copy this secret now. It will not be shown again.">
      <div class="secret-row">
        <code class="secret-value">{{ createdKey.secret }}</code>
        <UiButton variant="secondary" @click="copySecret">{{ copied ? 'Copied!' : 'Copy' }}</UiButton>
        <UiButton variant="default" @click="dismissCreatedKey">Dismiss</UiButton>
      </div>
    </UiCard>

    <UiCard title="API keys" subtitle="Keys are scoped to the currently active company.">
      <template #actions>
        <UiButton variant="primary" @click="openCreate">New key</UiButton>
      </template>
      <UiDataTable :columns="columns" :rows="rows" :total="rows.length" :loading="loading" row-key="id" persist-key="apiconsumer-keys" search-placeholder="Search keys..." empty-title="No API keys have been created yet." @refresh="loadKeys">
        <template #cell-scopes="{ value }">
          <UiBadge v-for="scope in value" :key="scope" tone="neutral">{{ SCOPE_LABELS[scope] || scope }}</UiBadge>
        </template>
        <template #cell-status="{ value }">
          <UiBadge :tone="value === 'active' ? 'success' : 'neutral'">{{ value }}</UiBadge>
        </template>
        <template #cell-actions="{ row }">
          <UiButton v-if="row.status === 'active'" variant="danger" size="small" @click="requestRevoke(row)">Revoke</UiButton>
        </template>
      </UiDataTable>
    </UiCard>

    <UiModal :open="createOpen" title="New API key" subtitle="Choose a name and the scopes this key should carry." @close="createOpen = false">
      <UiFormField label="Name">
        <UiInput v-model="name" placeholder="e.g. Zapier integration" />
      </UiFormField>
      <UiCheckboxGroup v-model="scopes" label="Scopes" :options="SCOPE_OPTIONS" />
      <UiFormField label="Expires" hint="Optional. Leave blank for a key that never expires.">
        <UiInput v-model="expiresAt" type="date" />
      </UiFormField>
      <template #footer>
        <UiButton :disabled="creating" @click="createOpen = false">Cancel</UiButton>
        <UiButton variant="primary" :disabled="creating || !name || !scopes.length" @click="submitCreate">{{ creating ? 'Creating...' : 'Create key' }}</UiButton>
      </template>
    </UiModal>

    <UiConfirmModal
      :open="!!revokeTarget"
      title="Revoke API key"
      :message="`Revoke '${revokeTarget?.name}'? Any external party using this key will immediately lose access.`"
      confirm-label="Revoke"
      danger
      :busy="revoking"
      @confirm="confirmRevoke"
      @cancel="revokeTarget = null"
    />
  </UiPage>
</template>

<style scoped>
.secret-row { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.secret-value { flex: 1 1 auto; min-width: 0; overflow-x: auto; padding: 8px 12px; background: var(--ui-surface-muted, rgba(0,0,0,.04)); border-radius: var(--ui-radius-sm); font-size: .86rem; }
</style>
