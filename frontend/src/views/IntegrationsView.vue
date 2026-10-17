<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { integrationsApi } from '@/api'
import UiBadge from '@/components/ui/UiBadge.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiCard from '@/components/ui/UiCard.vue'
import UiDataTable from '@/components/ui/UiDataTable.vue'
import UiFormField from '@/components/ui/UiFormField.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiMetric from '@/components/ui/UiMetric.vue'
import UiNotice from '@/components/ui/UiNotice.vue'
import UiPage from '@/components/ui/UiPage.vue'
import UiPageHeader from '@/components/ui/UiPageHeader.vue'
import UiSelect from '@/components/ui/UiSelect.vue'
import UiToggle from '@/components/ui/UiToggle.vue'

const overview = ref(null)
const username = ref('')
const enabled = ref(true)
const countryCode = ref('AE')
const level = ref('city')
const rows = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(25)
const search = ref('')
const loading = ref(false)
const tableLoading = ref(false)
const action = ref('')
const notice = ref(null)
let pollTimer

const levelOptions = [
  { value: 'country', label: 'Countries' },
  { value: 'area', label: 'States / administrative areas' },
  { value: 'city', label: 'Cities' },
  { value: 'locality', label: 'Localities / communities' },
]
const countryOptions = [{ value: 'AE', label: 'United Arab Emirates (AE)' }]
const locationColumns = computed(() => {
  const common = [
    { key: 'name', label: 'Name', sortable: false },
    { key: 'country_code', label: 'Country' },
  ]
  if (['city', 'locality'].includes(level.value)) common.push({ key: 'administrative_area_name', label: 'Administrative area' })
  if (level.value === 'locality') common.push(
    { key: 'city_name', label: 'City' },
    { key: 'mapping_status', label: 'Mapping' },
  )
  if (level.value === 'area') common.push({ key: 'code', label: 'Code' })
  return [
    ...common,
    { key: 'latitude', label: 'Latitude' },
    { key: 'longitude', label: 'Longitude' },
    ...(['city', 'locality'].includes(level.value) ? [{ key: 'population', label: 'Population' }, { key: 'timezone', label: 'Timezone' }] : []),
  ]
})
const runColumns = [
  { key: 'created_at', label: 'Requested' },
  { key: 'country_code', label: 'Country' },
  { key: 'status', label: 'Status' },
  { key: 'result', label: 'Result' },
]
const runRows = computed(() => (overview.value?.runs || []).map(run => ({
  ...run,
  created_at: formatDate(run.created_at),
  result: run.error || summarizeCounters(run.counters),
})))
const hasActiveRun = computed(() => (overview.value?.runs || []).some(run => ['pending', 'running'].includes(run.status)))

function errorMessage(error, fallback) {
  const data = error.response?.data
  if (typeof data?.detail === 'string') return data.detail
  if (data && typeof data === 'object') return Object.values(data).flat().join(' ')
  return fallback
}
function formatDate(value) {
  return value ? new Intl.DateTimeFormat(undefined, { dateStyle: 'short', timeStyle: 'short' }).format(new Date(value)) : '-'
}
function summarizeCounters(counters) {
  if (!counters || !Object.keys(counters).length) return '-'
  return `${counters.administrative_areas_total || 0} areas, ${counters.cities_total || 0} cities, ${counters.localities_total || 0} localities`
}
function statusTone(status) {
  return status === 'succeeded' || status === 'ready' ? 'success' : status === 'failed' || status === 'error' ? 'danger' : 'warning'
}
function showNotice(tone, message) { notice.value = { tone, message } }

async function loadOverview(silent = false) {
  if (!silent) loading.value = true
  try {
    const { data } = await integrationsApi.overview()
    overview.value = data
    username.value = data.geonames?.username || ''
    enabled.value = data.geonames?.is_enabled ?? true
  } catch (error) {
    showNotice('danger', errorMessage(error, 'Unable to load integrations.'))
  } finally { loading.value = false }
}
async function loadLocations() {
  tableLoading.value = true
  try {
    const { data } = await integrationsApi.locations({
      level: level.value, country_code: countryCode.value,
      page: page.value, page_size: pageSize.value, search: search.value,
    })
    rows.value = data.results
    total.value = data.count
  } catch (error) {
    showNotice('danger', errorMessage(error, 'Unable to load geography records.'))
  } finally { tableLoading.value = false }
}
async function saveSource() {
  action.value = 'save'; notice.value = null
  try {
    await integrationsApi.saveGeographySource({ username: username.value, is_enabled: enabled.value })
    await loadOverview(true)
    showNotice('success', 'GeoNames configuration saved. Test it before synchronizing geography.')
  } catch (error) { showNotice('danger', errorMessage(error, 'Unable to save GeoNames configuration.')) }
  finally { action.value = '' }
}
async function testSource() {
  action.value = 'test'; notice.value = null
  try {
    const { data } = await integrationsApi.testGeographySource()
    await loadOverview(true)
    showNotice('success', `Connection verified for ${data.sample.country} (${data.sample.iso2}).`)
  } catch (error) { showNotice('danger', errorMessage(error, 'GeoNames connection test failed.')) }
  finally { action.value = '' }
}
async function startSync() {
  action.value = 'sync'; notice.value = null
  try {
    const { data } = await integrationsApi.syncGeography(countryCode.value)
    await loadOverview(true)
    showNotice('success', `Geography sync queued as task #${data.background_task_id}.`)
  } catch (error) { showNotice('danger', errorMessage(error, 'Unable to queue geography sync.')) }
  finally { action.value = '' }
}

watch([level, countryCode, page, pageSize, search], () => loadLocations())
watch([level, countryCode, pageSize, search], () => { page.value = 1 })
onMounted(async () => {
  await Promise.all([loadOverview(), loadLocations()])
  pollTimer = window.setInterval(async () => {
    if (!hasActiveRun.value) return
    await loadOverview(true)
    if (!hasActiveRun.value) await loadLocations()
  }, 5000)
})
onBeforeUnmount(() => window.clearInterval(pollTimer))
</script>

<template>
  <UiPage width="wide">
    <UiPageHeader eyebrow="External services" title="Integrations" description="Connect external providers and maintain trusted shared reference data without coupling provider APIs to domain records." />
    <UiNotice v-if="notice" :tone="notice.tone">{{ notice.message }}</UiNotice>

    <section class="integration-metrics">
      <UiMetric label="Countries" :value="overview?.geography.countries || 0" hint="Active master records" tone="success" />
      <UiMetric label="States / areas" :value="overview?.geography.administrative_areas || 0" hint="Administrative level 1" />
      <UiMetric label="Cities" :value="overview?.geography.cities || 0" hint="Administrative city anchors" />
      <UiMetric label="Localities" :value="overview?.geography.localities || 0" :hint="`${overview?.geography.unmapped_localities || 0} awaiting city mapping`" />
    </section>

    <div class="integration-grid">
      <UiCard title="GeoNames geography" subtitle="Canonical country, state, city, and locality source. Platform-managed and shared by every company.">
        <div v-if="loading" class="integration-state">Loading configuration...</div>
        <template v-else>
          <UiFormField label="GeoNames username" hint="Use a GeoNames account username, not an email address or password.">
            <UiInput v-model="username" :disabled="!overview?.can_manage_platform" placeholder="GeoNames username" autocomplete="off" />
          </UiFormField>
          <UiToggle v-model="enabled" label="Enable geography source" description="Disabling blocks new sync runs but preserves existing master data." :disabled="!overview?.can_manage_platform" />
          <div class="integration-status">
            <UiBadge :tone="statusTone(overview?.geonames?.status)">{{ overview?.geonames?.status || 'not configured' }}</UiBadge>
            <span>Last sync: {{ formatDate(overview?.geonames?.last_successful_sync_at) }}</span>
          </div>
          <p v-if="overview?.geonames?.last_error" class="integration-error">{{ overview.geonames.last_error }}</p>
          <div class="integration-actions">
            <UiButton variant="secondary" :disabled="!overview?.can_manage_platform || !!action" @click="saveSource">{{ action === 'save' ? 'Saving...' : 'Save' }}</UiButton>
            <UiButton variant="secondary" :disabled="!overview?.can_manage_platform || !overview?.geonames || !!action" @click="testSource">{{ action === 'test' ? 'Testing...' : 'Test connection' }}</UiButton>
          </div>
        </template>
      </UiCard>

      <UiCard title="Geography synchronization" subtitle="Start with UAE, then add another ISO country code when regional expansion is required.">
        <UiFormField label="Country">
          <UiSelect v-model="countryCode" :options="countryOptions" />
        </UiFormField>
        <UiNotice tone="info">Sync runs in the durable <strong>integrations</strong> queue. Existing records are updated in place; missing source records are deactivated, not deleted.</UiNotice>
        <div class="integration-actions">
          <UiButton variant="primary" :disabled="!overview?.can_manage_platform || !overview?.geonames?.is_enabled || !!action || hasActiveRun" @click="startSync">{{ action === 'sync' ? 'Queueing...' : hasActiveRun ? 'Sync in progress' : 'Sync UAE geography' }}</UiButton>
        </div>
      </UiCard>
    </div>

    <UiCard title="Geography master" subtitle="Browse the normalized reference records available to property forms and matching.">
      <UiDataTable v-model:page="page" v-model:page-size="pageSize" v-model:search="search" :columns="locationColumns" :rows="rows" :total="total" :loading="tableLoading" row-key="id" persist-key="integration-geography" search-placeholder="Search geography..." empty-title="No geography records have been synchronized." @refresh="loadLocations">
        <template #filters><UiSelect v-model="level" :options="levelOptions" /></template>
      </UiDataTable>
    </UiCard>

    <UiCard title="Recent synchronization runs" subtitle="Durable task feedback for geography imports.">
      <UiDataTable :columns="runColumns" :rows="runRows" :total="runRows.length" :page-size="10" row-key="id" persist-key="integration-runs" search-placeholder="Search runs..." empty-title="No geography sync has been requested." @refresh="loadOverview">
        <template #cell-status="{ value }"><UiBadge :tone="statusTone(value)">{{ value }}</UiBadge></template>
      </UiDataTable>
    </UiCard>
  </UiPage>
</template>

<style scoped>
.integration-metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:var(--ui-gap-md);margin-bottom:var(--ui-gap-lg)}
.integration-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:var(--ui-gap-lg);margin-bottom:var(--ui-gap-lg)}
.integration-grid :deep(.ui-card){height:100%}.integration-grid :deep(.ui-card__body){display:flex;flex-direction:column;gap:18px}
.integration-actions{display:flex;flex-wrap:wrap;gap:10px;margin-top:auto}.integration-status{display:flex;align-items:center;gap:12px;color:var(--ui-text-muted);font-size:.86rem}
.integration-error{margin:0;color:var(--ui-danger);font-size:.86rem}.integration-state{padding:24px;text-align:center;color:var(--ui-text-muted)}
:deep(.ui-card){margin-bottom:var(--ui-gap-lg)}
@media(max-width:800px){.integration-metrics,.integration-grid{grid-template-columns:1fr}}
</style>
