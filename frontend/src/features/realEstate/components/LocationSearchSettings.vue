<script setup>
import { computed, onMounted, ref } from 'vue'
import { realEstateApi } from '@/api'
import { apiError } from '@/features/realEstate/apiErrors'
import LocationBackfill from './LocationBackfill.vue'

// What the Real Estate Location AI step may use to work out where an inquiry's property is
// (apps/real_estate/services/location_service.py). Its instructions are the
// "Real Estate Location" prompt below.
const DESCRIPTIONS = {
  model_knowledge: "The AI uses what it knows about the market's communities, projects and buildings. No extra cost; may not know new or small projects.",
  web_search: 'The AI also searches the web to check which community a building or cluster belongs to. Extra cost on every inquiry (OpenRouter web search) and slower; needs OpenRouter models with paid credit.',
}

const state = ref(null)
const mode = ref('')
const saving = ref(false)
const error = ref('')
const notice = ref('')
const changed = computed(() => state.value && mode.value !== state.value.mode)

async function load() {
  error.value = ''
  try {
    state.value = (await realEstateApi.getLocationSearch()).data
    mode.value = state.value.mode
  } catch (exc) {
    error.value = apiError(exc, 'Unable to load the location settings.')
  }
}

async function save() {
  saving.value = true; error.value = ''; notice.value = ''
  try {
    state.value = (await realEstateApi.setLocationSearch(mode.value)).data
    notice.value = 'Saved. New inquiries and "Find locations" below use this.'
  } catch (exc) {
    error.value = apiError(exc, 'Unable to save the location settings.')
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<template>
  <section class="location-search" aria-label="Inquiry location finding">
    <header>
      <h3>Inquiry location finding</h3>
      <p>
        After each inquiry is extracted, the AI reads the whole inquiry (message, group name, sender and
        properties) and names each property's area, building or cluster, and city for the Area Map. Its
        instructions are the "Real Estate Location" prompt below. Choose what it may use.
      </p>
    </header>
    <p v-if="error" class="location-search__error" role="alert">{{ error }}</p>
    <p v-if="notice" class="location-search__notice">{{ notice }}</p>
    <template v-if="state">
      <div class="location-search__modes" role="radiogroup" aria-label="Location finding source">
        <label v-for="choice in state.choices" :key="choice.value" :class="{ active: mode === choice.value }">
          <input v-model="mode" type="radio" name="location-search-mode" :value="choice.value" />
          <span>
            <strong>{{ choice.label }}</strong>
            <small>{{ DESCRIPTIONS[choice.value] }}</small>
            <small v-if="choice.value === 'web_search' && state.web_search_blockers.length" class="location-search__warn">
              Not available yet: the location AI uses {{ state.web_search_blockers.join(', ') }}.
            </small>
          </span>
        </label>
      </div>
      <div class="location-search__actions">
        <button type="button" class="primary" :disabled="!changed || saving" @click="save">{{ saving ? 'Saving...' : 'Save location finding' }}</button>
      </div>
    </template>
    <LocationBackfill />
  </section>
</template>

<style scoped>
.location-search{margin:0 0 16px;padding:16px;border:1px solid var(--ui-border,#e5e7eb);border-radius:10px;background:var(--ui-surface,#fff)}
.location-search h3{margin:0 0 4px;font-size:1rem}
.location-search header p{margin:0 0 10px;color:var(--ui-text-muted,#6b7280);font-size:.82rem}
.location-search__modes{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:8px}
.location-search__modes label{display:flex;gap:8px;padding:10px;border:1px solid var(--ui-border,#e5e7eb);border-radius:8px;cursor:pointer}
.location-search__modes label.active{border-color:var(--ui-primary,#2563eb);background:var(--ui-primary-soft,#eff6ff)}
.location-search__modes span{display:flex;flex-direction:column;gap:3px}
.location-search__modes small{color:var(--ui-text-muted,#6b7280);font-size:.75rem;line-height:1.35}
.location-search__modes .location-search__warn{color:var(--ui-warning,#b45309);font-weight:600}
.location-search__actions{display:flex;justify-content:flex-end;margin-top:10px}
.location-search button{padding:5px 10px;border:1px solid var(--ui-border,#d1d5db);border-radius:6px;background:var(--ui-surface,#fff);color:inherit;font-size:.8rem;cursor:pointer}
.location-search button.primary{border-color:var(--ui-primary,#2563eb);background:var(--ui-primary,#2563eb);color:var(--ui-on-primary,#fff)}
.location-search button:disabled{opacity:.6;cursor:default}
.location-search__error{margin:6px 0;color:var(--ui-danger,#dc2626);font-size:.82rem;font-weight:600}
.location-search__notice{margin:6px 0;color:var(--ui-success,#16a34a);font-size:.82rem;font-weight:600}
</style>
