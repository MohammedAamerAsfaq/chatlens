<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { taskQueueApi } from '@/api'

const overview = ref({ queues: [], workers: [], schedules: [] })
const tasks = ref([])
const total = ref(0)
const selectedTask = ref(null)
const loading = ref(false)
const loadingDetail = ref(false)
const error = ref('')
const filters = ref({ queue: '', status: '', task_key: '', correlation_id: '' })
let timer = null

const taskStatuses = ['pending', 'claimed', 'running', 'retrying', 'succeeded', 'failed', 'cancelled']
const liveStatuses = new Set(['pending', 'claimed', 'running', 'retrying'])
const queueNames = computed(() => overview.value.queues.map(queue => queue.name))
const activeWork = computed(() => overview.value.queues.reduce((sum, queue) => (
  sum + (queue.counts.pending || 0) + (queue.counts.claimed || 0) + (queue.counts.running || 0) + (queue.counts.retrying || 0)
), 0))
const failedWork = computed(() => overview.value.queues.reduce((sum, queue) => sum + (queue.counts.failed || 0), 0))
const liveWorkers = computed(() => overview.value.workers.filter(worker => worker.status === 'running').length)

function requestParams() {
  const params = { limit: 150 }
  for (const [key, value] of Object.entries(filters.value)) {
    if (value) params[key] = value
  }
  return params
}

async function refresh(showLoading = false) {
  if (showLoading) loading.value = true
  error.value = ''
  try {
    const [overviewResponse, tasksResponse] = await Promise.all([
      taskQueueApi.overview(),
      taskQueueApi.tasks(requestParams()),
    ])
    overview.value = overviewResponse.data
    tasks.value = tasksResponse.data.results
    total.value = tasksResponse.data.count
    if (selectedTask.value && !tasks.value.some(task => task.id === selectedTask.value.id)) {
      selectedTask.value = null
    }
  } catch (requestError) {
    error.value = requestError.response?.data?.detail || 'Unable to load task operations data.'
  } finally {
    loading.value = false
  }
}

async function selectTask(task) {
  if (selectedTask.value?.id === task.id) {
    selectedTask.value = null
    return
  }
  loadingDetail.value = true
  try {
    const { data } = await taskQueueApi.task(task.id)
    selectedTask.value = data
  } catch (requestError) {
    error.value = requestError.response?.data?.detail || `Unable to load task ${task.id}.`
  } finally {
    loadingDetail.value = false
  }
}

function formatDate(value) {
  return value ? new Date(value).toLocaleString() : '-'
}

function age(value) {
  if (!value) return '-'
  const seconds = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 1000))
  if (seconds < 60) return `${seconds}s`
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h`
  return `${Math.floor(seconds / 86400)}d`
}

function duration(task) {
  if (!task.started_at) return '-'
  const end = task.finished_at || new Date().toISOString()
  const seconds = Math.max(0, Math.round((new Date(end) - new Date(task.started_at)) / 1000))
  return seconds < 60 ? `${seconds}s` : `${Math.floor(seconds / 60)}m ${seconds % 60}s`
}

function statusClass(status) {
  return `status status-${status}`
}

function taskSummary(task) {
  if (task.last_error) return task.last_error
  if (task.status === 'succeeded') return 'Completed successfully.'
  if (task.status === 'retrying') return `Retry ${task.attempts} of ${task.max_attempts} waiting until ${formatDate(task.available_at)}.`
  if (task.status === 'running') return 'Handler is executing.'
  if (task.status === 'claimed') return `Claimed by ${task.locked_by || 'worker'}.`
  return 'Waiting for a worker.'
}

watch(filters, () => refresh(), { deep: true })
onMounted(() => {
  refresh(true)
  timer = setInterval(() => refresh(), 5000)
})
onUnmounted(() => clearInterval(timer))
</script>

<template>
  <main class="task-operations-view">
    <header class="operations-head">
      <div>
        <p class="eyebrow">Durable Execution</p>
        <h1>Task Operations</h1>
        <p class="subtitle">Live queue, worker, scheduler, and execution feedback. Refreshes every 5 seconds.</p>
      </div>
      <button class="refresh-button" :disabled="loading" @click="refresh(true)">
        {{ loading ? 'Refreshing...' : 'Refresh now' }}
      </button>
    </header>

    <p v-if="error" class="error-banner">{{ error }}</p>

    <section class="headline-metrics" aria-label="Task summary">
      <article class="metric-card metric-active"><span>Active work</span><strong>{{ activeWork }}</strong><small>pending, claimed, running, retrying</small></article>
      <article class="metric-card metric-failed"><span>Failed tasks</span><strong>{{ failedWork }}</strong><small>requires review or manual retry</small></article>
      <article class="metric-card metric-worker"><span>Live workers</span><strong>{{ liveWorkers }}</strong><small>{{ overview.workers.length }} registered</small></article>
      <article class="metric-card metric-schedule"><span>Active schedules</span><strong>{{ overview.schedules.filter(schedule => schedule.is_active).length }}</strong><small>scheduler only enqueues work</small></article>
    </section>

    <section class="queue-grid" aria-label="Queue health">
      <article v-for="queue in overview.queues" :key="queue.name" class="queue-card" :class="{ paused: queue.is_paused, disabled: !queue.is_enabled }">
        <div class="queue-title"><h2>{{ queue.display_name }}</h2><span :class="queue.is_enabled && !queue.is_paused ? 'queue-live' : 'queue-stopped'">{{ !queue.is_enabled ? 'Disabled' : queue.is_paused ? 'Paused' : 'Ready' }}</span></div>
        <div class="queue-counts"><span><b>{{ queue.counts.pending || 0 }}</b> pending</span><span><b>{{ queue.counts.running || 0 }}</b> running</span><span><b>{{ queue.counts.retrying || 0 }}</b> retrying</span><span :class="{ alert: queue.counts.failed }"><b>{{ queue.counts.failed || 0 }}</b> failed</span></div>
        <footer>Oldest pending: <strong>{{ queue.oldest_pending_age_seconds == null ? '-' : age(new Date(Date.now() - queue.oldest_pending_age_seconds * 1000).toISOString()) }}</strong></footer>
      </article>
    </section>

    <section class="operations-split">
      <article class="operations-panel workers-panel">
        <div class="panel-title"><div><p class="eyebrow">Worker Registry</p><h2>Workers</h2></div><span>{{ overview.workers.length }}</span></div>
        <div v-if="!overview.workers.length" class="empty-state">No task worker has registered yet. Start the worker service before enabling queue mode.</div>
        <div v-for="worker in overview.workers" :key="worker.worker_id" class="worker-row">
          <span :class="statusClass(worker.status)">{{ worker.status }}</span>
          <div><strong>{{ worker.worker_id }}</strong><small>{{ worker.hostname }} · PID {{ worker.process_id }}</small></div>
          <div class="worker-meta"><small>{{ worker.queue_names.join(', ') }}</small><small>Heartbeat {{ age(worker.last_heartbeat_at) }} ago</small></div>
        </div>
      </article>

      <article class="operations-panel schedule-panel">
        <div class="panel-title"><div><p class="eyebrow">Task Scheduler</p><h2>Schedules</h2></div><span>{{ overview.schedules.length }}</span></div>
        <div v-if="!overview.schedules.length" class="empty-state">No schedules configured. This is normal until recurring maintenance or reports are enabled.</div>
        <div v-for="schedule in overview.schedules" :key="schedule.id" class="schedule-row">
          <span :class="schedule.is_active ? 'schedule-dot active' : 'schedule-dot'"></span>
          <div><strong>{{ schedule.name }}</strong><small>{{ schedule.task_key }} · {{ schedule.queue_name }}</small></div>
          <div class="schedule-time"><small>Next {{ formatDate(schedule.next_run_at) }}</small><small v-if="schedule.last_error" class="error-text">{{ schedule.last_error }}</small></div>
        </div>
      </article>
    </section>

    <section class="task-panel">
      <div class="task-panel-head">
        <div><p class="eyebrow">Execution Ledger</p><h2>Background Tasks <span>{{ total }}</span></h2></div>
        <div class="task-filters">
          <select v-model="filters.queue"><option value="">All queues</option><option v-for="queue in queueNames" :key="queue" :value="queue">{{ queue }}</option></select>
          <select v-model="filters.status"><option value="">All statuses</option><option v-for="status in taskStatuses" :key="status" :value="status">{{ status }}</option></select>
          <input v-model.trim="filters.task_key" placeholder="Task key" />
          <input v-model.trim="filters.correlation_id" placeholder="Correlation ID" />
        </div>
      </div>

      <div class="task-table-wrap">
        <table class="task-table">
          <thead><tr><th>Task</th><th>Queue</th><th>State</th><th>Attempts</th><th>Worker / timing</th><th>Feedback</th></tr></thead>
          <tbody>
            <tr v-if="!tasks.length"><td colspan="6" class="empty-cell">No tasks match the selected filters.</td></tr>
            <tr v-for="task in tasks" :key="task.id" :class="{ selected: selectedTask?.id === task.id }" @click="selectTask(task)">
              <td><strong>#{{ task.id }}</strong><span>{{ task.task_key }}</span><small>{{ age(task.created_at) }} ago · {{ task.company_name || 'system' }}</small></td>
              <td>{{ task.queue_name }}</td>
              <td><span :class="statusClass(task.status)">{{ task.status }}</span></td>
              <td>{{ task.attempts }} / {{ task.max_attempts }}</td>
              <td><span>{{ task.locked_by || '-' }}</span><small>{{ duration(task) }}</small></td>
              <td class="feedback-cell" :class="{ failure: task.status === 'failed' }">{{ taskSummary(task) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section v-if="selectedTask" class="detail-panel">
      <div class="detail-head"><div><p class="eyebrow">Task Detail</p><h2>#{{ selectedTask.id }} · {{ selectedTask.task_key }}</h2></div><button @click="selectedTask = null">Close</button></div>
      <p v-if="loadingDetail">Loading task events...</p>
      <div v-else class="detail-grid">
        <div class="detail-summary"><span :class="statusClass(selectedTask.status)">{{ selectedTask.status }}</span><p>{{ taskSummary(selectedTask) }}</p><dl><dt>Correlation</dt><dd>{{ selectedTask.correlation_id }}</dd><dt>Idempotency</dt><dd>{{ selectedTask.idempotency_key || '-' }}</dd><dt>Available</dt><dd>{{ formatDate(selectedTask.available_at) }}</dd></dl></div>
        <div class="timeline"><h3>Task Event Log</h3><div v-for="event in selectedTask.events" :key="event.id" class="timeline-event"><span class="timeline-dot"></span><div><strong>{{ event.event_type.replaceAll('_', ' ') }}</strong><small>{{ formatDate(event.created_at) }} · attempt {{ event.attempt_number }}{{ event.worker_id ? ` · ${event.worker_id}` : '' }}</small><p v-if="event.message">{{ event.message }}</p><pre v-if="event.error">{{ event.error }}</pre></div></div></div>
      </div>
      <details><summary>Payload and result</summary><div class="payload-grid"><pre>{{ JSON.stringify(selectedTask.payload, null, 2) }}</pre><pre>{{ JSON.stringify(selectedTask.result, null, 2) }}</pre></div></details>
      <details v-if="selectedTask.last_traceback"><summary>Latest traceback</summary><pre class="traceback">{{ selectedTask.last_traceback }}</pre></details>
    </section>
  </main>
</template>

<style scoped>
.task-operations-view { min-height: 100%; overflow: auto; padding: 30px; background: radial-gradient(circle at 90% 0%, #e2f8ed 0, transparent 28rem), #f6f7f4; color: #18231e; }
.operations-head, .task-panel-head, .detail-head, .panel-title, .queue-title { display: flex; align-items: center; justify-content: space-between; gap: 18px; }
.eyebrow { margin: 0 0 5px; color: #558568; text-transform: uppercase; letter-spacing: .12em; font-size: .68rem; font-weight: 800; }
h1, h2, h3, p { margin-top: 0; } h1 { margin-bottom: 6px; font-size: 2rem; letter-spacing: -.045em; } h2 { margin-bottom: 0; font-size: 1.05rem; } .subtitle { margin-bottom: 0; color: #65736a; }
.refresh-button, .detail-head button { border: 0; background: #175c3b; color: white; padding: 10px 14px; border-radius: 8px; font-weight: 700; cursor: pointer; } .refresh-button:disabled { opacity: .6; cursor: wait; }
.error-banner { margin: 18px 0; padding: 11px 14px; color: #8d2822; background: #ffe9e6; border-left: 4px solid #d64e43; }
.headline-metrics { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin: 26px 0 14px; }.metric-card { padding: 17px; border-radius: 12px; background: white; box-shadow: 0 8px 25px rgba(38, 61, 47, .07); border-top: 4px solid #94b8a3; }.metric-card span, .metric-card small, .worker-row small, .schedule-row small, td small { display: block; color: #6a796f; font-size: .74rem; }.metric-card strong { display: block; font: 700 1.8rem Georgia, serif; margin: 5px 0; }.metric-failed { border-color: #da6257; }.metric-active { border-color: #289161; }.metric-worker { border-color: #4e81aa; }.metric-schedule { border-color: #be8a34; }
.queue-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 12px; }.queue-card, .operations-panel, .task-panel, .detail-panel { background: rgba(255,255,255,.92); border: 1px solid #e0e6df; border-radius: 12px; box-shadow: 0 7px 20px rgba(35, 58, 43, .05); }.queue-card { padding: 16px; }.queue-card.paused, .queue-card.disabled { background: #fbf8ef; }.queue-title h2 { text-transform: capitalize; }.queue-live, .queue-stopped { font-size: .68rem; font-weight: 800; text-transform: uppercase; color: #1b7d4b; }.queue-stopped { color: #a35c22; }.queue-counts { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin: 15px 0; color: #65736a; font-size: .77rem; }.queue-counts b { color: #1f2d24; }.queue-counts .alert b { color: #c13b32; }.queue-card footer { color: #69776e; font-size: .75rem; }
.operations-split { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin: 14px 0; }.operations-panel { padding: 17px; }.panel-title > span { background: #eaf2eb; color: #286143; padding: 3px 8px; border-radius: 999px; font-size: .75rem; font-weight: 800; }.worker-row, .schedule-row { display: grid; grid-template-columns: auto 1fr auto; align-items: center; gap: 10px; padding: 12px 0; border-top: 1px solid #eef1ed; }.worker-row strong, .schedule-row strong { display:block; font-size: .82rem; word-break: break-all; }.worker-meta, .schedule-time { text-align: right; }.error-text { color: #b53c34 !important; max-width: 170px; }.empty-state, .empty-cell { color: #78847c; padding: 20px 0; font-size: .84rem; }.schedule-dot { width: 9px; height: 9px; border-radius: 99px; background: #aeb8b0; }.schedule-dot.active { background: #d69e36; box-shadow: 0 0 0 4px #fff3d9; }
.task-panel { margin-top: 14px; }.task-panel-head { padding: 18px; border-bottom: 1px solid #e6ebe6; }.task-panel-head h2 span { color: #66806f; font-size: .8rem; }.task-filters { display: flex; flex-wrap: wrap; gap: 7px; }.task-filters input, .task-filters select { border: 1px solid #d6ded7; background: #fafcf9; padding: 8px 9px; font-size: .78rem; border-radius: 7px; color: #314137; }.task-table-wrap { overflow: auto; }.task-table { width: 100%; border-collapse: collapse; font-size: .79rem; min-width: 900px; }.task-table th { text-align: left; color: #728076; text-transform: uppercase; font-size: .65rem; letter-spacing: .07em; padding: 10px 14px; background: #f8faf7; }.task-table td { padding: 12px 14px; border-top: 1px solid #edf0ec; vertical-align: top; }.task-table tbody tr { cursor: pointer; }.task-table tbody tr:hover, .task-table tbody tr.selected { background: #f0f8f2; }.task-table td strong, .task-table td span { display: block; }.task-table td > strong { color: #2a4434; }.feedback-cell { max-width: 350px; color: #526258; }.feedback-cell.failure { color: #a9332c; }.empty-cell { text-align: center; }
.status { display: inline-block !important; border-radius: 999px; padding: 3px 8px; font-size: .66rem; font-weight: 800; text-transform: uppercase; letter-spacing: .04em; }.status-pending, .status-retrying { background: #fff2cf; color: #8e6112; }.status-claimed, .status-running { background: #dceefb; color: #21628f; }.status-succeeded { background: #ddf3e4; color: #1b7240; }.status-failed { background: #ffe1dd; color: #a72f28; }.status-cancelled, .status-stopped, .status-unhealthy { background: #e8ebea; color: #59675f; }
.detail-panel { margin-top: 14px; padding: 20px; border-top: 4px solid #1e7148; }.detail-head button { background: #f1f4f1; color: #425348; }.detail-grid { display: grid; grid-template-columns: minmax(230px, .7fr) 2fr; gap: 26px; margin: 18px 0; }.detail-summary p { color: #4c5e52; }.detail-summary dl { display:grid; grid-template-columns: 90px 1fr; gap: 8px; font-size: .78rem; }.detail-summary dt { color:#78867c; }.detail-summary dd { margin:0; word-break:break-all; }.timeline h3 { font-size:.9rem; }.timeline-event { display:flex; gap:12px; position:relative; padding: 0 0 17px; }.timeline-event:not(:last-child)::before { content:''; position:absolute; left:4px; top:10px; bottom:-2px; border-left:1px solid #d3ddd5; }.timeline-dot { width:9px; height:9px; border-radius:50%; background:#2c8e5c; margin-top:4px; flex:0 0 auto; }.timeline-event strong, .timeline-event small { display:block; }.timeline-event small { color:#718077; font-size:.7rem; }.timeline-event p { margin:5px 0 0; font-size:.78rem; }.timeline-event pre, pre { white-space: pre-wrap; overflow-wrap:anywhere; background:#f5f7f4; padding:10px; border-radius:6px; font-size:.7rem; color:#7f2924; }.payload-grid { display:grid; grid-template-columns:1fr 1fr; gap:12px; }.payload-grid pre { color:#2a4234; }.traceback { max-height:360px; overflow:auto; } details { margin-top:14px; } summary { cursor:pointer; font-weight:700; color:#315542; }
@media (max-width: 900px) { .task-operations-view { padding:18px; }.headline-metrics, .operations-split, .detail-grid { grid-template-columns: 1fr 1fr; }.detail-grid { grid-template-columns:1fr; }.operations-head, .task-panel-head { align-items:flex-start; flex-direction:column; }.worker-row, .schedule-row { grid-template-columns:auto 1fr; }.worker-meta, .schedule-time { grid-column:2; text-align:left; }.payload-grid { grid-template-columns:1fr; } }
@media (max-width: 560px) { .headline-metrics { grid-template-columns:1fr 1fr; }.operations-split { grid-template-columns:1fr; } h1 { font-size:1.65rem; } }
</style>
