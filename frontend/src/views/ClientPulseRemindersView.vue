<script setup>
import { onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { clientPulseApi } from '@/api'
import '@/assets/clientpulse.css'

const route = useRoute()
const reminders = ref([]), clients = ref([]), owners = ref([]), notifications = ref([]), metrics = ref({})
const loading = ref(true), busy = ref(''), error = ref(''), success = ref('')
const showForm = ref(route.query.create === '1'), editingId = ref(null)
const windowFilter = ref('overdue'), page = ref(1), pages = ref(1), count = ref(0), assignedTo = ref('')
const form = reactive({ profile_id: null, assigned_to_id: null, title: '', description: '', due_at: '', priority: 'normal', recurrence_type: 'none', interval_days: 1 })

function localValue(value) {
  const date = new Date(value)
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16)
}
function resetForm() {
  Object.assign(form, {
    profile_id: Number(route.query.profile_id) || null,
    assigned_to_id: owners.value.length === 1 ? owners.value[0].id : null,
    title: '', description: '', due_at: localValue(Date.now() + 3600000),
    priority: 'normal', recurrence_type: 'none', interval_days: 1,
  })
  editingId.value = null
}
function msg(exc, fallback) {
  const data = exc.response?.data
  return data?.detail || (data ? JSON.stringify(data) : fallback)
}
function reminderPayload() {
  return {
    profile_id: form.profile_id,
    assigned_to_id: form.assigned_to_id,
    title: form.title,
    description: form.description,
    due_at: new Date(form.due_at).toISOString(),
    priority: form.priority,
    recurrence_type: form.recurrence_type,
    recurrence_rule: form.recurrence_type === 'custom' ? { interval_days: Number(form.interval_days) } : {},
  }
}
async function load() {
  loading.value = true; error.value = ''
  try {
    const params = { window: windowFilter.value, page: page.value, page_size: 25 }
    if (assignedTo.value) params.assigned_to_id = assignedTo.value
    const [r, d, n] = await Promise.all([clientPulseApi.reminders(params), clientPulseApi.dashboard(), clientPulseApi.notifications()])
    reminders.value = r.data.results; count.value = r.data.count
    pages.value = Math.max(1, Math.ceil(count.value / 25)); metrics.value = d.data; notifications.value = n.data
  } catch (exc) { error.value = msg(exc, 'Unable to load reminders.') }
  finally { loading.value = false }
}
function openCreate() { resetForm(); showForm.value = true }
function closeForm() { showForm.value = false; resetForm() }
function edit(item) {
  Object.assign(form, {
    profile_id: item.profile.id, assigned_to_id: item.assigned_to?.id || null,
    title: item.title, description: item.description || '', due_at: localValue(item.due_at),
    priority: item.priority, recurrence_type: item.recurrence_type,
    interval_days: item.recurrence_rule?.interval_days || 1,
  })
  editingId.value = item.id; showForm.value = true; window.scrollTo({ top: 0, behavior: 'smooth' })
}
async function saveReminder() {
  const mode = editingId.value ? 'edit' : 'create'
  busy.value = mode; error.value = ''; success.value = ''
  try {
    if (editingId.value) await clientPulseApi.updateReminder(editingId.value, reminderPayload())
    else await clientPulseApi.createReminder(reminderPayload())
    success.value = editingId.value ? 'Reminder updated.' : 'Reminder created.'
    closeForm(); await load()
  } catch (exc) { error.value = msg(exc, `Unable to ${mode} reminder.`) }
  finally { busy.value = '' }
}
async function complete(item) { busy.value=`complete-${item.id}`; try { await clientPulseApi.completeReminder(item.id); await load() } catch(exc) { error.value=msg(exc,'Unable to complete reminder.') } finally { busy.value='' } }
async function snooze(item,hours) { busy.value=`snooze-${item.id}`; try { await clientPulseApi.snoozeReminder(item.id,new Date(Date.now()+hours*3600000).toISOString()); await load() } catch(exc) { error.value=msg(exc,'Unable to snooze reminder.') } finally { busy.value='' } }
async function cancel(item) { if(!confirm('Cancel this reminder?'))return; await clientPulseApi.cancelReminder(item.id); await load() }
async function markRead(item) { await clientPulseApi.readNotification(item.id); item.read_at=new Date().toISOString(); metrics.value.unread_notifications=Math.max(0,metrics.value.unread_notifications-1) }
function move(next) { page.value=next; load() }
watch([windowFilter,assignedTo],()=>{page.value=1;load()})
onMounted(async()=>{
  try {
    const [c,o]=await Promise.all([clientPulseApi.clients({status:'active',page_size:100}),clientPulseApi.options()])
    clients.value=c.data.results;owners.value=o.data.owners;resetForm();await load()
  } catch(exc) { error.value=msg(exc,'Unable to initialize reminders.') }
})
</script>

<template><main class="cp-page"><div class="cp-shell">
  <header class="cp-hero"><div><p class="cp-eyebrow">Follow-up control</p><h1 class="cp-title">Reminders</h1><p class="cp-muted">Durable in-app follow-ups. No customer message is sent from this workspace.</p></div><button class="cp-button cp-primary" @click="showForm ? closeForm() : openCreate()">{{showForm?'Close':'New reminder'}}</button></header>
  <p v-if="error" class="cp-notice error">{{error}}</p><p v-if="success" class="cp-notice success">{{success}}</p>
  <section class="reminder-metrics"><article><span>Overdue</span><strong>{{metrics.overdue_reminders||0}}</strong></article><article><span>Due today</span><strong>{{metrics.due_today||0}}</strong></article><article><span>Upcoming</span><strong>{{metrics.upcoming||0}}</strong></article><article><span>Unread</span><strong>{{metrics.unread_notifications||0}}</strong></article></section>
  <section v-if="showForm" class="cp-panel cp-card"><h2>{{editingId?'Edit reminder':'Create reminder'}}</h2><form class="cp-form-grid" @submit.prevent="saveReminder">
    <label>Client<select v-model="form.profile_id" class="cp-select" required><option :value="null">Select client</option><option v-for="client in clients" :key="client.id" :value="client.id">{{client.display_name||client.legal_name}}</option></select></label>
    <label>Assigned to<select v-model="form.assigned_to_id" class="cp-select"><option :value="null">Unassigned</option><option v-for="owner in owners" :key="owner.id" :value="owner.id">{{owner.username}}</option></select></label>
    <label>Due<input v-model="form.due_at" type="datetime-local" class="cp-input" required /></label>
    <label class="wide">Title<input v-model="form.title" class="cp-input" required /></label>
    <label class="wide">Description<textarea v-model="form.description" class="cp-textarea" /></label>
    <label>Priority<select v-model="form.priority" class="cp-select"><option v-for="v in ['low','normal','high','critical']" :key="v">{{v}}</option></select></label>
    <label>Repeat<select v-model="form.recurrence_type" class="cp-select"><option v-for="v in ['none','daily','weekly','monthly','custom']" :key="v">{{v}}</option></select></label>
    <label v-if="form.recurrence_type==='custom'">Every days<input v-model.number="form.interval_days" type="number" min="1" class="cp-input" /></label>
    <div class="cp-actions wide"><button v-if="editingId" type="button" class="cp-button" @click="closeForm">Cancel edit</button><button class="cp-button cp-primary" :disabled="busy==='create'||busy==='edit'">{{editingId?'Save changes':'Create reminder'}}</button></div>
  </form></section>
  <section v-if="notifications.some(n=>!n.read_at)" class="cp-panel cp-card"><h2>Notifications</h2><div class="cp-list"><button v-for="item in notifications.filter(n=>!n.read_at)" :key="item.id" class="notification" @click="markRead(item)"><strong>{{item.reminder.title}}</strong><span>{{item.reminder.profile.display_name}} · Mark read</span></button></div></section>
  <section class="cp-panel cp-toolbar"><button v-for="tab in ['overdue','today','upcoming','completed']" :key="tab" :class="['cp-button',{ 'cp-primary':windowFilter===tab }]" @click="windowFilter=tab">{{tab}}</button><select v-model="assignedTo" class="cp-select"><option value="">All assignees</option><option v-for="owner in owners" :key="owner.id" :value="owner.id">{{owner.username}}</option></select><button class="cp-button" @click="load">Refresh</button></section>
  <section class="cp-panel cp-grid"><div v-if="loading" class="cp-empty">Loading reminders...</div><table v-else class="cp-table"><thead><tr><th>Reminder</th><th>Client</th><th>Due</th><th>Assigned</th><th>Priority</th><th>Repeat</th><th>Actions</th></tr></thead><tbody><tr v-for="item in reminders" :key="item.id"><td><strong>{{item.title}}</strong><p class="cp-muted">{{item.description}}</p></td><td><RouterLink class="cp-name" :to="`/clientpulse/${item.profile.id}`">{{item.profile.display_name}}</RouterLink></td><td>{{new Date(item.snoozed_until||item.due_at).toLocaleString()}}<br><span class="cp-badge">{{item.status}}</span></td><td>{{item.assigned_to?.username||'Unassigned'}}</td><td>{{item.priority}}</td><td>{{item.recurrence_type}}</td><td><div v-if="item.status!=='completed'&&item.status!=='cancelled'" class="row-actions"><button class="cp-button" @click="edit(item)">Edit</button><button class="cp-button cp-primary" @click="complete(item)">Complete</button><button class="cp-button" @click="snooze(item,1)">+1h</button><button class="cp-button" @click="snooze(item,24)">+1d</button><button class="cp-button cp-danger" @click="cancel(item)">Cancel</button></div></td></tr></tbody></table><div v-if="!loading&&!reminders.length" class="cp-empty">No reminders in this view.</div><footer class="cp-pager"><span>{{count}} reminders</span><div><button class="cp-button" :disabled="page<=1" @click="move(page-1)">Previous</button> Page {{page}} of {{pages}} <button class="cp-button" :disabled="page>=pages" @click="move(page+1)">Next</button></div></footer></section>
</div></main></template>

<style scoped>
.reminder-metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:18px 0}.reminder-metrics article{background:#173d2b;color:#fff;border-radius:13px;padding:15px}.reminder-metrics span{display:block;color:#b8d4c4;font-size:.74rem;text-transform:uppercase}.reminder-metrics strong{font:700 2rem Georgia,serif}.notification{display:flex;justify-content:space-between;text-align:left;border:1px solid #b9dec8;background:#effaf3;border-radius:10px;padding:11px;cursor:pointer}.row-actions{display:flex;flex-wrap:wrap;gap:5px}@media(max-width:800px){.reminder-metrics{grid-template-columns:repeat(2,1fr)}}
</style>
