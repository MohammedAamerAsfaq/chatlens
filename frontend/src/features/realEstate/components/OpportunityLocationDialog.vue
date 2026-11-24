<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { FontAwesomeIcon } from '@fortawesome/vue-fontawesome'
import { faMapLocationDot, faWandMagicSparkles } from '@fortawesome/free-solid-svg-icons'
import { realEstateApi } from '@/api'
import UiButton from '@/components/ui/UiButton.vue'
import UiModal from '@/components/ui/UiModal.vue'
import UiNotice from '@/components/ui/UiNotice.vue'
import { apiError } from '@/features/realEstate/apiErrors'
import { googleMapsUrl, itemPlace } from '@/features/realEstate/location'

// Location of an inquiry's properties: find it with the Location AI, set it by hand, or
// clear it. Emits the updated opportunity so the board can refresh the card.
const props = defineProps({
  open: { type: Boolean, default: false },
  opportunity: { type: Object, default: null },
})
const emit = defineEmits(['close', 'updated'])

const STATUS_TEXT = {
  pending: 'Not located yet',
  unknown: 'No location',
  error: 'The location step failed',
}

const busy = ref('')
const error = ref('')
const editing = ref(null)
const form = reactive({ area: '', sub_area: '', city: '' })

const items = computed(() => props.opportunity?.items || [])
const title = computed(() => (props.opportunity ? `Location for #${props.opportunity.id}` : 'Location'))

watch(() => props.open, open => {
  if (open) { error.value = ''; editing.value = null; busy.value = '' }
})

function startEdit(item) {
  editing.value = item.id
  Object.assign(form, { area: item.geo_area || '', sub_area: item.geo_sub_area || '', city: item.geo_city || '' })
  error.value = ''
}

async function run(key, request) {
  busy.value = key; error.value = ''
  try {
    const { data } = await request()
    editing.value = null
    emit('updated', data)
  } catch (exc) {
    error.value = apiError(exc, 'Unable to update the location.')
  } finally {
    busy.value = ''
  }
}

function findWithAi() {
  return run('ai', () => realEstateApi.locateOpportunity(props.opportunity.id))
}

function save(item) {
  return run(item.id, () => realEstateApi.setOpportunityLocation(props.opportunity.id, { item: item.id, action: 'set', ...form }))
}

function clear(item) {
  if (!window.confirm(`Clear the location of ${itemLabel(item)}? The location AI will not set it again on its own.`)) return
  return run(item.id, () => realEstateApi.setOpportunityLocation(props.opportunity.id, { item: item.id, action: 'clear' }))
}

function itemLabel(item) {
  return items.value.length > 1 ? `property ${item.sequence}${item.title ? ` (${item.title})` : ''}` : 'this inquiry'
}

function sourceText(item) {
  if (item.geo_source === 'manual') return item.geo_basis || 'Set by hand'
  const confidence = item.geo_confidence != null ? ` · ${Math.round(Number(item.geo_confidence) * 100)}% sure` : ''
  return `Found by the location AI${confidence}`
}

function positionNote(item) {
  const position = item.geo_position
  if (!position || position.status === 'placed') return ''
  return position.status === 'pending' ? 'Not on the map yet: waiting for a Google Maps lookup.' : `Not on the map: ${position.error || 'not found'}`
}
</script>

<template>
  <UiModal :open="open" :title="title" subtitle="Where the inquiry's property is, used by the Area Map." @close="emit('close')">
    <UiNotice v-if="error" tone="danger" role="alert">{{ error }}</UiNotice>
    <div class="location-dialog__ai">
      <p>The location AI reads the whole inquiry (message, group name, sender and properties) and finds the area. This replaces locations set by hand.</p>
      <UiButton variant="primary" :disabled="!!busy" @click="findWithAi">
        <span v-if="busy === 'ai'" class="ui-spinner location-dialog__spinner" aria-hidden="true"></span>
        <FontAwesomeIcon v-else :icon="faWandMagicSparkles" /> {{ busy === 'ai' ? 'Finding...' : 'Find with AI' }}
      </UiButton>
    </div>

    <p v-if="!items.length" class="location-dialog__muted">This inquiry has no property details to locate.</p>
    <article v-for="item in items" :key="item.id" class="location-dialog__item">
      <header>
        <strong>{{ items.length > 1 ? `Property ${item.sequence}` : 'Property' }}<template v-if="item.title"> · {{ item.title }}</template></strong>
        <small v-if="item.locations?.length">Broker wrote: {{ item.locations.join(', ') }}</small>
      </header>

      <form v-if="editing === item.id" class="location-dialog__form" @submit.prevent="save(item)">
        <label>Area (community or district)<input v-model="form.area" placeholder="e.g. DAMAC Hills 2" aria-label="Area" required /></label>
        <label>Building, cluster or project<input v-model="form.sub_area" placeholder="e.g. Verona" aria-label="Building, cluster or project" /></label>
        <label>City<input v-model="form.city" placeholder="e.g. Dubai" aria-label="City" /></label>
        <div class="location-dialog__actions">
          <UiButton type="submit" variant="primary" size="small" :disabled="!!busy">{{ busy === item.id ? 'Saving...' : 'Save location' }}</UiButton>
          <UiButton type="button" variant="outline" size="small" :disabled="!!busy" @click="editing = null">Cancel</UiButton>
        </div>
      </form>

      <template v-else>
        <div v-if="item.geo_status === 'located'" class="location-dialog__place">
          <FontAwesomeIcon :icon="faMapLocationDot" class="location-dialog__pin" />
          <div>
            <strong>{{ itemPlace(item) }}</strong>
            <small>{{ sourceText(item) }}</small>
            <small v-if="item.geo_source !== 'manual' && item.geo_basis" class="location-dialog__basis">{{ item.geo_basis }}</small>
            <small v-if="positionNote(item)" class="location-dialog__warn">{{ positionNote(item) }}</small>
          </div>
          <a :href="googleMapsUrl(item)" target="_blank" rel="noopener noreferrer">Open in Google Maps</a>
        </div>
        <div v-else class="location-dialog__none">
          <strong>{{ STATUS_TEXT[item.geo_status] || 'No location' }}</strong>
          <small v-if="item.geo_status === 'error' && item.geo_error" class="location-dialog__warn">{{ item.geo_error }}</small>
          <small v-else-if="item.geo_basis">{{ item.geo_basis }}</small>
        </div>
        <div class="location-dialog__actions">
          <UiButton variant="outline" size="small" :disabled="!!busy" @click="startEdit(item)">{{ item.geo_status === 'located' ? 'Edit location' : 'Add location' }}</UiButton>
          <UiButton v-if="item.geo_status === 'located'" variant="outline" size="small" class="location-dialog__clear" :disabled="!!busy" @click="clear(item)">
            {{ busy === item.id ? 'Clearing...' : 'Clear location' }}
          </UiButton>
        </div>
      </template>
    </article>
  </UiModal>
</template>

<style scoped>
.location-dialog__ai { display:flex; align-items:center; justify-content:space-between; gap:1rem; margin-bottom:1rem; padding:.75rem; border-radius:var(--ui-radius-sm); background:var(--ui-surface-muted); }
.location-dialog__ai p { margin:0; color:var(--ui-text-muted); font-size:.84rem; }
.location-dialog__ai :deep(.ui-button) { flex:none; }
.location-dialog__spinner { display:inline-block; width:14px; height:14px; margin:0; border-width:2px; }
.location-dialog__item { display:grid; gap:.6rem; padding:.85rem 0; border-top:1px solid var(--ui-border); }
.location-dialog__item header { display:flex; flex-direction:column; gap:.15rem; }
.location-dialog__item small, .location-dialog__muted { color:var(--ui-text-muted); font-size:.8rem; }
.location-dialog__place { display:flex; align-items:flex-start; gap:.65rem; }
.location-dialog__place > div, .location-dialog__none { display:flex; flex:1; flex-direction:column; gap:.15rem; }
.location-dialog__place a { flex:none; color:var(--ui-primary); font-size:.84rem; font-weight:700; }
.location-dialog__pin { margin-top:.15rem; color:#ea4335; font-size:1.2rem; }
.location-dialog__basis { font-style:italic; }
.location-dialog__warn { color:var(--ui-warning) !important; }
.location-dialog__form { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:.6rem; }
.location-dialog__form label { display:flex; flex-direction:column; gap:.25rem; color:var(--ui-text-muted); font-size:.78rem; font-weight:700; }
.location-dialog__form input { min-height:34px; padding:.35rem .5rem; border:1px solid var(--ui-border-strong); border-radius:var(--ui-radius-sm); background:var(--ui-surface); color:var(--ui-text); font:inherit; font-weight:500; }
.location-dialog__form .location-dialog__actions { grid-column:1/-1; }
.location-dialog__actions { display:flex; justify-content:flex-end; gap:.5rem; }
.location-dialog__clear { color:var(--ui-danger); }
@media (max-width:640px) { .location-dialog__form { grid-template-columns:1fr; } .location-dialog__ai, .location-dialog__place { flex-direction:column; align-items:stretch; } }
</style>
