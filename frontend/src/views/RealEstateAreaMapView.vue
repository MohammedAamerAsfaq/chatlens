<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { FontAwesomeIcon } from '@fortawesome/vue-fontawesome'
import { faLocationDot, faRotate } from '@fortawesome/free-solid-svg-icons'
import { realEstateApi } from '@/api'
import UiButton from '@/components/ui/UiButton.vue'
import UiCard from '@/components/ui/UiCard.vue'
import UiDatePicker from '@/components/ui/UiDatePicker.vue'
import UiEmptyState from '@/components/ui/UiEmptyState.vue'
import UiNotice from '@/components/ui/UiNotice.vue'
import UiPage from '@/components/ui/UiPage.vue'
import UiPageHeader from '@/components/ui/UiPageHeader.vue'
import UiSelect from '@/components/ui/UiSelect.vue'
import UiTabs from '@/components/ui/UiTabs.vue'
import { apiError } from '@/features/realEstate/apiErrors'
import { opportunityLanes, statusFilters } from '@/features/realEstate/boardOptions'
import { loadGoogleMaps } from '@/features/realEstate/googleMapsLoader'

// Same colours as the board lanes.
const ACTIVITY_COLORS = { buying: '#238b75', selling: '#d4862c', leasing_inquiry: '#3b72c4', leasing_offer: '#a25f83' }
const ALL_COLOR = '#2563eb'
const STATUS_TEXT = {
  pending: 'Not looked up on Google yet',
  not_found: 'Not found',
  error: 'Google lookup failed',
}

const tabs = [{ value: 'all', label: 'All' }, ...opportunityLanes.map(lane => ({ value: lane.key, label: lane.label }))]
const laneLabels = Object.fromEntries(opportunityLanes.map(lane => [lane.key, lane.label]))
const activity = ref('all')
const status = ref('')
const dateFrom = ref('')
const dateTo = ref('')
const report = ref(null)
const loading = ref(false)
const placing = ref(false)
const error = ref('')
const notice = ref('')
const mapError = ref('')
const mapElement = ref(null)
const selectedKey = ref('')

let map = null
let infoWindow = null
let markers = new Map()

const areas = computed(() => report.value?.areas || [])
const placed = computed(() => areas.value.filter(area => area.status === 'placed'))
const unplaced = computed(() => areas.value.filter(area => area.status !== 'placed'))
const maxCount = computed(() => Math.max(1, ...areas.value.map(area => area.count)))
const located = computed(() => (report.value ? report.value.total_opportunities - report.value.without_location : 0))
const google = computed(() => report.value?.google || null)

function params() {
  const value = { activity_type: activity.value }
  if (status.value) value.status = status.value
  if (dateFrom.value) value.date_from = dateFrom.value.slice(0, 10)
  if (dateTo.value) value.date_to = dateTo.value.slice(0, 10)
  return value
}

let loadSeq = 0
async function load() {
  const seq = ++loadSeq
  loading.value = true; error.value = ''; notice.value = ''
  try {
    const { data } = await realEstateApi.areaMap(params())
    if (seq !== loadSeq) return
    report.value = data
    await drawMap()
  } catch (exc) {
    if (seq !== loadSeq) return
    error.value = apiError(exc, 'Unable to load the area map.')
  } finally {
    if (seq === loadSeq) loading.value = false
  }
}

async function placeOnGoogle() {
  placing.value = true; error.value = ''; notice.value = ''
  try {
    const { data } = await realEstateApi.placeAreas(params())
    report.value = data
    notice.value = data.notice || ''
    await drawMap()
  } catch (exc) {
    error.value = apiError(exc, 'Unable to look up the areas on Google Maps.')
  } finally {
    placing.value = false
  }
}

function colorFor(area) {
  if (activity.value !== 'all') return ACTIVITY_COLORS[activity.value] || ALL_COLOR
  const [top] = Object.entries(area.by_activity).sort((a, b) => b[1] - a[1])
  return (top && ACTIVITY_COLORS[top[0]]) || ALL_COLOR
}

function share(area) {
  return located.value ? Math.round((area.count / located.value) * 100) : 0
}

function breakdown(area) {
  return Object.entries(area.by_activity)
    .sort((a, b) => b[1] - a[1])
    .map(([key, count]) => `${laneLabels[key] || key}: ${count}`)
    .join(' · ')
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]))
}

async function drawMap() {
  mapError.value = ''
  if (!report.value) return
  if (!report.value.browser_api_key) {
    mapError.value = report.value.map_error
    return
  }
  try {
    const maps = await loadGoogleMaps(report.value.browser_api_key)
    await nextTick()
    if (!mapElement.value) return
    if (!map) {
      const { latitude, longitude } = report.value.country
      map = new maps.Map(mapElement.value, {
        center: { lat: latitude ?? 25.2, lng: longitude ?? 55.27 }, zoom: 9,
        mapTypeControl: false, streetViewControl: false, fullscreenControl: true,
      })
      infoWindow = new maps.InfoWindow()
    }
    markers.forEach(marker => marker.setMap(null))
    markers = new Map()
    const bounds = new maps.LatLngBounds()
    for (const area of placed.value) {
      const position = { lat: area.latitude, lng: area.longitude }
      // Area grows with the number of inquiries, so the busiest areas stand out.
      const scale = 9 + 25 * Math.sqrt(area.count / maxCount.value)
      const marker = new maps.Marker({
        map, position, title: `${area.name}: ${area.count}`, zIndex: area.count,
        icon: { path: maps.SymbolPath.CIRCLE, scale, fillColor: colorFor(area), fillOpacity: 0.72, strokeColor: '#fff', strokeWeight: 2 },
        label: { text: String(area.count), color: '#fff', fontSize: '13px', fontWeight: '700' },
      })
      marker.addListener('click', () => openArea(area, false))
      markers.set(area.key, marker)
      bounds.extend(position)
    }
    if (placed.value.length > 1) map.fitBounds(bounds, 48)
    else if (placed.value.length === 1) { map.setCenter(bounds.getCenter()); map.setZoom(13) }
  } catch (exc) {
    mapError.value = exc.message || 'The map could not be loaded.'
  }
}

function openArea(area, pan = true) {
  selectedKey.value = area.key
  const marker = markers.get(area.key)
  if (!marker || !map) return
  if (pan) { map.panTo(marker.getPosition()); if (map.getZoom() < 12) map.setZoom(12) }
  infoWindow.setContent(
    `<div class="area-map__info"><strong>${escapeHtml(area.name)}</strong>`
    + `<div>${area.count} inquir${area.count === 1 ? 'y' : 'ies'} (${share(area)}%)</div>`
    + `<div>${escapeHtml(breakdown(area))}</div>`
    + (area.matched_label ? `<small>Placed at ${escapeHtml(area.matched_label)}</small>` : '')
    + '</div>',
  )
  infoWindow.open({ map, anchor: marker })
}

watch([activity, status, dateFrom, dateTo], load)
onMounted(load)
onBeforeUnmount(() => {
  markers.forEach(marker => marker.setMap(null))
  markers = new Map()
  map = null
})
</script>

<template>
  <UiPage width="wide">
    <UiPageHeader eyebrow="Real Estate Intelligence" title="Area Map" description="Where inquiries are coming from: every area mentioned in an inquiry, sized by how many inquiries mention it." />
    <UiCard class="area-map__filters">
      <UiTabs v-model="activity" :tabs="tabs" />
      <div class="area-map__controls">
        <UiSelect v-model="status" :options="statusFilters" />
        <UiDatePicker v-model="dateFrom" placeholder="From date" />
        <UiDatePicker v-model="dateTo" placeholder="To date" />
        <UiButton variant="outline" :disabled="loading" @click="load"><FontAwesomeIcon :icon="faRotate" /> Refresh</UiButton>
      </div>
    </UiCard>

    <UiNotice v-if="error" tone="danger">{{ error }}</UiNotice>
    <UiNotice v-if="notice" tone="warning">{{ notice }}</UiNotice>

    <div v-if="report" class="area-map__summary">
      <strong>{{ report.total_opportunities.toLocaleString() }} inquiries</strong>
      <span>{{ located.toLocaleString() }} mention an area · {{ areas.length }} areas · {{ placed.length }} on the map</span>
      <span v-if="report.without_location">{{ report.without_location.toLocaleString() }} without any location</span>
      <span v-if="loading" class="area-map__progress" role="status"><span class="ui-spinner area-map__spinner" aria-hidden="true"></span> Updating...</span>
    </div>

    <div class="area-map__layout">
      <div class="area-map__map-wrap" :aria-busy="loading">
        <UiNotice v-if="mapError" tone="warning">{{ mapError }}</UiNotice>
        <div v-show="!mapError" ref="mapElement" class="area-map__map" aria-label="Map of inquiries by area"></div>
        <UiEmptyState v-if="!report && loading" busy title="Loading the area map..." class="area-map__loading" />
        <div v-if="report && !mapError" class="area-map__legend">
          <template v-if="activity === 'all'">
            <span v-for="lane in opportunityLanes" :key="lane.key"><i :style="{ background: ACTIVITY_COLORS[lane.key] }"></i>{{ lane.label }}</span>
            <small>Colour shows each area's most common inquiry type.</small>
          </template>
          <small v-else>Bigger circle = more inquiries.</small>
        </div>
      </div>

      <aside class="area-map__ranking">
        <h2>Top areas</h2>
        <p v-if="report && !areas.length" class="area-map__muted">No inquiry mentions an area for these filters.</p>
        <ol v-else>
          <li v-for="(area, index) in areas" :key="area.key" :class="{ selected: selectedKey === area.key, off: area.status !== 'placed' }">
            <button type="button" :disabled="area.status !== 'placed'" :title="area.status === 'placed' ? 'Show on the map' : STATUS_TEXT[area.status]" @click="openArea(area)">
              <span class="area-map__rank">{{ index + 1 }}</span>
              <span class="area-map__name">
                <strong>{{ area.name }}</strong>
                <small>{{ breakdown(area) }}</small>
                <small v-if="area.status !== 'placed'" class="area-map__off">
                  <FontAwesomeIcon :icon="faLocationDot" /> Not on the map: {{ STATUS_TEXT[area.status] }}<template v-if="area.error"> - {{ area.error }}</template>
                </small>
              </span>
              <span class="area-map__count">{{ area.count }}<small>{{ share(area) }}%</small></span>
            </button>
            <span class="area-map__bar" :style="{ width: `${(area.count / maxCount) * 100}%`, background: colorFor(area) }"></span>
          </li>
        </ol>
      </aside>
    </div>

    <UiCard v-if="google && google.waiting" class="area-map__google">
      <div>
        <strong>{{ google.waiting }} area{{ google.waiting === 1 ? '' : 's' }} not found in the free area list</strong>
        <p>
          These names (often buildings, projects or short forms such as "JVC") can be looked up on Google Maps, once each.
          Each lookup is one Google Maps request<template v-if="google.usage">: {{ google.usage.remaining }} of {{ google.usage.monthly_request_limit }} left this month</template>.
          Up to {{ google.batch }} areas with the most inquiries are looked up per click.
        </p>
      </div>
      <UiButton variant="primary" :disabled="placing || !google.available || (google.usage && !google.usage.remaining)" @click="placeOnGoogle">
        <span v-if="placing" class="ui-spinner area-map__spinner" aria-hidden="true"></span>
        {{ placing ? 'Looking up...' : 'Find on Google Maps' }}
      </UiButton>
      <p v-if="!google.available" class="area-map__muted">Google Maps is not configured or not enabled in Integrations.</p>
    </UiCard>
  </UiPage>
</template>

<style scoped>
.area-map__filters { margin-bottom: 1rem; }
.area-map__controls { display:grid; grid-template-columns:13rem 11rem 11rem auto; gap:.75rem; align-items:center; margin-top:1rem; }
.area-map__summary { display:flex; flex-wrap:wrap; align-items:center; gap:.4rem 1rem; margin:.75rem 0; }
.area-map__summary span, .area-map__muted { color:var(--ui-text-muted); }
.area-map__progress { display:inline-flex; align-items:center; gap:.4rem; color:var(--ui-primary) !important; }
.area-map__spinner { display:inline-block; width:14px; height:14px; margin:0; border-width:2px; }
.area-map__layout { display:grid; grid-template-columns:minmax(0,1fr) 22rem; gap:1rem; align-items:start; }
.area-map__map-wrap { position:relative; }
.area-map__map { height:640px; border:1px solid var(--ui-border); border-radius:var(--ui-radius); background:var(--ui-surface-muted); }
.area-map__loading { position:absolute; inset:0; }
.area-map__legend { display:flex; flex-wrap:wrap; align-items:center; gap:.4rem 1rem; margin-top:.5rem; font-size:.82rem; }
.area-map__legend span { display:inline-flex; align-items:center; gap:.35rem; }
.area-map__legend i { width:12px; height:12px; border-radius:50%; }
.area-map__legend small { color:var(--ui-text-muted); }
.area-map__ranking { max-height:680px; overflow:auto; padding:1rem; border:1px solid var(--ui-border); border-radius:var(--ui-radius); background:var(--ui-surface); }
.area-map__ranking h2 { margin:0 0 .6rem; font-size:1rem; }
.area-map__ranking ol { margin:0; padding:0; list-style:none; display:grid; gap:.35rem; }
.area-map__ranking li { position:relative; overflow:hidden; border-radius:calc(var(--ui-radius) - 2px); background:var(--ui-surface-muted); }
.area-map__ranking li.selected { outline:2px solid var(--ui-primary); }
.area-map__ranking button { position:relative; z-index:1; display:flex; width:100%; align-items:center; gap:.6rem; padding:.55rem .65rem; border:0; background:transparent; color:inherit; font:inherit; text-align:left; cursor:pointer; }
.area-map__ranking button:disabled { cursor:default; }
.area-map__bar { position:absolute; left:0; bottom:0; height:3px; opacity:.85; }
.area-map__rank { flex:none; width:1.6rem; color:var(--ui-text-muted); font-weight:700; }
.area-map__name { display:flex; flex:1; min-width:0; flex-direction:column; gap:.1rem; }
.area-map__name strong { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.area-map__name small { color:var(--ui-text-muted); font-size:.75rem; }
.area-map__off { color:var(--ui-warning) !important; }
.area-map__count { display:flex; flex-direction:column; align-items:flex-end; font-weight:800; font-size:1.05rem; }
.area-map__count small { color:var(--ui-text-muted); font-size:.72rem; font-weight:600; }
.area-map__google { display:flex; justify-content:space-between; align-items:center; gap:1rem; margin-top:1rem; }
.area-map__google p { margin:.3rem 0 0; color:var(--ui-text-muted); font-size:.86rem; }
:deep(.area-map__info) { display:grid; gap:.2rem; font-size:.86rem; }
@media (max-width:1000px) { .area-map__layout { grid-template-columns:1fr; } .area-map__map { height:420px; } .area-map__controls { grid-template-columns:1fr 1fr; } .area-map__google { flex-direction:column; align-items:flex-start; } }
</style>
