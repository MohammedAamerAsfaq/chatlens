<script setup>
import { onMounted, ref } from 'vue'
import { taskQueueApi } from '@/api'

const queues = ref([])
const runtime = ref({ automation_mode: 'thread', embedding_mode: 'thread', classification_mode: 'thread', recovery_mode: 'thread', worker_heartbeat_seconds: 15, scheduler_interval_seconds: 5 })
const loading = ref(false)
const saving = ref(false)
const saved = ref(false)
const error = ref('')

async function load() {
  loading.value = true
  try {
    const { data } = await taskQueueApi.settings()
    queues.value = data.queues; runtime.value = data.runtime
  } catch (e) {
    error.value = e.response?.data?.detail || 'Failed to load task settings.'
  } finally { loading.value = false }
}

async function save() {
  saving.value = true; saved.value = false; error.value = ''
  try {
    const { data } = await taskQueueApi.saveSettings({ queues: queues.value, runtime: runtime.value })
    queues.value = data.queues; runtime.value = data.runtime; saved.value = true
  } catch (e) {
    error.value = e.response?.data?.detail || 'Failed to save task settings.'
  } finally { saving.value = false }
}

onMounted(load)
</script>

<template>
  <main class="page task-queue-settings-page">
    <header><div><h1>Task &amp; Queues</h1><p>Control parallel background work and the maximum runtime for every task in each queue.</p></div><button :disabled="loading || saving" @click="save">{{ saving ? 'Saving...' : 'Save Settings' }}</button></header>
    <p v-if="error" class="error">{{ error }}</p><p v-if="saved" class="saved">Saved. Running workers use the new limits on their next poll.</p>
    <section v-if="!loading" class="grid"><article><h2>Runtime Modes</h2><code>Database controlled</code><label v-for="field in ['automation_mode','embedding_mode','classification_mode','recovery_mode']" :key="field">{{ field.replaceAll('_', ' ') }}<select v-model="runtime[field]"><option value="thread">Thread</option><option value="db_queue">DB queue</option></select></label><label>Worker heartbeat (seconds)<input v-model.number="runtime.worker_heartbeat_seconds" type="number" min="1" max="300"></label><label>Scheduler interval (seconds)<input v-model.number="runtime.scheduler_interval_seconds" type="number" min="1" max="300"></label></article><article v-for="queue in queues" :key="queue.name"><h2>{{ queue.display_name }}</h2><code>{{ queue.name }}</code><label>Concurrent tasks<input v-model.number="queue.max_concurrency" type="number" min="1" max="64"></label><small>Tasks may run in parallel up to this limit.</small><label>Task timeout (seconds)<input v-model.number="queue.task_timeout_seconds" type="number" min="30" max="7200"></label><small>Default: 300 seconds. On timeout the task is retried and its queue slot is released.</small></article></section>
  </main>
</template>

<style scoped>
.page{height:100%;overflow:auto;padding:var(--ui-page-padding);color:var(--ui-text);background:var(--ui-bg);font-family:var(--ui-font-sans)}header{display:flex;justify-content:space-between;gap:18px;align-items:flex-start;margin-bottom:20px}h1{margin:0;color:var(--ui-text-strong);font:700 1.65rem var(--ui-font-display)}header p{margin:6px 0 0;color:var(--ui-text-muted);max-width:620px}button{border:0;border-radius:var(--ui-radius-sm);background:var(--ui-primary);color:var(--ui-on-primary);padding:10px 15px;font-weight:700;cursor:pointer}button:hover{background:var(--ui-primary-hover)}button:disabled{opacity:.6}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px}article{background:var(--ui-surface);border:1px solid var(--ui-border);border-radius:var(--ui-radius-lg);padding:18px;box-shadow:var(--ui-shadow-card)}h2{margin:0 0 3px;color:var(--ui-text-strong);font-size:1rem}code{color:var(--ui-text-muted);font-size:.78rem}label{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-top:18px;font-weight:700;font-size:.88rem}input,select{border:1px solid var(--ui-border-strong);border-radius:var(--ui-radius-sm);padding:7px;background:var(--ui-surface);color:var(--ui-text)}input{width:78px}small{display:block;margin-top:5px;color:var(--ui-text-muted);line-height:1.35}.error,.saved{padding:10px 12px;border-radius:var(--ui-radius-sm)}.error{background:var(--ui-danger-soft);color:var(--ui-danger)}.saved{background:var(--ui-success-soft);color:var(--ui-success)}@media(max-width:640px){header{flex-direction:column}button{width:100%}}
</style>
