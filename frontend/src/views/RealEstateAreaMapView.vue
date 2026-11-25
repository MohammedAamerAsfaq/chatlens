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
import UiSelect from '@/components/ui/UiSelect.vue'
import UiTabs from '@/components/ui/UiTabs.vue'
import { apiError } from '@/features/realEstate/apiErrors'
import { activityColors as ACTIVITY_COLORS, opportunityLanes, statusFilters } from '@/features/realEstate/boardOptions'
import AreaInquiriesGrid from '@/features/realEstate/components/AreaInquiriesGrid.vue'
import { loadGoogleMaps } from '@/features/realEstate/googleMapsLoader'

const ALL_COLOR = '#2563eb'
const AREA_STATUS_TEXT = {
  pending: 'Waiting for a Google Maps lookup',
  not_found: 'Google Maps could not find it',
  error: 'Google Maps lookup failed',
}
const POLL_MS = 10000

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
const selectedId = ref(null)
const rankingElement = ref(null)
const mergingId = ref(null)
const mergeTarget = ref(null)
const merging = ref(false)

let map = null
let infoWindow = null
let markers = new Map()
let pollTimer = null

const areas = computed(() => report.value?.areas || [])
const totals = computed(() => report.value?.totals || null)
const placed = computed(() => areas.value.filter(area => area.status === 'placed'))
const maxCount = computed(() => Math.max(1, ...areas.value.map(area => area.count)))
const google = computed(() => report.value?.google || null)
const selectedArea = computed(() => areas.value.find(area => area.id === selectedId.value) || null)
const gridFilters = computed(() => params())

function params() {
  const value = { activity_type: activity.value }
  if (status.value) value.status = status.value
  if (dateFrom.value) value.date_from = dateFrom.value.slice(0, 10)
  if (dateTo.value) value.date_to = dateTo.value.slice(0, 10)
  return value
}

async function show(data) {
  report.value = data
  // The chosen area is gone (merged away, or none of its inquiries match the new filters).
  if (selectedId.value && !areas.value.some(area => area.id === selectedId.value)) clearArea()
  schedulePoll()
  await drawMap()
}

let loadSeq = 0
async function load({ quiet = false } = {}) {
  const seq = ++loadSeq
  if (!quiet) { loading.value = true; error.value = ''; notice.value = '' }
  try {
    const { data } = await realEstateApi.areaMap(params())
    if (seq !== loadSeq) return
    await show(data)
  } catch (exc) {
    if (seq !== loadSeq) return
    error.value = apiError(exc, 'Unable to load the area map.')
  } finally {
    if (seq === loadSeq) loading.value = false
  }
}

// While the Location AI step is running for queued inquiries, refresh the counts.
function schedulePoll() {
  clearTimeout(pollTimer)
  if (report.value?.locating) pollTimer = setTimeout(() => load({ quiet: true }), POLL_MS)
}

function startMerge(area) {
  mergingId.value = area.id
  mergeTarget.value = null
}

const mergeOptions = computed(() => areas.value.filter(area => area.id !== mergingId.value))

async function mergeInto(area) {
  const target = areas.value.find(item => item.id === mergeTarget.value)
  if (!target) return
  if (!window.confirm(`Merge "${areaLabel(area)}" into "${areaLabel(target)}"? Its ${area.count} inquir${area.count === 1 ? 'y moves' : 'ies move'} there, and later inquiries the AI places in "${area.name}" go there too.`)) return
  merging.value = true; error.value = ''; notice.value = ''
  try {
    const { data } = await realEstateApi.mergeAreas(area.id, target.id, params())
    notice.value = `Merged "${area.name}" into "${target.name}".`
    mergingId.value = null
    await show(data)
  } catch (exc) {
    error.value = apiError(exc, 'Unable to merge the areas.')
  } finally {
    merging.value = false
  }
}

async function placeOnGoogle() {
  placing.value = true; error.value = ''; notice.value = ''
  try {
    const { data } = await realEstateApi.placeAreas(params())
    notice.value = data.notice || ''
    await show(data)
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
  const located = totals.value?.located || 0
  return located ? Math.round((area.count / located) * 100) : 0
}

function breakdown(area) {
  return Object.entries(area.by_activity)
    .sort((a, b) => b[1] - a[1])
    .map(([key, count]) => `${laneLabels[key] || key}: ${count}`)
    .join(' · ')
}

function subAreas(area) {
  return area.sub_areas.map(sub => `${sub.name} ${sub.count}`).join(' · ')
}

function areaLabel(area) {
  return area.city && area.city !== area.name ? `${area.name}, ${area.city}` : area.name
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
    const firstDraw = !map
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
        map, position, title: `${areaLabel(area)}: ${area.count}`, zIndex: area.count,
        icon: { path: maps.SymbolPath.CIRCLE, scale, fillColor: colorFor(area), fillOpacity: 0.72, strokeColor: '#fff', strokeWeight: 2 },
        label: { text: String(area.count), color: '#fff', fontSize: '13px', fontWeight: '700' },
      })
      marker.addListener('click', () => openArea(area, false))
      markers.set(area.id, marker)
      bounds.extend(position)
    }
    // Keep the user's view while the counts refresh during a backfill.
    if (firstDraw || !report.value.locating) {
      if (placed.value.length > 1) map.fitBounds(bounds, 48)
      else if (placed.value.length === 1) { map.setCenter(bounds.getCenter()); map.setZoom(13) }
    }
  } catch (exc) {
    mapError.value = exc.message || 'The map could not be loaded.'
  }
}

// Scroll only the ranking panel (not the page), so the map stays in view.
async function revealInRanking(areaId) {
  await nextTick()
  const panel = rankingElement.value
  const item = panel && [...panel.querySelectorAll('[data-area-id]')].find(el => el.dataset.areaId === String(areaId))
  if (!panel || !item) return
  const offset = item.getBoundingClientRect().top - panel.getBoundingClientRect().top
  panel.scrollTo({ top: panel.scrollTop + offset - 48, behavior: 'smooth' })
}

function clearArea() {
  selectedId.value = null
  infoWindow?.close()
}

function openArea(area, pan = true) {
  selectedId.value = area.id
  // Clicked on the map: bring its card into view. Clicked in the list: it is already visible.
  if (!pan) revealInRanking(area.id)
  const marker = markers.get(area.id)
  if (!marker || !map) { infoWindow?.close(); return }
  if (pan) { map.panTo(marker.getPosition()); if (map.getZoom() < 12) map.setZoom(12) }
  infoWindow.setContent(
    `<div class="area-map__info"><strong>${escapeHtml(areaLabel(area))}</strong>`
    + `<div>${area.count} inquir${area.count === 1 ? 'y' : 'ies'} (${share(area)}%)</div>`
    + `<div>${escapeHtml(breakdown(area))}</div>`
    + (area.sub_areas.length ? `<div>Buildings / clusters: ${escapeHtml(subAreas(area))}</div>` : '')
    + (area.matched_label ? `<small>Placed at ${escapeHtml(area.matched_label)}</small>` : '')
    + '</div>',
  )
  infoWindow.open({ map, anchor: marker })
}

watch([activity, status, dateFrom, dateTo], () => load())
onMounted(() => load())
onBeforeUnmount(() => {
  clearTimeout(pollTimer)
  markers.forEach(marker => marker.setMap(null))
  markers = new Map()
  map = null
})
</script>

<template>
  <UiPage width="wide">
    <UiCard class="area-map__filters">
      <UiTabs v-model="activity" :tabs="tabs" />
      <div class="area-map__controls">
        <UiSelect v-model="status" :options="statusFilters" />
        <UiDatePicker v-model="dateFrom" placeholder="From date" />
        <UiDatePicker v-model="dateTo" placeholder="To date" />
        <UiButton variant="outline" :disabled="loading" :aria-busy="loading" @click="load()">
          <span v-if="loading" class="ui-spinner area-map__spinner" aria-hidden="true"></span><FontAwesomeIcon v-else :icon="faRotate" /> {{ loading ? 'Updating...' : 'Refresh' }}
        </UiButton>
      </div>
    </UiCard>

    <UiNotice v-if="error" tone="danger">{{ error }}</UiNotice>
    <UiNotice v-if="notice" tone="info">{{ notice }}</UiNotice>

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

      <aside ref="rankingElement" class="area-map__ranking">
        <h2>Top areas</h2>
        <p v-if="report && !areas.length" class="area-map__muted">No located inquiries for these filters yet.</p>
        <ol v-else>
          <li v-for="(area, index) in areas" :key="area.id" :data-area-id="area.id" :class="{ selected: selectedId === area.id, off: area.status !== 'placed' }">
            <button type="button" :title="area.status === 'placed' ? 'Show on the map and list its inquiries' : `List its inquiries (not on the map: ${AREA_STATUS_TEXT[area.status]})`" @click="openArea(area)">
              <span class="area-map__rank">{{ index + 1 }}</span>
              <span class="area-map__name">
                <strong>{{ areaLabel(area) }}</strong>
                <small>{{ breakdown(area) }}</small>
                <small v-if="area.sub_areas.length" class="area-map__subs">{{ subAreas(area) }}</small>
                <small v-if="area.status !== 'placed'" class="area-map__off">
                  <FontAwesomeIcon :icon="faLocationDot" /> Not on the map: {{ AREA_STATUS_TEXT[area.status] }}<template v-if="area.error"> - {{ area.error }}</template>
                </small>
              </span>
              <span class="area-map__count">{{ area.count }}<small>{{ share(area) }}%</small></span>
            </button>
            <div v-if="mergingId === area.id" class="area-map__merge">
              <select v-model="mergeTarget" :aria-label="`Merge ${area.name} into`">
                <option :value="null" disabled>Merge into...</option>
                <option v-for="option in mergeOptions" :key="option.id" :value="option.id">{{ areaLabel(option) }} ({{ option.count }})</option>
              </select>
              <button type="button" class="area-map__link" :disabled="!mergeTarget || merging" @click="mergeInto(area)">{{ merging ? 'Merging...' : 'Merge' }}</button>
              <button type="button" class="area-map__link" :disabled="merging" @click="mergingId = null">Cancel</button>
            </div>
            <button v-else-if="areas.length > 1" type="button" class="area-map__link area-map__merge-start" title="Same place written another way? Merge it into the right area." @click="startMerge(area)">Merge...</button>
            <span class="area-map__bar" :style="{ width: `${(area.count / maxCount) * 100}%`, background: colorFor(area) }"></span>
          </li>
        </ol>
      </aside>
    </div>

    <AreaInquiriesGrid v-if="report" :filters="gridFilters" :area="selectedArea" @clear-area="clearArea" />

    <UiCard v-if="google && google.waiting" class="area-map__google">
      <div>
        <strong>{{ google.waiting }} area{{ google.waiting === 1 ? '' : 's' }} waiting for a map position</strong>
        <p>
          These areas are not in the free area list and Google Maps could not be used when they were found.
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
.area-map__muted { color:var(--ui-text-muted); }
.area-map__spinner { display:inline-block; width:14px; height:14px; margin:0; border-width:2px; }
.area-map__google { display:flex; justify-content:space-between; align-items:center; gap:1rem; margin-bottom:1rem; }
.area-map__google { margin:1rem 0 0; }
.area-map__google p { margin:.3rem 0 0; color:var(--ui-text-muted); font-size:.86rem; }
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
.area-map__name .area-map__subs { font-style:italic; }
.area-map__off { color:var(--ui-warning) !important; }
.area-map__count { display:flex; flex-direction:column; align-items:flex-end; font-weight:800; font-size:1.05rem; }
.area-map__count small { color:var(--ui-text-muted); font-size:.72rem; font-weight:600; }
.area-map__merge { position:relative; z-index:1; display:flex; align-items:center; gap:.4rem; padding:0 .65rem .55rem 2.85rem; }
.area-map__merge select { flex:1; min-width:0; padding:.25rem .4rem; border:1px solid var(--ui-border-strong); border-radius:var(--ui-radius-sm); background:var(--ui-surface); color:var(--ui-text); font:inherit; font-size:.8rem; }
.area-map__ranking .area-map__link { width:auto; padding:0; border:0; background:none; color:var(--ui-primary); font-size:.78rem; font-weight:700; cursor:pointer; }
.area-map__ranking .area-map__link:disabled { opacity:.5; cursor:default; }
.area-map__ranking .area-map__merge-start { position:relative; z-index:1; display:block; margin:-.35rem .65rem .45rem auto; }
:deep(.area-map__info) { display:grid; gap:.2rem; font-size:.86rem; }
@media (max-width:1000px) { .area-map__layout { grid-template-columns:1fr; } .area-map__map { height:420px; } .area-map__controls { grid-template-columns:1fr 1fr; } .area-map__google { flex-direction:column; align-items:flex-start; } }
</style>
