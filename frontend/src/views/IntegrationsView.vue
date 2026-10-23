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
import UiModal from '@/components/ui/UiModal.vue'
import UiNotice from '@/components/ui/UiNotice.vue'
import UiPage from '@/components/ui/UiPage.vue'
import UiPageHeader from '@/components/ui/UiPageHeader.vue'
import UiSelect from '@/components/ui/UiSelect.vue'
import UiTabs from '@/components/ui/UiTabs.vue'
import UiToggle from '@/components/ui/UiToggle.vue'

const overview = ref(null)
const providerTab = ref('geonames')
const username = ref('')
const enabled = ref(true)
const googleEnabled = ref(false)
const googleApiKey = ref('')
const googleBrowserApiKey = ref('')
const googleMonthlyLimit = ref(100)
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
const googleAction = ref('')
const notice = ref(null)
const resolverOpen = ref(false)
const resolverLocality = ref(null)
const resolverQuery = ref('')
const resolverResults = ref([])
const resolverPlaceId = ref('')
const resolverSessionToken = ref('')
const resolverCityId = ref('')
const resolverCities = ref([])
let pollTimer

const providerTabs = [
  { value: 'geonames', label: 'GeoNames' },
  { value: 'google_maps', label: 'Google Maps' },
]
const levelOptions = [
  { value: 'country', label: 'Countries' },
  { value: 'area', label: 'States / administrative areas' },
  { value: 'city', label: 'Cities' },
  { value: 'locality', label: 'Localities / communities' },
]
const countryOptions = [
  { value: 'AE', label: 'United Arab Emirates (AE)' },
  { value: 'SA', label: 'Saudi Arabia (SA)' },
  { value: 'QA', label: 'Qatar (QA)' },
  { value: 'KW', label: 'Kuwait (KW)' },
  { value: 'BH', label: 'Bahrain (BH)' },
  { value: 'OM', label: 'Oman (OM)' },
]
const selectedCountry = computed(() => (
  countryOptions.find(option => option.value === countryCode.value) || countryOptions[0]
))
const locationColumns = computed(() => {
  const common = [
    { key: 'name', label: 'Name', sortable: false },
    { key: 'country_code', label: 'Country' },
  ]
  if (['city', 'locality'].includes(level.value)) common.push({ key: 'administrative_area_name', label: 'Administrative area' })
  if (level.value === 'locality') {
    common.push(
      { key: 'city_name', label: 'City' },
      { key: 'mapping_status', label: 'Mapping' },
    )
    if (providerTab.value === 'google_maps') common.push(
      { key: 'google_reference', label: 'Google Maps' },
      { key: 'actions', label: '', exportable: false },
    )
  }
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
  if (error.response?.status === 404) {
    return 'The integration API endpoint is not available in the currently running backend process.'
  }
  if (error.response?.status === 405) {
    return 'The currently running backend does not accept this request method.'
  }
  if (typeof data === 'string' && data.trim()) {
    const contentType = error.response?.headers?.['content-type'] || ''
    if (!contentType.includes('text/html')) return data.trim().slice(0, 300)
  }
  if (error.response?.status) return `${fallback} HTTP ${error.response.status}.`
  if (error.message) return `${fallback} ${error.message}`
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
    googleEnabled.value = data.google_maps?.is_enabled ?? false
    googleApiKey.value = ''
    googleBrowserApiKey.value = ''
    googleMonthlyLimit.value = data.google_maps?.usage?.monthly_request_limit || 100
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

async function saveGoogleMaps() {
  if (!overview.value?.google_maps?.api_key_configured && !googleApiKey.value.trim()) {
    showNotice('danger', 'Enter a Google Maps API key before saving the configuration.')
    return
  }
  googleAction.value = 'save'; notice.value = null
  try {
    const payload = {
      monthly_request_limit: googleMonthlyLimit.value,
      is_enabled: googleEnabled.value,
    }
    if (googleApiKey.value) payload.api_key = googleApiKey.value
    if (googleBrowserApiKey.value) payload.browser_api_key = googleBrowserApiKey.value
    await integrationsApi.saveGoogleMaps(payload)
    googleApiKey.value = ''
    googleBrowserApiKey.value = ''
    await loadOverview(true)
    showNotice('success', 'Google Maps API configuration saved. Test the connection before resolving localities.')
  } catch (error) { showNotice('danger', errorMessage(error, 'Unable to save Google Maps configuration.')) }
  finally { googleAction.value = '' }
}
async function testGoogleMaps() {
  googleAction.value = 'test'; notice.value = null
  try {
    await integrationsApi.testGoogleMaps()
    await loadOverview(true)
    showNotice('success', 'Google Maps Places connection verified.')
  } catch (error) { showNotice('danger', errorMessage(error, 'Google Maps connection test failed.')) }
  finally { googleAction.value = '' }
}
async function openResolver(locality) {
  resolverLocality.value = locality
  resolverQuery.value = [locality.name, locality.administrative_area_name, locality.country_code].filter(Boolean).join(', ')
  resolverResults.value = []
  resolverPlaceId.value = ''
  resolverSessionToken.value = ''
  resolverCityId.value = ''
  resolverCities.value = []
  resolverOpen.value = true
  try {
    const { data } = await integrationsApi.locations({
      level: 'city', country_code: locality.country_code,
      area_id: locality.administrative_area_id, page_size: 3000,
    })
    resolverCities.value = data.results.map(city => ({ value: city.id, label: city.name }))
  } catch (error) { showNotice('danger', errorMessage(error, 'Unable to load city options.')) }
}
async function findGoogleMatches() {
  googleAction.value = 'suggest'; notice.value = null
  try {
    const { data } = await integrationsApi.googleLocalitySuggestions(
      resolverLocality.value.id, { query: resolverQuery.value },
    )
    resolverResults.value = data.results
    resolverSessionToken.value = data.session_token
    resolverPlaceId.value = data.results[0]?.place_id || ''
    await loadOverview(true)
    if (!data.results.length) showNotice('warning', 'Google Maps returned no matching places.')
  } catch (error) { showNotice('danger', errorMessage(error, 'Unable to search Google Maps.')) }
  finally { googleAction.value = '' }
}
async function confirmGoogleMatch() {
  googleAction.value = 'resolve'; notice.value = null
  try {
    await integrationsApi.resolveGoogleLocality(resolverLocality.value.id, {
      place_id: resolverPlaceId.value,
      session_token: resolverSessionToken.value,
      city_id: resolverCityId.value,
    })
    resolverOpen.value = false
    await Promise.all([loadOverview(true), loadLocations()])
    showNotice('success', 'Google place verified and locality mapped to the selected city.')
  } catch (error) { showNotice('danger', errorMessage(error, 'Unable to verify this locality.')) }
  finally { googleAction.value = '' }
}

watch([level, countryCode, page, pageSize, search], () => loadLocations())
watch([level, countryCode, pageSize, search], () => { page.value = 1 })
watch(providerTab, value => {
  if (value === 'google_maps') level.value = 'locality'
})
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

    <nav class="provider-tabs" aria-label="Integration providers">
      <UiTabs v-model="providerTab" :tabs="providerTabs" />
    </nav>

    <section v-if="providerTab === 'geonames'" class="provider-panel">
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

        <UiCard title="Geography synchronization" subtitle="Synchronize canonical geography for the six Gulf Cooperation Council countries.">
          <UiFormField label="Country">
            <UiSelect v-model="countryCode" :options="countryOptions" />
          </UiFormField>
          <UiNotice tone="info">Sync runs in the durable <strong>integrations</strong> queue. Existing records are updated in place; missing source records are deactivated, not deleted.</UiNotice>
          <div class="integration-actions">
            <UiButton variant="primary" :disabled="!overview?.can_manage_platform || !overview?.geonames?.is_enabled || !!action || hasActiveRun" @click="startSync">{{ action === 'sync' ? 'Queueing...' : hasActiveRun ? 'Sync in progress' : `Sync ${selectedCountry.label} geography` }}</UiButton>
          </div>
        </UiCard>
      </div>

      <UiCard title="Geography master" subtitle="Browse the canonical records imported from GeoNames for property forms and matching.">
        <UiDataTable v-model:page="page" v-model:page-size="pageSize" v-model:search="search" :columns="locationColumns" :rows="rows" :total="total" :loading="tableLoading" row-key="id" persist-key="integration-geography" search-placeholder="Search geography..." empty-title="No geography records have been synchronized." @refresh="loadLocations">
          <template #filters><UiSelect v-model="level" :options="levelOptions" /></template>
          <template #cell-mapping_status="{ value }"><UiBadge :tone="value === 'mapped' ? 'success' : 'warning'">{{ value }}</UiBadge></template>
        </UiDataTable>
      </UiCard>

      <UiCard title="Recent synchronization runs" subtitle="Durable task feedback for GeoNames geography imports.">
        <UiDataTable :columns="runColumns" :rows="runRows" :total="runRows.length" :page-size="10" row-key="id" persist-key="integration-runs" search-placeholder="Search runs..." empty-title="No geography sync has been requested." @refresh="loadOverview">
          <template #cell-status="{ value }"><UiBadge :tone="statusTone(value)">{{ value }}</UiBadge></template>
        </UiDataTable>
      </UiCard>
    </section>

    <section v-else class="provider-panel">
      <UiCard title="Google Maps APIs configuration" subtitle="Configure Places, reverse geocoding, and interactive maps. GeoNames remains the canonical source.">
        <div class="google-config">
          <UiFormField label="Server Google Maps API key" :hint="overview?.google_maps?.api_key_configured ? `Configured: ${overview.google_maps.api_key_masked}. Leave blank to keep it.` : 'Enter a server-restricted key with Places API (New) and Geocoding API enabled.'">
            <UiInput v-model="googleApiKey" type="password" :disabled="!overview?.can_manage_platform" placeholder="Enter API key" autocomplete="new-password" />
          </UiFormField>
          <UiFormField label="Browser map API key" :hint="overview?.google_maps?.browser_api_key_configured ? `Configured: ${overview.google_maps.browser_api_key_masked}. Leave blank to keep it.` : 'Use a separate HTTP-referrer-restricted key with Maps JavaScript API enabled.'">
            <UiInput v-model="googleBrowserApiKey" type="password" :disabled="!overview?.can_manage_platform" placeholder="Enter browser map key" autocomplete="new-password" />
          </UiFormField>
          <UiFormField label="Monthly request cap" hint="Hard application cap across autocomplete and place-detail requests.">
            <UiInput v-model="googleMonthlyLimit" type="number" min="1" max="100000" :disabled="!overview?.can_manage_platform" />
          </UiFormField>
          <div class="google-toggle-panel">
            <UiToggle v-model="googleEnabled" label="Enable Google Maps verification" description="No automatic or bulk Google requests are made." :disabled="!overview?.can_manage_platform" />
          </div>
        </div>
        <div class="google-config-footer">
          <div class="integration-status">
            <UiBadge :tone="statusTone(overview?.google_maps?.status)">{{ overview?.google_maps?.status || 'not configured' }}</UiBadge>
            <span>{{ overview?.google_maps?.api_key_configured ? 'API key configured' : 'API key required' }}</span>
            <span>{{ overview?.google_maps?.browser_api_key_configured ? 'Interactive map configured' : 'Interactive map key required' }}</span>
            <span>{{ overview?.google_maps?.usage?.request_count || 0 }} / {{ overview?.google_maps?.usage?.monthly_request_limit || googleMonthlyLimit }} requests this month</span>
          </div>
          <div class="integration-actions google-config-actions">
            <UiButton variant="secondary" :disabled="!overview?.can_manage_platform || !!googleAction" @click="saveGoogleMaps">{{ googleAction === 'save' ? 'Saving...' : 'Save Google Maps' }}</UiButton>
            <UiButton variant="secondary" :disabled="!overview?.can_manage_platform || !overview?.google_maps?.is_enabled || !overview?.google_maps?.api_key_configured || !!googleAction" @click="testGoogleMaps">{{ googleAction === 'test' ? 'Testing...' : 'Test connection' }}</UiButton>
          </div>
        </div>
        <p v-if="overview?.google_maps?.last_error" class="integration-error">{{ overview.google_maps.last_error }}</p>
      </UiCard>

      <UiCard title="Google Maps locality verification" subtitle="Review canonical localities, find Google place candidates, and approve their internal city mapping.">
        <UiDataTable v-model:page="page" v-model:page-size="pageSize" v-model:search="search" :columns="locationColumns" :rows="rows" :total="total" :loading="tableLoading" row-key="id" persist-key="integration-google-localities" search-placeholder="Search localities..." empty-title="No localities are available for verification." @refresh="loadLocations">
          <template #cell-mapping_status="{ value }"><UiBadge :tone="value === 'mapped' ? 'success' : 'warning'">{{ value }}</UiBadge></template>
          <template #cell-google_reference="{ value }"><UiBadge :tone="value?.status === 'verified' ? 'success' : 'neutral'">{{ value?.status || 'not verified' }}</UiBadge></template>
          <template #cell-actions="{ row }"><UiButton size="small" variant="secondary" :disabled="!overview?.can_manage_platform || !overview?.google_maps?.is_enabled" @click.stop="openResolver(row)">{{ row.google_reference ? 'Review' : 'Resolve' }}</UiButton></template>
        </UiDataTable>
      </UiCard>
    </section>

    <UiModal :open="resolverOpen" title="Verify locality with Google Maps" :subtitle="resolverLocality ? `${resolverLocality.name}, ${resolverLocality.administrative_area_name}` : ''" size="large" tall @close="resolverOpen = false">
      <div class="resolver-form">
        <UiFormField label="Google Maps search"><div class="resolver-search"><UiInput v-model="resolverQuery" /><UiButton :disabled="!resolverQuery || !!googleAction" @click="findGoogleMatches">{{ googleAction === 'suggest' ? 'Searching...' : 'Find matches' }}</UiButton></div></UiFormField>
        <UiNotice tone="info">Results are temporary. Only the selected Google place ID and its approved internal city link are stored.</UiNotice>
        <div v-if="resolverResults.length" class="resolver-results">
          <label v-for="result in resolverResults" :key="result.place_id" :class="{ selected: resolverPlaceId === result.place_id }">
            <input v-model="resolverPlaceId" type="radio" :value="result.place_id">
            <span><strong>{{ result.main_text || result.text }}</strong><small>{{ result.secondary_text }}</small></span>
          </label>
        </div>
        <UiFormField label="Canonical ChatLens city" hint="An operator must approve the internal city; Google never rewrites canonical names.">
          <UiSelect v-model="resolverCityId" :options="resolverCities" placeholder="Select city" searchable />
        </UiFormField>
      </div>
      <template #footer><UiButton variant="secondary" @click="resolverOpen = false">Cancel</UiButton><UiButton :disabled="!resolverPlaceId || !resolverCityId || !!googleAction" @click="confirmGoogleMatch">{{ googleAction === 'resolve' ? 'Verifying...' : 'Verify and map' }}</UiButton></template>
    </UiModal>
  </UiPage>
</template>

<style scoped>
.integration-metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:var(--ui-gap-md);margin-bottom:var(--ui-gap-lg)}
.provider-tabs{padding:5px 12px 0;border:1px solid var(--ui-border);border-radius:var(--ui-radius-lg);background:var(--ui-surface);box-shadow:var(--ui-shadow-card)}
.provider-tabs :deep(.ui-tabs){gap:8px;border-bottom:0}.provider-tabs :deep(.ui-tabs>button){padding:11px 16px;font-size:.82rem}
.provider-panel{display:grid;gap:var(--ui-gap-lg);margin-top:var(--ui-gap-md)}
.provider-panel :deep(.ui-card){margin:0}
.integration-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:var(--ui-gap-lg)}
.integration-grid :deep(.ui-card){height:100%}.integration-grid :deep(.ui-card__body){display:flex;flex-direction:column;gap:18px}
.integration-actions{display:flex;flex-wrap:wrap;gap:10px;margin-top:auto}.integration-status{display:flex;align-items:center;gap:12px;color:var(--ui-text-muted);font-size:.86rem}
.integration-error{margin:0;color:var(--ui-danger);font-size:.86rem}.integration-state{padding:24px;text-align:center;color:var(--ui-text-muted)}
.google-config{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:var(--ui-gap-lg);align-items:start}
.google-toggle-panel{display:flex;min-height:72px;align-items:center;padding:12px 14px;border:1px solid var(--ui-border);border-radius:var(--ui-radius-md);background:var(--ui-surface-muted)}
.google-config-footer{display:flex;align-items:center;justify-content:space-between;gap:18px;margin-top:18px;padding-top:16px;border-top:1px solid var(--ui-border)}
.google-config-actions{flex:none;margin:0}.resolver-form{display:grid;gap:18px}.resolver-search{display:grid;grid-template-columns:1fr auto;gap:10px}.resolver-results{display:grid;gap:8px}.resolver-results label{display:flex;gap:12px;padding:14px;border:1px solid var(--ui-border);border-radius:var(--ui-radius-md);cursor:pointer}.resolver-results label.selected{border-color:var(--ui-primary);background:var(--ui-primary-soft)}.resolver-results span{display:grid;gap:3px}.resolver-results small{color:var(--ui-text-muted)}
@media(max-width:1050px){.google-config{grid-template-columns:1fr 1fr}.google-toggle-panel{grid-column:1/-1}.google-config-footer{align-items:flex-start;flex-direction:column}}
@media(max-width:800px){.integration-metrics,.integration-grid,.google-config{grid-template-columns:1fr}.google-toggle-panel{grid-column:auto}.google-config-actions{width:100%}.resolver-search{grid-template-columns:1fr}}
</style>
