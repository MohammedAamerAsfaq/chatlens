<script setup>
import { onMounted, ref } from 'vue'
import { tradingApi } from '@/api'

const loading = ref(false)
const saving = ref(false)
const saved = ref(false)
const error = ref('')

const settings = ref({
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
        <p>Controls for V2 inquiry extraction, candidate matching, batching, and timeout behavior.</p>
      </div>
      <button class="primary-btn" :disabled="saving || loading" @click="saveSettings">
        {{ saving ? 'Saving...' : 'Save Settings' }}
      </button>
    </header>

    <div v-if="error" class="alert error">{{ error }}</div>
    <div v-if="saved" class="alert success">Saved.</div>

    <section class="settings-grid">
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
.v2-settings-page { height: 100%; overflow: auto; padding: 24px; color: #111827; }
.page-header { display: flex; justify-content: space-between; gap: 16px; align-items: flex-start; margin-bottom: 18px; }
.page-header h1 { font-size: 1.5rem; font-weight: 700; margin: 0 0 4px; }
.page-header p { margin: 0; color: #64748b; }
.settings-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 16px; }
.settings-card { background: #fff; border: 1px solid #e5e7eb; border-radius: 12px; padding: 18px; display: flex; flex-direction: column; gap: 16px; box-shadow: 0 1px 2px rgba(15,23,42,0.04); }
.settings-card h2 { margin: 0 0 4px; font-size: 1rem; font-weight: 700; }
.settings-card p { margin: 0; color: #64748b; font-size: 0.88rem; line-height: 1.45; }
.field { display: flex; flex-direction: column; gap: 6px; }
.field span { font-size: 0.82rem; font-weight: 600; color: #334155; }
.field input { width: 180px; border: 1px solid #cbd5e1; border-radius: 8px; padding: 8px 10px; font-size: 0.9rem; }
.field small { color: #64748b; font-size: 0.78rem; line-height: 1.35; }
.primary-btn { border: 0; background: #16a34a; color: #fff; border-radius: 8px; padding: 9px 14px; font-weight: 700; cursor: pointer; }
.primary-btn:disabled { opacity: 0.6; cursor: not-allowed; }
.alert { border-radius: 8px; padding: 10px 12px; margin-bottom: 12px; font-size: 0.88rem; }
.alert.error { background: #fef2f2; color: #991b1b; border: 1px solid #fecaca; }
.alert.success { background: #f0fdf4; color: #166534; border: 1px solid #bbf7d0; }
</style>
