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

const API_BASE_URL = '/api/external/v1'
const ENDPOINTS = [
  { method: 'GET', path: '/ping/', scope: null, description: 'Verify a key is valid and see which company and scopes it carries. Works with any valid key, no scope required.' },
  { method: 'GET', path: '/contacts/', scope: 'data:read', description: 'List and retrieve WhatsApp contacts.' },
  { method: 'GET', path: '/chats/', scope: 'data:read', description: 'List and retrieve chats.' },
  { method: 'GET', path: '/messages/', scope: 'data:read', description: 'List messages. Supports an optional ?chat=<id> filter.' },
  { method: 'GET', path: '/outbound-messages/', scope: 'data:read', description: 'Status of messages sent through this API.' },
  { method: 'GET', path: '/inquiries/', scope: 'data:read', description: 'List buying/selling inquiries. Optional ?status=, ?inquiry_type=, ?first_seen_after=, ?first_seen_before= (ISO 8601) filters. Paginated.' },
  { method: 'GET', path: '/products/', scope: 'data:read', description: 'The product catalog. Defaults to tracked products only. Optional ?tracking=, ?is_active=, ?category=, ?search= filters. Paginated.' },
  { method: 'GET', path: '/product-mentions/', scope: 'data:read', description: 'Per-product WTB/WTS mention counts over a date range. ?first_seen_after=, ?first_seen_before= (default: last 30 days), ?search=, ?limit= (default 100, max 500). Not paginated — returns one grouped summary.' },
  { method: 'POST', path: '/send-message/', scope: 'messages:send', description: 'Send an outbound WhatsApp message.' },
  { method: 'GET / POST', path: '/webhooks/', scope: 'webhooks:manage', description: 'List or create webhook subscriptions.' },
  { method: 'PATCH / DELETE', path: '/webhooks/{id}/', scope: 'webhooks:manage', description: 'Update or remove a webhook subscription.' },
  { method: 'GET', path: '/webhooks/{id}/deliveries/', scope: 'webhooks:manage', description: 'Delivery attempt log for one subscription.' },
]
function methodTone(method) {
  if (method.startsWith('GET')) return 'neutral'
  if (method.startsWith('POST')) return 'success'
  return 'warning'
}

const QUICK_START_STEPS = [
  'Create a key below with the scopes your integration actually needs.',
  'Call GET /ping/ with it to confirm the key works — this one accepts any key, even with no scopes.',
  'Call the data/action endpoints you need, using the scopes you granted the key.',
  'Optionally register a webhook so ChatLens pushes events to you instead of you polling for changes.',
]

const FILTER_REFERENCE = [
  { path: '/messages/', params: '?chat=<id>' },
  { path: '/inquiries/', params: '?status=&inquiry_type=&first_seen_after=&first_seen_before=' },
  { path: '/products/', params: '?tracking=&is_active=&category=&search=' },
  { path: '/product-mentions/', params: '?first_seen_after=&first_seen_before=&search=&limit=' },
]

const ERROR_CODES = [
  { code: '400', meaning: 'Bad input — e.g. an unparseable date filter, or a request body that failed validation.' },
  { code: '401', meaning: "Invalid, revoked, or expired key, or the key's company is no longer active." },
  { code: '403', meaning: 'The key is valid but does not carry the scope this endpoint requires.' },
  { code: '404', meaning: 'The referenced object does not exist, or does not belong to this key’s company.' },
  { code: '409', meaning: 'POST /send-message/ only — the destination looks like a new chat and confirm_new_chat was not set.' },
  { code: '429', meaning: 'Rate limit exceeded for this key.' },
]

const CURL_EXAMPLES = [
  { title: 'Verify a key', command: 'curl ' + API_BASE_URL + '/ping/ \\\n  -H "Authorization: Api-Key <prefix>.<secret>"' },
  { title: 'List contacts, page 2 of 25', command: 'curl "' + API_BASE_URL + '/contacts/?page=2&page_size=25" \\\n  -H "Authorization: Api-Key <prefix>.<secret>"' },
  {
    title: 'Send a message',
    command: 'curl -X POST ' + API_BASE_URL + '/send-message/ \\\n'
      + '  -H "Authorization: Api-Key <prefix>.<secret>" \\\n'
      + '  -H "Content-Type: application/json" \\\n'
      + '  -d \'{"whatsapp_account_id": 1, "destination_jid": "971500000000@s.whatsapp.net", "text": "Hello"}\'',
  },
  { title: 'Product mentions in the last 7 days', command: 'curl "' + API_BASE_URL + '/product-mentions/?first_seen_after=2026-10-10T00:00:00Z" \\\n  -H "Authorization: Api-Key <prefix>.<secret>"' },
  { title: 'Search the tracked product catalog', command: 'curl "' + API_BASE_URL + '/products/?search=iphone" \\\n  -H "Authorization: Api-Key <prefix>.<secret>"' },
]

const WEBHOOK_VERIFY_SNIPPET = 'import hmac, hashlib\n\n'
  + 'expected = hmac.new(subscription_secret.encode(), request_body, hashlib.sha256).hexdigest()\n'
  + "received = request.headers['X-ChatLens-Signature']\n"
  + 'is_valid = hmac.compare_digest(expected, received)'

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

function legacyCopy(text) {
  const textarea = document.createElement('textarea')
  textarea.value = text
  textarea.style.position = 'fixed'
  textarea.style.opacity = '0'
  document.body.appendChild(textarea)
  textarea.focus()
  textarea.select()
  const succeeded = document.execCommand('copy')
  document.body.removeChild(textarea)
  if (!succeeded) throw new Error('execCommand copy failed')
}

async function copySecret() {
  const text = createdKey.value.secret
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text)
    } else {
      legacyCopy(text)
    }
    copied.value = true
    setTimeout(() => { copied.value = false }, 1500)
  } catch {
    showNotice('danger', 'Could not copy automatically (this page is not served over HTTPS). Select the key text and copy it manually.')
  }
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

    <UiCard title="Usage guide" subtitle="Everything a third-party developer needs to integrate, in one place.">
      <section class="guide-section">
        <h3>Quick start</h3>
        <ol>
          <li v-for="step in QUICK_START_STEPS" :key="step">{{ step }}</li>
        </ol>
      </section>

      <section class="guide-section">
        <h3>Authentication</h3>
        <p>
          Every request carries <code>Authorization: Api-Key &lt;prefix&gt;.&lt;secret&gt;</code>. The secret is shown
          exactly once, right after you create a key — if you lose it, there's no way to recover it, only revoke the
          key and create a new one. Scopes are fixed at creation time too; there's no "edit scopes" action, by design.
        </p>
      </section>

      <section class="guide-section">
        <h3>Scopes</h3>
        <ul>
          <li v-for="option in SCOPE_OPTIONS" :key="option.value"><code>{{ option.value }}</code> — {{ option.label }}.</li>
        </ul>
      </section>

      <section class="guide-section">
        <h3>Pagination</h3>
        <p>
          List endpoints accept <code>?page=</code> and <code>?page_size=</code> (default 50, max 200) and return
          <code>{ count, next, previous, results }</code>. <code>/product-mentions/</code> is the one exception — it
          returns a single grouped summary rather than a page of rows, so it uses its own <code>?limit=</code> instead
          (default 100, max 500).
        </p>
      </section>

      <section class="guide-section">
        <h3>Filtering reference</h3>
        <table class="guide-table">
          <thead><tr><th>Endpoint</th><th>Query params</th></tr></thead>
          <tbody>
            <tr v-for="item in FILTER_REFERENCE" :key="item.path">
              <td><code>{{ API_BASE_URL }}{{ item.path }}</code></td>
              <td><code>{{ item.params }}</code></td>
            </tr>
          </tbody>
        </table>
      </section>

      <section class="guide-section">
        <h3>Rate limits</h3>
        <p>Each key is limited to <strong>60 requests per minute</strong> by default. Exceeding it returns <code>429</code>.</p>
      </section>

      <section class="guide-section">
        <h3>Errors</h3>
        <table class="guide-table">
          <thead><tr><th>Status</th><th>Meaning</th></tr></thead>
          <tbody>
            <tr v-for="item in ERROR_CODES" :key="item.code">
              <td><UiBadge tone="neutral">{{ item.code }}</UiBadge></td>
              <td>{{ item.meaning }}</td>
            </tr>
          </tbody>
        </table>
      </section>

      <section class="guide-section">
        <h3>Webhooks</h3>
        <p>
          Register a target URL with <code>POST {{ API_BASE_URL }}/webhooks/</code> (requires the
          <code>webhooks:manage</code> scope) with the event types you want. The response includes a signing
          <code>secret</code>, shown once — save it, it's how you verify deliveries are really from ChatLens.
        </p>
        <p>Two event types exist today: <code>message.inbound.received</code> and <code>outbound_message.status_changed</code>.</p>
        <p>
          Every delivery POSTs a JSON body to your URL with an <code>X-ChatLens-Event</code> header naming the event,
          and an <code>X-ChatLens-Signature</code> header — an HMAC-SHA256 hex digest of the raw request body, keyed
          with your subscription's secret. Verify it like this before trusting the payload:
        </p>
        <pre class="guide-code">{{ WEBHOOK_VERIFY_SNIPPET }}</pre>
        <p>
          A failed delivery (non-2xx response, or a timeout) is retried up to 5 times total, with exponential backoff
          starting at 15 seconds and capping at 15 minutes between attempts. Check
          <code>{{ API_BASE_URL }}/webhooks/{id}/deliveries/</code> for the attempt history on a subscription.
        </p>
      </section>

      <section class="guide-section">
        <h3>Examples</h3>
        <div v-for="example in CURL_EXAMPLES" :key="example.title" class="guide-example">
          <p class="guide-example__title">{{ example.title }}</p>
          <pre class="guide-code">{{ example.command }}</pre>
        </div>
      </section>
    </UiCard>

    <UiCard title="Available endpoints" subtitle="Everything a key can reach, depending on the scopes it was granted.">
      <UiNotice tone="info">
        Base URL: <code>{{ API_BASE_URL }}</code> &middot; Authenticate with <code>Authorization: Api-Key &lt;prefix&gt;.&lt;secret&gt;</code>
        <br>List endpoints are paginated: <code>?page=</code> and <code>?page_size=</code> (default 50, max 200), returning <code>{ count, next, previous, results }</code>.
      </UiNotice>
      <div class="endpoints-table">
        <table>
          <thead>
            <tr><th>Method</th><th>Path</th><th>Scope</th><th>Description</th></tr>
          </thead>
          <tbody>
            <tr v-for="endpoint in ENDPOINTS" :key="endpoint.path + endpoint.method">
              <td><UiBadge :tone="methodTone(endpoint.method)">{{ endpoint.method }}</UiBadge></td>
              <td><code>{{ API_BASE_URL }}{{ endpoint.path }}</code></td>
              <td><UiBadge :tone="endpoint.scope ? 'neutral' : 'success'">{{ endpoint.scope ? SCOPE_LABELS[endpoint.scope] : 'Any key' }}</UiBadge></td>
              <td>{{ endpoint.description }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </UiCard>

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
.endpoints-table { overflow-x: auto; margin-top: var(--ui-gap-md); }
.endpoints-table table { width: 100%; border-collapse: collapse; font-size: .86rem; }
.endpoints-table th { text-align: left; padding: 8px 12px; color: var(--ui-text-muted); font-weight: 600; border-bottom: 1px solid var(--ui-border, rgba(0,0,0,.08)); }
.endpoints-table td { padding: 8px 12px; border-bottom: 1px solid var(--ui-border, rgba(0,0,0,.06)); vertical-align: top; }
.endpoints-table code { font-size: .82rem; }

.guide-section { margin-bottom: var(--ui-gap-lg); }
.guide-section:last-child { margin-bottom: 0; }
.guide-section h3 { margin: 0 0 8px; font-size: .95rem; }
.guide-section p { margin: 0 0 8px; color: var(--ui-text-muted); line-height: 1.5; }
.guide-section ul, .guide-section ol { margin: 0; padding-left: 20px; color: var(--ui-text-muted); line-height: 1.6; }
.guide-table { width: 100%; border-collapse: collapse; font-size: .86rem; }
.guide-table th { text-align: left; padding: 6px 12px; color: var(--ui-text-muted); font-weight: 600; border-bottom: 1px solid var(--ui-border, rgba(0,0,0,.08)); }
.guide-table td { padding: 6px 12px; border-bottom: 1px solid var(--ui-border, rgba(0,0,0,.06)); vertical-align: top; }
.guide-code { margin: 0; padding: 10px 12px; background: var(--ui-surface-muted, rgba(0,0,0,.04)); border-radius: var(--ui-radius-sm); font-size: .8rem; overflow-x: auto; white-space: pre; }
.guide-example { margin-bottom: 12px; }
.guide-example:last-child { margin-bottom: 0; }
.guide-example__title { margin: 0 0 6px; font-weight: 600; font-size: .86rem; }
</style>
