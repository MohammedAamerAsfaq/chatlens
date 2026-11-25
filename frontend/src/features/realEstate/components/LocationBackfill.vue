<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { realEstateApi } from '@/api'
import { apiError } from '@/features/realEstate/apiErrors'

// Run the Location AI step for inquiries received before it existed, ones that failed, or
// all of them again (e.g. after changing the "Real Estate Location" instructions).
// New inquiries are located automatically.
const POLL_MS = 10000

const status = ref(null)
const busy = ref(false)
const error = ref('')
const notice = ref('')
let pollTimer = null

const unlocated = computed(() => (status.value ? status.value.pending + status.value.error : 0))
const plural = (count, one, many) => `${count.toLocaleString()} ${count === 1 ? one : many}`

function show(data) {
  status.value = data
  clearTimeout(pollTimer)
  // While the AI works through the queue, keep the counts current.
  if (data.locating) pollTimer = setTimeout(load, POLL_MS)
}

async function load() {
  try {
    show((await realEstateApi.locationStatus()).data)
  } catch (exc) {
    error.value = apiError(exc, 'Unable to load how many inquiries still need a location.')
  }
}

async function locate(scope) {
  if (scope === 'all' && !window.confirm(
    `Run the location AI again for all ${plural(status.value.with_properties, 'inquiry', 'inquiries')} with property details, including ones already located? Each inquiry is one AI call.`,
  )) return
  busy.value = true; error.value = ''; notice.value = ''
  try {
    const { data } = await realEstateApi.locateAreas(scope)
    notice.value = data.queued
      ? `${plural(data.queued, 'inquiry', 'inquiries')} queued. The Area Map updates as the AI works through them.`
      : 'Nothing to queue: these inquiries are already being located or have no property details.'
    show(data)
  } catch (exc) {
    error.value = apiError(exc, 'Unable to queue the location AI.')
  } finally {
    busy.value = false
  }
}

onMounted(load)
onBeforeUnmount(() => clearTimeout(pollTimer))
</script>

<template>
  <div class="location-backfill" aria-label="Find locations for earlier inquiries">
    <h4>Inquiries without an area</h4>
    <p v-if="error" class="location-backfill__error" role="alert">{{ error }}</p>
    <template v-if="status">
      <p class="location-backfill__state">
        <strong v-if="status.locating" class="location-backfill__progress"><span class="ui-spinner location-backfill__spinner" aria-hidden="true"></span> Locating {{ plural(status.locating, 'inquiry', 'inquiries') }}...</strong>
        <strong v-else-if="unlocated">{{ plural(unlocated, 'inquiry has', 'inquiries have') }} no area yet</strong>
        <strong v-else>Every inquiry with property details has been located.</strong>
        <span v-if="status.pending"> · {{ status.pending.toLocaleString() }} not located yet</span>
        <span v-if="status.error" class="location-backfill__failed"> · {{ status.error.toLocaleString() }} failed</span>
      </p>
      <p class="location-backfill__help">
        One AI call per inquiry{{ status.location_search_mode === 'web_search' ? ', with live web search' : '' }}.
        New inquiries are located automatically; this is for inquiries received before, or ones that failed.
      </p>
      <div v-if="status.error_reasons.length" class="location-backfill__reasons" role="status">
        <strong>Why the location step failed</strong>
        <span v-for="reason in status.error_reasons" :key="reason.error">{{ reason.count.toLocaleString() }} × {{ reason.error }}</span>
      </div>
      <p v-if="notice" class="location-backfill__notice">{{ notice }}</p>
      <div class="location-backfill__actions">
        <button type="button" :disabled="busy || !status.with_properties" @click="locate('all')">Re-check all</button>
        <button type="button" class="primary" :disabled="busy || !unlocated" @click="locate('unlocated')">
          {{ busy ? 'Queuing...' : `Find locations for ${unlocated.toLocaleString()}` }}
        </button>
      </div>
    </template>
  </div>
</template>

<style scoped>
.location-backfill{margin-top:14px;padding-top:12px;border-top:1px solid var(--ui-border,#e5e7eb)}
.location-backfill h4{margin:0 0 6px;font-size:.9rem}
.location-backfill p{margin:0 0 6px;font-size:.82rem}
.location-backfill__help{color:var(--ui-text-muted,#6b7280)}
.location-backfill__state span{color:var(--ui-text-muted,#6b7280)}
.location-backfill__state .location-backfill__failed,.location-backfill__error{color:var(--ui-danger,#dc2626)}
.location-backfill__error{font-weight:600}
.location-backfill__notice{color:var(--ui-success,#16a34a);font-weight:600}
.location-backfill__progress{display:inline-flex;align-items:center;gap:6px;color:var(--ui-primary,#2563eb)}
.location-backfill__spinner{display:inline-block;width:13px;height:13px;margin:0;border-width:2px}
.location-backfill__reasons{display:flex;flex-direction:column;gap:2px;margin:0 0 8px;padding:8px 10px;border-radius:8px;background:var(--ui-danger-soft,#fef2f2);color:var(--ui-danger,#dc2626);font-size:.8rem}
.location-backfill__actions{display:flex;justify-content:flex-end;gap:8px}
.location-backfill button{padding:5px 10px;border:1px solid var(--ui-border,#d1d5db);border-radius:6px;background:var(--ui-surface,#fff);color:inherit;font-size:.8rem;cursor:pointer}
.location-backfill button.primary{border-color:var(--ui-primary,#2563eb);background:var(--ui-primary,#2563eb);color:var(--ui-on-primary,#fff)}
.location-backfill button:disabled{opacity:.6;cursor:default}
</style>
