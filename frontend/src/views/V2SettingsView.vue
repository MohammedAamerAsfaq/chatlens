<script setup>
import { onMounted, ref } from 'vue'
import { tradingApi } from '@/api'

const loading = ref(false)
const saving = ref(false)
const saved = ref(false)
const error = ref('')

const settings = ref({
  gatepass_mode: 'observational',
  pass2_candidate_max_distance: 0.55,
  exact_auto_match_max_distance: 0.45,
  pass2_candidates_per_line: 3,
  pass2_batch_max_items: 15,
  pass2_ai_timeout_seconds: 300,
})

async function loadSettings() {
  loading.value = true
  error.value = ''
  try {
    const { data } = await tradingApi.getV2MatchingSettings()
    Object.assign(settings.value, data)
  } catch (e) {
    error.value = e.response?.data?.detail || 'Failed to load V2 settings.'
  } finally {
    loading.value = false
  }
}

async function saveSettings() {
  saving.value = true
  saved.value = false
  error.value = ''
  try {
    const { data } = await tradingApi.setV2MatchingSettings(settings.value)
    settings.value = data
    saved.value = true
    setTimeout(() => { saved.value = false }, 2500)
  } catch (e) {
    error.value = e.response?.data?.detail || 'Failed to save V2 settings.'
  } finally {
    saving.value = false
  }
}

onMounted(loadSettings)
</script>

<template>
  <main class="v2-settings-page">
    <header class="page-header">
      <div>
        <h1>V2 Settings</h1>
        <p>Controls for V2 GatePass, inquiry extraction, candidate matching, batching, and timeout behavior.</p>
      </div>
      <button class="primary-btn" :disabled="saving || loading" @click="saveSettings">
        {{ saving ? 'Saving...' : 'Save Settings' }}
      </button>
    </header>

    <div v-if="error" class="alert error">{{ error }}</div>
    <div v-if="saved" class="alert success">Saved.</div>

    <section class="settings-grid">
      <article class="settings-card gatepass-card">
        <div>
          <h2>V2 GatePass</h2>
          <p>Classifies each message as buy, sell, or not inquiry before the existing V2 extraction pass.</p>
        </div>
        <label class="field">
          <span>Operating mode</span>
          <select v-model="settings.gatepass_mode">
            <option value="observational">Observational</option>
            <option value="enforced">Enforced</option>
          </select>
          <small v-if="settings.gatepass_mode === 'observational'">Records the GatePass decision but always continues the existing V2 pipeline.</small>
          <small v-else>Stops before extraction only when GatePass returns not_inquiry. Gate errors continue processing.</small>
        </label>
      </article>
      <article class="settings-card">
        <div>
          <h2>Distance Gates</h2>
          <p>Reject weak embedding candidate sets before AI matching and weak exact matches after AI matching.</p>
        </div>
        <label class="field">
          <span>Pass 2 candidate max distance</span>
          <input v-model.number="settings.pass2_candidate_max_distance" type="number" min="0" step="0.01" />
          <small>Reject candidate set before pass 2 when best distance is greater. Default: 0.55.</small>
        </label>
        <label class="field">
          <span>Exact auto-match max distance</span>
          <input v-model.number="settings.exact_auto_match_max_distance" type="number" min="0" step="0.01" />
          <small>Reject exact match acceptance after pass 2 when best distance is greater. Default: 0.45.</small>
        </label>
      </article>

      <article class="settings-card">
        <div>
          <h2>Pass 2 Payload Limits</h2>
          <p>Keep pass 2 smaller by limiting candidates per line and splitting large work into batches.</p>
        </div>
        <label class="field">
          <span>Candidates per product line</span>
          <input v-model.number="settings.pass2_candidates_per_line" type="number" min="1" step="1" />
          <small>Only this many ranked candidates are sent for each extracted product line. Default: 3.</small>
        </label>
        <label class="field">
          <span>Max product lines + distinct candidates per batch</span>
          <input v-model.number="settings.pass2_batch_max_items" type="number" min="1" step="1" />
          <small>When a pass 2 request would exceed this total, it is split into multiple AI calls. Default: 15.</small>
        </label>
      </article>

      <article class="settings-card">
        <div>
          <h2>Failure Handling</h2>
          <p>Fail loudly when a pass 2 AI request exceeds the configured runtime.</p>
        </div>
        <label class="field">
          <span>Pass 2 AI timeout seconds</span>
          <input v-model.number="settings.pass2_ai_timeout_seconds" type="number" min="1" step="1" />
          <small>Default: 300 seconds. Timed-out inquiries are marked error instead of staying pending.</small>
        </label>
      </article>
    </section>
  </main>
</template>

<style scoped>
.v2-settings-page { height: 100%; overflow: auto; padding: var(--ui-page-padding); color: var(--ui-text); background: var(--ui-bg); font-family: var(--ui-font-sans); }
.page-header { display: flex; justify-content: space-between; gap: 16px; align-items: flex-start; margin-bottom: 18px; }
.page-header h1 { color: var(--ui-text-strong); font-family: var(--ui-font-display); font-size: 1.5rem; font-weight: 700; margin: 0 0 4px; }
.page-header p { margin: 0; color: var(--ui-text-muted); }
.settings-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 16px; }
.settings-card { background: var(--ui-surface); border: 1px solid var(--ui-border); border-radius: var(--ui-radius-lg); padding: 18px; display: flex; flex-direction: column; gap: 16px; box-shadow: var(--ui-shadow-card); }
.settings-card h2 { margin: 0 0 4px; color: var(--ui-text-strong); font-size: 1rem; font-weight: 700; }
.settings-card p { margin: 0; color: var(--ui-text-muted); font-size: 0.88rem; line-height: 1.45; }
.field { display: flex; flex-direction: column; gap: 6px; }
.field span { font-size: 0.82rem; font-weight: 600; color: var(--ui-text); }
.field input, .field select { width: 220px; border: 1px solid var(--ui-border-strong); border-radius: var(--ui-radius-sm); padding: 8px 10px; color: var(--ui-text); font-size: 0.9rem; background: var(--ui-surface); }
.gatepass-card { border-top: 4px solid var(--ui-primary); }
.field small { color: var(--ui-text-muted); font-size: 0.78rem; line-height: 1.35; }
.primary-btn { border: 0; background: var(--ui-primary); color: var(--ui-on-primary); border-radius: var(--ui-radius-sm); padding: 9px 14px; font-weight: 700; cursor: pointer; }
.primary-btn:disabled { opacity: 0.6; cursor: not-allowed; }
.alert { border-radius: var(--ui-radius-sm); padding: 10px 12px; margin-bottom: 12px; font-size: 0.88rem; }
.alert.error { background: var(--ui-danger-soft); color: var(--ui-danger); border: 1px solid color-mix(in srgb,var(--ui-danger) 30%,var(--ui-border)); }
.alert.success { background: var(--ui-success-soft); color: var(--ui-success); border: 1px solid color-mix(in srgb,var(--ui-success) 30%,var(--ui-border)); }
</style>
