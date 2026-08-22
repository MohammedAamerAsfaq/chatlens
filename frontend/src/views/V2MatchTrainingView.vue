<script setup>
import { computed, onMounted, ref } from 'vue'
import { tradingApi } from '@/api'

const pool = ref('random')
const loading = ref(false)
const submitting = ref(false)
const error = ref('')
const done = ref(false)
const sample = ref(null)
const reviewedCount = ref(0)

const stats = ref(null)
const statsLoading = ref(false)

const POOLS = [
  { value: 'random', label: 'Random' },
  { value: 'rejected', label: 'Threshold-Rejected' },
  { value: 'passed', label: 'Passed Through' },
]

onMounted(() => {
  loadNext()
  loadStats()
})

function formatDistance(value) {
  if (value == null) return '-'
  return Number(value).toFixed(4)
}

// Stock as it was AT REVIEW TIME (from the original stored pass-2 prompt), not
// live Product.qty — current stock may have moved on since the message arrived,
// and the point is judging the match against what was actually available then.
function stockLabel(c) {
  if (!c.seen_in_original_candidates) return 'not retrieved originally'
  if (c.stock_status_at_review === 'in_stock') return `in stock (qty ${c.qty_at_review}) at review time`
  if (c.stock_status_at_review === 'out_of_stock') return 'out of stock at review time'
  return 'stock unknown at review time'
}

function stockClass(c) {
  if (!c.seen_in_original_candidates) return 'unknown'
  if (c.stock_status_at_review === 'in_stock') return 'in'
  if (c.stock_status_at_review === 'out_of_stock') return 'out'
  return 'unknown'
}

async function loadNext() {
  loading.value = true
  error.value = ''
  try {
    const { data } = await tradingApi.getNextV2TrainingSample({ pool: pool.value })
    if (data.done) {
      sample.value = null
      done.value = true
    } else {
      sample.value = data
      done.value = false
    }
  } catch (e) {
    error.value = e.response?.data?.detail || 'Failed to load next sample.'
  } finally {
    loading.value = false
  }
}

async function loadStats() {
  statsLoading.value = true
  try {
    const { data } = await tradingApi.getV2TrainingStats()
    stats.value = data
  } catch {
    // non-critical — the review flow works without stats
  } finally {
    statsLoading.value = false
  }
}

function setPool(value) {
  if (pool.value === value) return
  pool.value = value
  loadNext()
}

async function submitVerdict(correctProductId) {
  if (!sample.value || submitting.value) return
  submitting.value = true
  error.value = ''
  try {
    await tradingApi.submitV2TrainingSample({
      message_id: sample.value.message_id,
      line_index: sample.value.line_index,
      query_text: sample.value.query_text,
      ai_product_id: sample.value.ai_product_id,
      ai_match_type: sample.value.ai_match_type,
      candidates: sample.value.candidates,
      correct_product_id: correctProductId,
    })
    reviewedCount.value += 1
    await loadNext()
    loadStats()
  } catch (e) {
    error.value = e.response?.data?.detail || 'Failed to save verdict.'
  } finally {
    submitting.value = false
  }
}

// Chart geometry — SVG scatter of best_distance vs whether the nearest candidate
// was actually correct, with the live pass2_candidate_max_distance /
// exact_auto_match_max_distance settings drawn as reference lines.
const CHART_WIDTH = 640
const CHART_HEIGHT = 220
const CHART_PAD_LEFT = 40
const CHART_PAD_BOTTOM = 28
const CHART_PAD_TOP = 14
const CHART_PAD_RIGHT = 14

const chartDomainMax = computed(() => {
  const rows = stats.value?.samples || []
  const max = rows.reduce((m, r) => (r.distance != null && r.distance > m ? r.distance : m), 0.6)
  return Math.ceil((max + 0.05) * 10) / 10
})

function xScale(distance) {
  const usableWidth = CHART_WIDTH - CHART_PAD_LEFT - CHART_PAD_RIGHT
  return CHART_PAD_LEFT + (distance / chartDomainMax.value) * usableWidth
}

const chartPoints = computed(() => {
  const rows = stats.value?.samples || []
  const usableHeight = CHART_HEIGHT - CHART_PAD_TOP - CHART_PAD_BOTTOM
  return rows
    .filter(r => r.distance != null)
    .map((r, i) => ({
      x: xScale(r.distance),
      // Jitter y within a fixed band per outcome so overlapping points stay visible.
      y: CHART_PAD_TOP + (r.top_candidate_correct ? usableHeight * 0.28 : usableHeight * 0.72) + (((i * 37) % 21) - 10),
      correct: r.top_candidate_correct,
      distance: r.distance,
    }))
})

const xTicks = computed(() => {
  const max = chartDomainMax.value
  const step = max <= 0.6 ? 0.1 : 0.2
  const ticks = []
  for (let v = 0; v <= max + 0.0001; v += step) ticks.push(Math.round(v * 100) / 100)
  return ticks
})

const thresholdLines = computed(() => {
  const s = stats.value?.settings
  if (!s) return []
  return [
    { value: s.exact_auto_match_max_distance, label: 'exact cutoff', color: '#2a78d6' },
    { value: s.pass2_candidate_max_distance, label: 'candidate cutoff', color: '#eb6834' },
  ]
})
</script>

<template>
  <main class="training-page">
    <header class="page-header">
      <div>
        <h1>V2 Match Training</h1>
        <p>Review real past inquiry lines against fresh candidate retrieval to calibrate the pass-2 distance thresholds.</p>
      </div>
      <div class="pool-tabs">
        <button
          v-for="p in POOLS"
          :key="p.value"
          class="pool-tab"
          :class="{ active: pool === p.value }"
          @click="setPool(p.value)"
        >{{ p.label }}</button>
      </div>
    </header>

    <div v-if="error" class="alert error">{{ error }}</div>

    <section class="review-card">
      <div v-if="loading" class="empty">Loading next sample...</div>
      <div v-else-if="done" class="empty">No more unreviewed samples in this pool right now.</div>
      <template v-else-if="sample">
        <div class="message-box">
          <div class="message-label">Original message</div>
          <pre>{{ sample.message_text }}</pre>
        </div>

        <div class="line-meta">
          <div>
            <div class="line-label">Extracted line</div>
            <div class="line-value">{{ sample.query_text }}</div>
          </div>
          <div>
            <div class="line-label">AI's original decision</div>
            <div class="line-value">
              {{ sample.ai_product_id ? `Product #${sample.ai_product_id} (${sample.ai_match_type})` : 'No match' }}
            </div>
            <div class="muted">{{ sample.ai_match_reason }}</div>
            <button class="ai-correct-btn" :disabled="submitting" @click="submitVerdict(sample.ai_product_id)">
              AI Decision was Correct
            </button>
          </div>
        </div>

        <div class="candidate-list">
          <div v-if="!sample.candidates.length" class="empty small">No candidates retrieved for this line.</div>
          <div v-for="(c, i) in sample.candidates" :key="c.product_id" class="candidate-row">
            <span class="rank">{{ i + 1 }}</span>
            <div class="candidate-main">
              <strong>#{{ c.product_id }} {{ c.name }}</strong>
              <span class="muted">
                {{ c.brand }} · distance {{ formatDistance(c.distance) }} ·
                <span class="stock-pill" :class="stockClass(c)">{{ stockLabel(c) }}</span>
              </span>
            </div>
            <button class="correct-btn" :disabled="submitting" @click="submitVerdict(c.product_id)">This is correct</button>
          </div>
        </div>

        <div class="verdict-actions">
          <button class="none-btn" :disabled="submitting" @click="submitVerdict(null)">None of these are correct</button>
        </div>
      </template>
    </section>

    <section class="stats-card">
      <div class="stats-head">
        <h2>Calibration data</h2>
        <span class="muted">{{ stats?.total ?? 0 }} reviewed this session</span>
      </div>
      <div v-if="statsLoading" class="empty small">Loading stats...</div>
      <template v-else-if="stats && stats.total">
        <svg class="viz-root" :viewBox="`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`" role="img" aria-label="Distance vs match correctness scatter plot">
          <line
            v-for="t in xTicks" :key="`grid-${t}`"
            :x1="xScale(t)" :x2="xScale(t)" :y1="CHART_PAD_TOP" :y2="CHART_HEIGHT - CHART_PAD_BOTTOM"
            stroke="#e1e0d9" stroke-width="1"
          />
          <text
            v-for="t in xTicks" :key="`tick-${t}`"
            :x="xScale(t)" :y="CHART_HEIGHT - 8" text-anchor="middle" font-size="10" fill="#898781"
          >{{ t.toFixed(2) }}</text>

          <g v-for="tl in thresholdLines" :key="tl.label">
            <line
              :x1="xScale(tl.value)" :x2="xScale(tl.value)" :y1="CHART_PAD_TOP" :y2="CHART_HEIGHT - CHART_PAD_BOTTOM"
              :stroke="tl.color" stroke-width="2" stroke-dasharray="4,3"
            />
            <text :x="xScale(tl.value) + 4" :y="CHART_PAD_TOP + 10" font-size="10" :fill="tl.color">{{ tl.label }} {{ tl.value }}</text>
          </g>

          <circle
            v-for="(p, i) in chartPoints" :key="i"
            :cx="p.x" :cy="p.y" r="4.5"
            :fill="p.correct ? '#0ca30c' : '#d03b3b'" fill-opacity="0.75"
          />
        </svg>
        <div class="legend">
          <span class="legend-item"><span class="swatch" style="background:#0ca30c" /> Nearest candidate was correct</span>
          <span class="legend-item"><span class="swatch" style="background:#d03b3b" /> Nearest candidate was wrong / no match</span>
        </div>

        <table class="stats-table">
          <thead>
            <tr><th>Best distance</th><th>Nearest candidate correct?</th><th>AI decision matched human?</th></tr>
          </thead>
          <tbody>
            <tr v-for="(r, i) in stats.samples" :key="i">
              <td>{{ formatDistance(r.distance) }}</td>
              <td>{{ r.top_candidate_correct ? 'Yes' : 'No' }}</td>
              <td>{{ r.ai_was_right ? 'Yes' : 'No' }}</td>
            </tr>
          </tbody>
        </table>
      </template>
      <div v-else class="empty small">No samples reviewed yet — verdicts will appear here as you go.</div>
    </section>
  </main>
</template>

<style scoped>
.training-page { height: 100%; overflow: auto; padding: 24px; color: #0b0b0b; background: #f9f9f7; }
.page-header { display: flex; justify-content: space-between; gap: 16px; align-items: flex-start; margin-bottom: 18px; flex-wrap: wrap; }
.page-header h1 { margin: 0 0 4px; font-size: 1.5rem; font-weight: 700; }
.page-header p { margin: 0; color: #52514e; max-width: 560px; }
.pool-tabs { display: flex; gap: 6px; }
.pool-tab { border: 1px solid #c3c2b7; background: #fff; border-radius: 999px; padding: 7px 14px; font-size: 0.82rem; font-weight: 600; cursor: pointer; color: #52514e; }
.pool-tab.active { background: #2a78d6; border-color: #2a78d6; color: #fff; }
.alert { border-radius: 8px; padding: 10px 12px; margin-bottom: 14px; font-size: 0.88rem; }
.alert.error { background: #fef2f2; color: #991b1b; border: 1px solid #fecaca; }
.review-card, .stats-card { background: #fcfcfb; border: 1px solid #e1e0d9; border-radius: 12px; padding: 18px; margin-bottom: 16px; }
.empty { padding: 36px; text-align: center; color: #898781; }
.empty.small { padding: 16px; }
.message-box { background: #f9f9f7; border: 1px solid #e1e0d9; border-radius: 8px; padding: 12px; margin-bottom: 14px; max-height: 180px; overflow: auto; }
.message-label, .line-label { font-size: 0.72rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; color: #898781; margin-bottom: 4px; }
.message-box pre { margin: 0; white-space: pre-wrap; font-family: inherit; font-size: 0.86rem; }
.line-meta { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px; }
.line-value { font-size: 0.92rem; font-weight: 600; }
.ai-correct-btn { margin-top: 8px; border: 1px solid #2a78d6; background: #eff6ff; color: #184f95; border-radius: 8px; padding: 6px 12px; font-weight: 700; font-size: 0.78rem; cursor: pointer; }
.ai-correct-btn:disabled { opacity: 0.6; cursor: not-allowed; }
.muted { color: #52514e; font-size: 0.78rem; }
.candidate-list { display: flex; flex-direction: column; gap: 8px; margin-bottom: 14px; }
.candidate-row { display: flex; align-items: center; gap: 12px; border: 1px solid #e1e0d9; border-radius: 8px; padding: 10px 12px; }
.rank { width: 22px; height: 22px; border-radius: 999px; background: #f0efec; display: grid; place-items: center; font-size: 0.76rem; font-weight: 700; flex-shrink: 0; }
.candidate-main { flex: 1; display: flex; flex-direction: column; gap: 2px; }
.stock-pill { display: inline-flex; border-radius: 999px; padding: 1px 8px; font-size: 0.72rem; font-weight: 700; }
.stock-pill.in { background: #eafbea; color: #006300; }
.stock-pill.out { background: #fef2f2; color: #991b1b; }
.stock-pill.unknown { background: #f0efec; color: #52514e; }
.correct-btn { border: 1px solid #0ca30c; background: #eafbea; color: #006300; border-radius: 8px; padding: 7px 12px; font-weight: 700; font-size: 0.8rem; cursor: pointer; }
.correct-btn:disabled { opacity: 0.6; cursor: not-allowed; }
.verdict-actions { display: flex; justify-content: flex-end; }
.none-btn { border: 1px solid #d03b3b; background: #fef2f2; color: #991b1b; border-radius: 8px; padding: 9px 16px; font-weight: 700; font-size: 0.85rem; cursor: pointer; }
.none-btn:disabled { opacity: 0.6; cursor: not-allowed; }
.stats-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.stats-head h2 { margin: 0; font-size: 1.05rem; }
.viz-root { width: 100%; height: auto; }
.legend { display: flex; gap: 18px; margin: 10px 0 16px; }
.legend-item { display: inline-flex; align-items: center; gap: 6px; font-size: 0.8rem; color: #52514e; }
.swatch { width: 10px; height: 10px; border-radius: 2px; display: inline-block; }
.stats-table { width: 100%; border-collapse: collapse; font-size: 0.82rem; }
.stats-table th { text-align: left; padding: 8px 10px; color: #898781; font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.04em; border-bottom: 1px solid #e1e0d9; }
.stats-table td { padding: 8px 10px; border-bottom: 1px solid #f0efec; }
@media (max-width: 800px) {
  .line-meta { grid-template-columns: 1fr; }
}
</style>
