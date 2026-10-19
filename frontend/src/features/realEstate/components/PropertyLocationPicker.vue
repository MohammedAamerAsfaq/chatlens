<script setup>
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { integrationsApi } from '@/api'
import UiFormField from '@/components/ui/UiFormField.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiNotice from '@/components/ui/UiNotice.vue'
import { loadGoogleMaps } from '../googleMapsLoader'

const props = defineProps({
  modelValue: { type: Object, required: true },
  countryCode: { type: String, default: 'AE' },
})
const emit = defineEmits(['update:modelValue'])
const query = ref('')
const suggestions = ref([])
const searching = ref(false)
const resolving = ref(false)
const error = ref('')
const mapError = ref('')
const mapElement = ref(null)
let debounceTimer
let sessionToken = ''
let map
let marker
let suppressSearch = false
let reverseRequest = 0

function token() {
  if (!sessionToken) {
    sessionToken = globalThis.crypto?.randomUUID?.()
      || `property-${Date.now()}-${Math.random().toString(16).slice(2)}`
  }
  return sessionToken
}
function patchAddress(values) {
  emit('update:modelValue', { ...props.modelValue, ...values })
}
function coordinate(value, fallback) {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : fallback
}
function currentPosition() {
  return {
    lat: coordinate(props.modelValue.latitude, 25.204849),
    lng: coordinate(props.modelValue.longitude, 55.270783),
  }
}
async function applyPosition(position) {
  const latitude = Number(position.lat).toFixed(6)
  const longitude = Number(position.lng).toFixed(6)
  const requestId = ++reverseRequest
  patchAddress({ latitude, longitude })
  resolving.value = true; error.value = ''
  try {
    const { data } = await integrationsApi.propertyReverseGeocode({
      latitude, longitude, country_code: props.countryCode || 'AE',
    })
    if (requestId !== reverseRequest) return
    patchAddress(data.address || { latitude, longitude })
    suppressSearch = true
    query.value = data.address?.normalized_location || `${latitude}, ${longitude}`
    suggestions.value = []
  } catch (exc) {
    if (requestId === reverseRequest) {
      error.value = exc.response?.data?.detail || 'Address details could not be resolved for this location.'
    }
  } finally {
    if (requestId === reverseRequest) resolving.value = false
  }
}
function syncMap() {
  if (!map || !marker) return
  const position = currentPosition()
  marker.setPosition(position)
  map.panTo(position)
}
async function initializeMap() {
  try {
    const { data } = await integrationsApi.propertyMapConfig()
    await loadGoogleMaps(data.browser_api_key)
    await nextTick()
    const position = currentPosition()
    map = new window.google.maps.Map(mapElement.value, {
      center: position, zoom: props.modelValue.latitude ? 16 : 11,
      mapTypeControl: false, streetViewControl: false, fullscreenControl: true,
    })
    marker = new window.google.maps.Marker({ map, position, draggable: true })
    marker.addListener('dragend', event => applyPosition({
      lat: event.latLng.lat(), lng: event.latLng.lng(),
    }))
    map.addListener('click', event => applyPosition({
      lat: event.latLng.lat(), lng: event.latLng.lng(),
    }))
  } catch (exc) {
    mapError.value = exc.response?.data?.detail || exc.message || 'Interactive map is unavailable.'
  }
}
async function searchAddress() {
  const value = query.value.trim()
  if (value.length < 3) { suggestions.value = []; return }
  searching.value = true; error.value = ''
  try {
    const { data } = await integrationsApi.propertyAddressSuggestions({
      query: value, country_code: props.countryCode || 'AE', session_token: token(),
    })
    suggestions.value = data.results
    sessionToken = data.session_token
  } catch (exc) {
    error.value = exc.response?.data?.detail || 'Address suggestions could not be loaded.'
    suggestions.value = []
  } finally { searching.value = false }
}
async function selectSuggestion(suggestion) {
  resolving.value = true; error.value = ''
  try {
    const { data } = await integrationsApi.propertyPlaceDetails({
      place_id: suggestion.place_id,
      session_token: token(),
      country_code: props.countryCode || 'AE',
    })
    const values = Object.fromEntries(
      Object.entries(data.address || {}).filter(([, value]) => value !== '' && value != null),
    )
    patchAddress(values)
    suppressSearch = true
    query.value = data.address.normalized_location || suggestion.text
    suggestions.value = []
    sessionToken = ''
    await nextTick()
    syncMap()
  } catch (exc) {
    error.value = exc.response?.data?.detail || 'The selected address could not be resolved.'
  } finally { resolving.value = false }
}

watch(query, () => {
  if (suppressSearch) { suppressSearch = false; return }
  clearTimeout(debounceTimer)
  debounceTimer = setTimeout(searchAddress, 450)
})
watch(() => [props.modelValue.latitude, props.modelValue.longitude], syncMap)
onMounted(() => {
  suppressSearch = true
  query.value = props.modelValue.normalized_location || ''
  initializeMap()
})
onBeforeUnmount(() => clearTimeout(debounceTimer))
</script>

<template>
  <div class="location-picker">
    <UiFormField label="Find address on Google Maps" hint="Type at least 3 characters, then select a result. Original address fields remain editable.">
      <UiInput v-model="query" autocomplete="off" placeholder="Building, community, street, or address..." />
    </UiFormField>
    <div v-if="searching || resolving" class="picker-status">{{ resolving ? 'Updating address...' : 'Searching...' }}</div>
    <div v-if="suggestions.length" class="suggestions">
      <button v-for="suggestion in suggestions" :key="suggestion.place_id" type="button" @click="selectSuggestion(suggestion)">
        <strong>{{ suggestion.main_text || suggestion.text }}</strong>
        <span>{{ suggestion.secondary_text }}</span>
      </button>
    </div>
    <UiNotice v-if="error" tone="danger">{{ error }}</UiNotice>
    <div ref="mapElement" class="property-map" :class="{ unavailable: mapError }">
      <span v-if="mapError">{{ mapError }}</span>
    </div>
    <p class="map-note">Click the map or drag the marker to update coordinates and available address fields.</p>
  </div>
</template>

<style scoped>
.location-picker{position:relative;display:grid;gap:10px}.picker-status,.map-note{color:var(--ui-text-muted);font-size:.8rem}.picker-status{position:absolute;right:12px;top:38px}.suggestions{position:absolute;z-index:20;top:72px;left:0;right:0;display:grid;max-height:230px;overflow:auto;border:1px solid var(--ui-border);border-radius:var(--ui-radius-md);background:var(--ui-surface);box-shadow:var(--ui-shadow-lg)}.suggestions button{display:grid;gap:3px;padding:11px 14px;border:0;border-bottom:1px solid var(--ui-border);background:transparent;text-align:left;cursor:pointer}.suggestions button:hover{background:var(--ui-primary-soft)}.suggestions span{color:var(--ui-text-muted);font-size:.8rem}.property-map{display:grid;height:320px;place-items:center;overflow:hidden;border:1px solid var(--ui-border);border-radius:var(--ui-radius-lg);background:var(--ui-surface-muted)}.property-map.unavailable{padding:24px;color:var(--ui-text-muted);text-align:center}.map-note{margin:0}
</style>
