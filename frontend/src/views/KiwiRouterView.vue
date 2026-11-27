<script setup>
import { computed, onMounted, ref } from 'vue'
import { FontAwesomeIcon } from '@fortawesome/vue-fontawesome'
import { faArrowDown, faArrowUp, faCloudArrowDown, faPlus, faTrashCan } from '@fortawesome/free-solid-svg-icons'
import { aiProvidersApi, kiwiRoutersApi } from '@/api'
import UiBadge from '@/components/ui/UiBadge.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiCard from '@/components/ui/UiCard.vue'
import UiEmptyState from '@/components/ui/UiEmptyState.vue'
import UiFormField from '@/components/ui/UiFormField.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiMetric from '@/components/ui/UiMetric.vue'
import UiNotice from '@/components/ui/UiNotice.vue'
import UiPage from '@/components/ui/UiPage.vue'
import UiPageHeader from '@/components/ui/UiPageHeader.vue'
import UiSelect from '@/components/ui/UiSelect.vue'
import UiToggle from '@/components/ui/UiToggle.vue'

const routers = ref([]), providers = ref([]), selectedId = ref(null), saving = ref(false), error = ref(''), notice = ref('')
const creating = ref(false), newName = ref('')
const selected = computed(() => routers.value.find(router => router.id === selectedId.value))

const capabilityLabel = value => ({ agent: 'General AI Agent', chat: 'Chat / Completion', embedding: 'Embeddings' }[value] || value)
const strategyOptions = [{ value: 'ordered_capacity_fill', label: 'Ordered capacity fill' }]
const strategyLabel = value => strategyOptions.find(option => option.value === value)?.label || value
const metadataOptions = [
  { value: 'incomplete', label: 'Incomplete' },
  { value: 'provider_published', label: 'Provider published' },
  { value: 'operator_supplied', label: 'Operator supplied' },
]
const providerOptions = computed(() => providers.value.map(provider => ({ value: provider.id, label: `${provider.display_name} · ${provider.model}` })))
const totalRpm = computed(() => (selected.value?.members || []).reduce((sum, item) => sum + (item.rpm_limit || 0), 0))
const verifiedCount = computed(() => (selected.value?.members || []).filter(item => item.metadata_source === 'provider_published').length)

// Numeric limits are optional: an emptied box means "no value", not 0.
const toNumber = value => (value === '' || value == null ? null : Number(value))

function formatApiError(value, path = '') {
  if (Array.isArray(value)) return value.map(item => formatApiError(item, path)).filter(Boolean).join(' ')
  if (value && typeof value === 'object') return Object.entries(value).map(([key, item]) => formatApiError(item, path ? `${path}.${key}` : key)).filter(Boolean).join(' ')
  return value == null ? '' : `${path ? `${path}: ` : ''}${value}`
}
function clearMessages() { error.value = ''; notice.value = '' }

async function load() {
  try {
    const [r, p] = await Promise.all([kiwiRoutersApi.list(), aiProvidersApi.list()])
    routers.value = r.data
    providers.value = p.data.filter(item => item.capability === 'agent')
    selectedId.value = routers.value[0]?.id ?? null
  } catch {
    error.value = 'Unable to load KiwiRouter configuration.'
  }
}
function selectRouter(id) { selectedId.value = id; clearMessages() }
async function create() {
  if (!newName.value.trim()) return
  clearMessages()
  try {
    const { data } = await kiwiRoutersApi.create({ name: newName.value.trim(), capability: 'agent', strategy: 'ordered_capacity_fill', members: [] })
    routers.value.push(data)
    selectedId.value = data.id
    newName.value = ''
    creating.value = false
  } catch (requestError) {
    error.value = formatApiError(requestError.response?.data) || 'Unable to create router.'
  }
}
async function save() {
  clearMessages()
  if (!selected.value?.name.trim()) { error.value = 'Router name is required.'; return }
  saving.value = true
  try {
    const { data } = await kiwiRoutersApi.update(selected.value.id, selected.value)
    routers.value[routers.value.findIndex(item => item.id === data.id)] = data
    notice.value = 'Router saved.'
  } catch (requestError) {
    error.value = formatApiError(requestError.response?.data) || 'Unable to save router.'
  } finally {
    saving.value = false
  }
}
async function removeRouter() {
  if (!selected.value || !confirm(`Delete router "${selected.value.name}"?`)) return
  clearMessages()
  try {
    const id = selected.value.id
    await kiwiRoutersApi.delete(id)
    routers.value = routers.value.filter(item => item.id !== id)
    selectedId.value = routers.value[0]?.id ?? null
  } catch {
    error.value = 'Unable to delete router. Remove any active reservations first.'
  }
}
function addMember() {
  const p = providers.value[0]
  if (!p) { error.value = 'Create a General AI Agent in AI Providers first.'; return }
  selected.value.members ??= []
  selected.value.members.push({ provider_config: p.id, priority: selected.value.members.length + 1, is_enabled: true, rpm_limit: null, tpm_limit: null, max_concurrency: null, input_cost_per_million: null, output_cost_per_million: null, request_timeout_seconds: 60, metadata_source: 'incomplete' })
}
function renumber() { selected.value.members.forEach((member, i) => { member.priority = i + 1 }) }
function removeMember(index) { selected.value.members.splice(index, 1); renumber() }
function move(index, delta) {
  const rows = selected.value.members, target = index + delta
  if (target < 0 || target >= rows.length) return
  ;[rows[index], rows[target]] = [rows[target], rows[index]]
  renumber()
}
async function fetchMetadata(member) {
  clearMessages()
  try {
    const { data } = await aiProvidersApi.fetchMetadata(member.provider_config)
    if (!data.available) { notice.value = data.detail; return }
    const metadata = data.metadata || {}
    for (const field of ['input_cost_per_million', 'output_cost_per_million']) if (metadata[field] != null) metadata[field] = Number(Number(metadata[field]).toFixed(4))
    if (Object.keys(metadata).length) Object.assign(member, metadata, { metadata_source: 'provider_published' })
    const account = data.account_metadata || {}
    const feedback = []
    if (account.limit_remaining != null) feedback.push(`credit remaining: $${account.limit_remaining}`)
    if (account.limit_reset) feedback.push(`reset: ${account.limit_reset}`)
    if (account.usage_daily != null) feedback.push(`daily usage: $${account.usage_daily}`)
    if (account.usage_monthly != null) feedback.push(`monthly usage: $${account.usage_monthly}`)
    notice.value = [data.detail, feedback.length ? `Key ${feedback.join(', ')}.` : ''].filter(Boolean).join(' ')
  } catch (requestError) {
    error.value = formatApiError(requestError.response?.data) || 'Provider metadata request failed. Enter verified values manually.'
  }
}
onMounted(load)

const numberFields = [
  { key: 'rpm_limit', label: 'RPM', placeholder: 'Required', min: 1 },
  { key: 'tpm_limit', label: 'TPM', placeholder: 'Optional', min: 1 },
  { key: 'max_concurrency', label: 'Concurrent', placeholder: 'Optional', min: 1 },
  { key: 'request_timeout_seconds', label: 'Timeout (s)', placeholder: '60', min: 1 },
  { key: 'input_cost_per_million', label: 'Input $ / 1M', placeholder: 'Optional', min: 0, step: '0.0001' },
  { key: 'output_cost_per_million', label: 'Output $ / 1M', placeholder: 'Optional', min: 0, step: '0.0001' },
]
</script>

<template>
  <UiPage width="full">
    <UiPageHeader eyebrow="AI routing" title="KiwiRouter" description="Reusable provider capacity and policy routing. Workflow assignment is configured separately." />
    <UiNotice v-if="error" tone="danger">{{ error }}</UiNotice>
    <UiNotice v-else-if="notice" tone="success">{{ notice }}</UiNotice>

    <div class="kiwi">
      <UiCard class="kiwi__routers" title="Routers">
        <template #actions>
          <UiButton size="small" variant="soft" :aria-expanded="creating" @click="creating = !creating"><FontAwesomeIcon :icon="faPlus" /> New</UiButton>
        </template>
        <form v-if="creating" class="kiwi__new" @submit.prevent="create">
          <UiFormField label="Router name"><UiInput v-model.trim="newName" autofocus placeholder="e.g. Inquiry Economy Router" /></UiFormField>
          <UiButton type="submit" variant="primary" size="small" :disabled="!newName.trim()">Create router</UiButton>
        </form>
        <nav class="kiwi__list" aria-label="Routers">
          <button v-for="router in routers" :key="router.id" type="button" class="kiwi__router" :class="{ 'is-selected': router.id === selectedId }" @click="selectRouter(router.id)">
            <span class="kiwi__router-name"><strong>{{ router.name }}</strong><UiBadge :tone="router.is_active ? 'success' : 'neutral'" dot>{{ router.is_active ? 'Active' : 'Off' }}</UiBadge></span>
            <small>{{ router.members.length }} agents · {{ strategyLabel(router.strategy) }}</small>
          </button>
        </nav>
        <p class="kiwi__muted">{{ routers.length ? 'Each router has its own ordered members and capacity policy.' : 'Create a router, then add configured AI Provider Agents.' }}</p>
      </UiCard>

      <div v-if="selected" class="kiwi__workspace">
        <UiCard :title="selected.name || 'Untitled router'" :subtitle="`${capabilityLabel(selected.capability)} · ${strategyLabel(selected.strategy)}`">
          <template #actions>
            <UiButton variant="danger" @click="removeRouter"><FontAwesomeIcon :icon="faTrashCan" /> Delete</UiButton>
            <UiButton variant="primary" :disabled="saving" @click="save">{{ saving ? 'Saving...' : 'Save changes' }}</UiButton>
          </template>
          <div class="kiwi__settings">
            <UiFormField label="Router name"><UiInput v-model="selected.name" /></UiFormField>
            <UiFormField label="Strategy" hint="Cost and latency strategies stay unavailable until every provider value is verified.">
              <UiSelect v-model="selected.strategy" :options="strategyOptions" />
            </UiFormField>
            <div class="kiwi__toggle"><UiToggle v-model="selected.is_active" label="Router enabled" :description="selected.is_active ? 'Can be selected as the agent target.' : 'Not used for routing.'" /></div>
          </div>
          <div class="kiwi__metrics">
            <UiMetric label="Agents" :value="selected.members.length" />
            <UiMetric label="Configured capacity" :value="`${totalRpm} RPM`" />
            <UiMetric label="Verified metadata" :value="`${verifiedCount} / ${selected.members.length}`" :tone="selected.members.length && verifiedCount === selected.members.length ? 'success' : 'neutral'" />
          </div>
        </UiCard>

        <UiCard title="Provider agent order" subtitle="Requests reserve capacity from the first eligible agent, then continue down the order.">
          <template #actions>
            <UiButton variant="soft" @click="addMember"><FontAwesomeIcon :icon="faPlus" /> Add agent</UiButton>
          </template>
          <UiEmptyState v-if="!selected.members.length" title="No agents assigned" description="Add a configured General AI Agent to begin." />
          <ol v-else class="kiwi__members">
            <li v-for="(member, index) in selected.members" :key="member.id || `${member.provider_config}-${index}`" class="kiwi__member">
              <div class="kiwi__member-head">
                <span class="kiwi__number" aria-hidden="true">{{ member.priority }}</span>
                <UiFormField class="kiwi__agent" label="Provider agent">
                  <UiSelect v-model="member.provider_config" :options="providerOptions" searchable />
                </UiFormField>
                <UiFormField class="kiwi__source" label="Metadata source">
                  <UiSelect v-model="member.metadata_source" :options="metadataOptions" />
                </UiFormField>
                <div class="kiwi__member-actions">
                  <UiButton size="icon" title="Fetch published limits and prices" aria-label="Fetch published limits and prices" @click="fetchMetadata(member)"><FontAwesomeIcon :icon="faCloudArrowDown" /></UiButton>
                  <UiButton size="icon" title="Move up" aria-label="Move up" :disabled="index === 0" @click="move(index, -1)"><FontAwesomeIcon :icon="faArrowUp" /></UiButton>
                  <UiButton size="icon" title="Move down" aria-label="Move down" :disabled="index === selected.members.length - 1" @click="move(index, 1)"><FontAwesomeIcon :icon="faArrowDown" /></UiButton>
                  <UiButton size="icon" variant="danger" title="Remove from router" aria-label="Remove from router" @click="removeMember(index)"><FontAwesomeIcon :icon="faTrashCan" /></UiButton>
                </div>
              </div>
              <div class="kiwi__limits">
                <UiFormField v-for="field in numberFields" :key="field.key" :label="field.label">
                  <UiInput type="number" :min="field.min" :step="field.step" :placeholder="field.placeholder" :model-value="member[field.key] ?? ''" @update:model-value="member[field.key] = toNumber($event)" />
                </UiFormField>
              </div>
            </li>
          </ol>
          <p class="kiwi__muted kiwi__help">
            <strong>Provider published</strong>: fetched from the provider's API. <strong>Operator supplied</strong>: entered by hand from an official provider plan.
            <strong>Incomplete</strong>: unknown values; suitable only for ordered routing.
          </p>
        </UiCard>
      </div>
      <UiCard v-else class="kiwi__workspace">
        <UiEmptyState title="No router selected" description="Create a KiwiRouter to configure provider capacity and routing order." />
      </UiCard>
    </div>
  </UiPage>
</template>

<style scoped>
.kiwi { display:grid; grid-template-columns:minmax(15rem,18rem) minmax(0,1fr); gap:1rem; align-items:start; }
.kiwi__workspace { display:grid; gap:1rem; min-width:0; }
.kiwi :deep(.ui-card__header > div:last-child) { display:flex; flex-wrap:wrap; gap:.5rem; }
.kiwi__muted { margin:.75rem 0 0; color:var(--ui-text-muted); font-size:.85rem; }
.kiwi__new { display:grid; gap:.6rem; margin-bottom:.75rem; padding:.75rem; border-radius:var(--ui-radius-sm); background:var(--ui-surface-muted); }
.kiwi__new .ui-button { justify-self:start; }
.kiwi__list { display:grid; gap:.25rem; }
.kiwi__router { display:grid; gap:.2rem; width:100%; padding:.65rem .75rem; border:1px solid transparent; border-radius:var(--ui-radius-sm); background:transparent; color:var(--ui-text); text-align:left; cursor:pointer; }
.kiwi__router:hover { background:var(--ui-surface-muted); }
.kiwi__router.is-selected { border-color:color-mix(in srgb, var(--ui-primary) 30%, transparent); background:var(--ui-primary-soft); }
.kiwi__router-name { display:flex; align-items:center; justify-content:space-between; gap:.5rem; }
.kiwi__router small { color:var(--ui-text-muted); }
.kiwi__settings { display:grid; grid-template-columns:minmax(0,1fr) minmax(0,1fr) auto; gap:1rem; align-items:start; }
.kiwi__toggle { padding-top:1.4rem; }
.kiwi__metrics { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:.75rem; margin-top:1rem; }
.kiwi__members { display:grid; gap:.75rem; margin:0; padding:0; list-style:none; }
.kiwi__member { display:grid; gap:.75rem; padding:.9rem; border:1px solid var(--ui-border); border-radius:var(--ui-radius-md); background:var(--ui-surface); }
.kiwi__member-head { display:grid; grid-template-columns:auto minmax(0,2fr) minmax(10rem,1fr) auto; gap:.75rem; align-items:end; }
.kiwi__number { display:grid; place-items:center; width:1.9rem; height:1.9rem; margin-bottom:.2rem; border-radius:50%; background:var(--ui-primary); color:var(--ui-on-primary); font-weight:800; }
.kiwi__member-actions { display:flex; gap:.35rem; }
.kiwi__limits { display:grid; grid-template-columns:repeat(auto-fit,minmax(8.5rem,1fr)); gap:.75rem; padding-left:2.65rem; }
.kiwi__help { line-height:1.5; }
@media (max-width: 1100px) {
  .kiwi { grid-template-columns:1fr; }
  .kiwi__settings { grid-template-columns:1fr 1fr; }
  .kiwi__toggle { grid-column:1 / -1; padding-top:0; }
}
@media (max-width: 760px) {
  .kiwi__settings, .kiwi__metrics { grid-template-columns:1fr; }
  .kiwi__member-head { grid-template-columns:auto minmax(0,1fr); }
  .kiwi__source, .kiwi__member-actions { grid-column:2; }
  .kiwi__limits { padding-left:0; grid-template-columns:repeat(2,minmax(0,1fr)); }
}
</style>
