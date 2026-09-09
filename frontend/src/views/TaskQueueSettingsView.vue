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
  <main class="page">
    <header><div><h1>Task &amp; Queues</h1><p>Control parallel background work and the maximum runtime for every task in each queue.</p></div><button :disabled="loading || saving" @click="save">{{ saving ? 'Saving...' : 'Save Settings' }}</button></header>
    <p v-if="error" class="error">{{ error }}</p><p v-if="saved" class="saved">Saved. Running workers use the new limits on their next poll.</p>
    <section v-if="!loading" class="grid"><article><h2>Runtime Modes</h2><code>Database controlled</code><label v-for="field in ['automation_mode','embedding_mode','classification_mode','recovery_mode']" :key="field">{{ field.replaceAll('_', ' ') }}<select v-model="runtime[field]"><option value="thread">Thread</option><option value="db_queue">DB queue</option></select></label><label>Worker heartbeat (seconds)<input v-model.number="runtime.worker_heartbeat_seconds" type="number" min="1" max="300"></label><label>Scheduler interval (seconds)<input v-model.number="runtime.scheduler_interval_seconds" type="number" min="1" max="300"></label></article><article v-for="queue in queues" :key="queue.name"><h2>{{ queue.display_name }}</h2><code>{{ queue.name }}</code><label>Concurrent tasks<input v-model.number="queue.max_concurrency" type="number" min="1" max="64"></label><small>Tasks may run in parallel up to this limit.</small><label>Task timeout (seconds)<input v-model.number="queue.task_timeout_seconds" type="number" min="30" max="7200"></label><small>Default: 300 seconds. On timeout the task is retried and its queue slot is released.</small></article></section>
  </main>
</template>

<style scoped>
.page{height:100%;overflow:auto;padding:24px;color:#172033;background:linear-gradient(135deg,#f7f4ed,#edf5f2)}header{display:flex;justify-content:space-between;gap:18px;align-items:flex-start;margin-bottom:20px}h1{margin:0;font:700 1.65rem Georgia,serif}header p{margin:6px 0 0;color:#5c6877;max-width:620px}button{border:0;border-radius:8px;background:#0e6b57;color:#fff;padding:10px 15px;font-weight:700;cursor:pointer}button:disabled{opacity:.6}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px}article{background:#fffdf8;border:1px solid #d9ded5;border-radius:14px;padding:18px;box-shadow:0 8px 22px rgba(29,48,43,.06)}h2{margin:0 0 3px;font-size:1rem}code{color:#69727b;font-size:.78rem}label{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-top:18px;font-weight:700;font-size:.88rem}input{width:78px;border:1px solid #bfcac2;border-radius:7px;padding:7px;background:#fff}small{display:block;margin-top:5px;color:#667085;line-height:1.35}.error,.saved{padding:10px 12px;border-radius:8px}.error{background:#fff1f1;color:#9b1c1c}.saved{background:#edfaf2;color:#17633a}@media(max-width:640px){header{flex-direction:column}button{width:100%}}
</style>
