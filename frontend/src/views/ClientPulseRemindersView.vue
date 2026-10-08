<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { clientPulseApi } from '@/api'
import UiButton from '@/components/ui/UiButton.vue'
import UiCard from '@/components/ui/UiCard.vue'
import UiSelect from '@/components/ui/UiSelect.vue'
import ReminderEditorModal from '@/features/clientpulse/components/ReminderEditorModal.vue'
import ReminderThreadModal from '@/features/clientpulse/components/ReminderThreadModal.vue'
import '@/assets/clientpulse.css'

const route = useRoute()
const reminders = ref([]), clients = ref([]), owners = ref([]), notifications = ref([]), metrics = ref({})
const loading = ref(true), busy = ref(''), error = ref(''), success = ref('')
const showForm = ref(route.query.create === '1'), editingId = ref(null)
const linkedFrom = ref(null), threadOpen = ref(false), threadLoading = ref(false)
const thread = ref(null), threadError = ref('')
const windowFilter = ref('overdue'), page = ref(1), pages = ref(1), count = ref(0), assignedTo = ref('')
const form = reactive({ profile_id: null, assigned_to_id: null, linked_from_id: null, title: '', description: '', due_at: '', priority: 'normal', recurrence_type: 'none', interval_days: 1 })
const unreadNotifications = computed(() => notifications.value.filter(item => !item.read_at))
const ownerFilters = computed(() => [
  { value: '', label: 'All assignees' },
  ...owners.value.map(owner => ({ value: owner.id, label: owner.username })),
])

function localValue(value) {
  const date = new Date(value)
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16)
}
function resetForm() {
  Object.assign(form, {
    profile_id: Number(route.query.profile_id) || null,
    assigned_to_id: owners.value.length === 1 ? owners.value[0].id : null,
    linked_from_id: null,
    title: '', description: '', due_at: localValue(Date.now() + 3600000),
    priority: 'normal', recurrence_type: 'none', interval_days: 1,
  })
  editingId.value = null
  linkedFrom.value = null
}
function message(exc, fallback) {
  const data = exc.response?.data
  return data?.detail || (data ? JSON.stringify(data) : fallback)
}
function reminderPayload() {
  const payload = {
    profile_id: form.profile_id,
    assigned_to_id: form.assigned_to_id || null,
    title: form.title,
    description: form.description,
    due_at: new Date(form.due_at).toISOString(),
    priority: form.priority,
    recurrence_type: form.recurrence_type,
    recurrence_rule: form.recurrence_type === 'custom' ? { interval_days: Number(form.interval_days) } : {},
  }
  if (!editingId.value && form.linked_from_id) payload.linked_from_id = form.linked_from_id
  return payload
}
async function load() {
  loading.value = true; error.value = ''
  try {
    const params = { window: windowFilter.value, page: page.value, page_size: 25 }
    if (assignedTo.value) params.assigned_to_id = assignedTo.value
    const [reminderData, dashboardData, notificationData] = await Promise.all([
      clientPulseApi.reminders(params), clientPulseApi.dashboard(), clientPulseApi.notifications(),
    ])
    reminders.value = reminderData.data.results; count.value = reminderData.data.count
    pages.value = Math.max(1, Math.ceil(count.value / 25)); metrics.value = dashboardData.data
    notifications.value = notificationData.data
  } catch (exc) { error.value = message(exc, 'Unable to load reminders.') }
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
  editingId.value = item.id; showForm.value = true
}
async function saveReminder() {
  const mode = editingId.value ? 'edit' : 'create'
  busy.value = mode; error.value = ''; success.value = ''
  try {
    if (editingId.value) await clientPulseApi.updateReminder(editingId.value, reminderPayload())
    else await clientPulseApi.createReminder(reminderPayload())
    success.value = editingId.value ? 'Reminder updated.' : linkedFrom.value ? 'Linked follow-up created.' : 'Reminder created.'
    closeForm(); await load()
  } catch (exc) { error.value = message(exc, `Unable to ${mode} reminder.`) }
  finally { busy.value = '' }
}
async function complete(item) {
  busy.value = `complete-${item.id}`
  try { await clientPulseApi.completeReminder(item.id); await load() }
  catch (exc) { error.value = message(exc, 'Unable to complete reminder.') }
  finally { busy.value = '' }
}
async function openLinkedFollowUp(item, completeFirst = false) {
  busy.value = `follow-${item.id}`; error.value = ''; success.value = ''
  try {
    if (completeFirst && item.status !== 'completed') await clientPulseApi.completeReminder(item.id)
    resetForm()
    Object.assign(form, {
      profile_id: item.profile.id,
      assigned_to_id: item.assigned_to?.id || null,
      linked_from_id: item.id,
      due_at: localValue(Date.now() + 86400000),
      priority: item.priority || 'normal',
    })
    linkedFrom.value = { id: item.id, title: item.title }
    threadOpen.value = false
    showForm.value = true
    await load()
  } catch (exc) { error.value = message(exc, 'Unable to start a linked follow-up.') }
  finally { busy.value = '' }
}
async function viewThread(item) {
  threadOpen.value = true; threadLoading.value = true; threadError.value = ''; thread.value = null
  try { thread.value = (await clientPulseApi.reminderThread(item.id)).data }
  catch (exc) { threadError.value = message(exc, 'Unable to load reminder thread.') }
  finally { threadLoading.value = false }
}
async function snooze(item, hours) { busy.value = `snooze-${item.id}`; try { await clientPulseApi.snoozeReminder(item.id, new Date(Date.now() + hours * 3600000).toISOString()); await load() } catch (exc) { error.value = message(exc, 'Unable to snooze reminder.') } finally { busy.value = '' } }
async function cancel(item) { if (!confirm('Cancel this reminder?')) return; await clientPulseApi.cancelReminder(item.id); await load() }
async function markRead(item) { await clientPulseApi.readNotification(item.id); item.read_at = new Date().toISOString(); metrics.value.unread_notifications = Math.max(0, metrics.value.unread_notifications - 1) }
function move(next) { page.value = next; load() }
watch([windowFilter, assignedTo], () => { page.value = 1; load() })
onMounted(async () => {
  try {
    const [clientData, optionsData] = await Promise.all([clientPulseApi.clients({ status: 'active', page_size: 100 }), clientPulseApi.options()])
    clients.value = clientData.data.results; owners.value = optionsData.data.owners; resetForm(); await load()
  } catch (exc) { error.value = message(exc, 'Unable to initialize reminders.') }
})
</script>

<template>
  <main class="cp-page reminder-page"><div class="cp-shell">
    <header class="cp-hero reminder-hero">
      <div><p class="cp-eyebrow">Follow-up control</p><h1 class="cp-title">Reminders</h1><p class="cp-muted">Durable internal follow-ups. No customer message is sent from this workspace.</p></div>
      <div class="hero-actions"><RouterLink class="ui-button ui-button--outline ui-button--medium" to="/clientpulse-settings">Notification settings</RouterLink><UiButton variant="primary" @click="openCreate">+ New reminder</UiButton></div>
    </header>
    <p v-if="error" class="cp-notice error">{{ error }}</p><p v-if="success" class="cp-notice success">{{ success }}</p>

    <section class="reminder-metrics">
      <article><span>Overdue</span><strong>{{ metrics.overdue_reminders || 0 }}</strong></article>
      <article><span>Due today</span><strong>{{ metrics.due_today || 0 }}</strong></article>
      <article><span>Upcoming</span><strong>{{ metrics.upcoming || 0 }}</strong></article>
      <article><span>Unread</span><strong>{{ metrics.unread_notifications || 0 }}</strong></article>
    </section>

    <UiCard v-if="unreadNotifications.length" title="Notifications" subtitle="Recent reminder alerts requiring attention." class="notification-panel">
      <template #actions><span class="panel-count">{{ unreadNotifications.length }} unread</span></template>
      <div class="notification-list"><button v-for="item in unreadNotifications" :key="item.id" class="notification" @click="markRead(item)"><span><strong>{{ item.reminder.title }}</strong><small>{{ item.reminder.profile.display_name }}</small></span><b>Mark read</b></button></div>
    </UiCard>

    <UiCard title="Reminder ledger" :subtitle="`${count} reminders in this view`" flush class="ledger-panel">
      <template #actions><div class="ledger-filters"><div class="filter-tabs"><UiButton v-for="tab in ['overdue','today','upcoming','completed']" :key="tab" size="small" :variant="windowFilter === tab ? 'primary' : 'soft'" @click="windowFilter = tab">{{ tab }}</UiButton></div><UiSelect v-model="assignedTo" :options="ownerFilters" /><UiButton size="small" variant="outline" @click="load">Refresh</UiButton></div></template>
      <div class="reminder-table-wrap">
        <div v-if="loading" class="cp-empty">Loading reminders...</div>
        <table v-else v-ui-data-table="'clientpulse-reminders'" class="cp-table"><thead><tr><th>Reminder</th><th>Client</th><th>Due</th><th>Assigned</th><th>Priority</th><th>Repeat</th><th>Actions</th></tr></thead><tbody>
          <tr v-for="item in reminders" :key="item.id">
            <td><div class="reminder-title"><strong>{{ item.title }}</strong><span v-if="item.linked_from">Linked</span></div><p class="cp-muted">{{ item.description }}</p></td>
            <td><RouterLink class="cp-name" :to="`/clientpulse/${item.profile.id}`">{{ item.profile.display_name }}</RouterLink></td>
            <td>{{ new Date(item.snoozed_until || item.due_at).toLocaleString() }}<br><span class="cp-badge">{{ item.status }}</span></td>
            <td>{{ item.assigned_to?.username || 'Unassigned' }}</td><td>{{ item.priority }}</td><td>{{ item.recurrence_type }}</td>
            <td><div class="row-actions">
              <UiButton size="small" variant="soft" @click="viewThread(item)">Thread</UiButton>
              <template v-if="item.status !== 'completed' && item.status !== 'cancelled'">
                <UiButton size="small" variant="soft" @click="edit(item)">Edit</UiButton>
                <UiButton size="small" variant="primary" :disabled="busy === `complete-${item.id}`" @click="complete(item)">Complete</UiButton>
                <UiButton size="small" variant="outline" :disabled="busy === `follow-${item.id}`" @click="openLinkedFollowUp(item, true)">Complete + follow-up</UiButton>
                <UiButton size="small" @click="snooze(item, 1)">+1h</UiButton><UiButton size="small" @click="snooze(item, 24)">+1d</UiButton>
                <UiButton size="small" variant="danger" @click="cancel(item)">Cancel</UiButton>
              </template>
              <UiButton v-else-if="item.status === 'completed'" size="small" variant="outline" @click="openLinkedFollowUp(item)">Add follow-up</UiButton>
            </div></td>
          </tr>
        </tbody></table>
        <div v-if="!loading && !reminders.length" class="cp-empty">No reminders in this view.</div>
      </div>
      <footer class="cp-pager"><span>{{ count }} reminders</span><div><UiButton size="small" :disabled="page <= 1" @click="move(page - 1)">Previous</UiButton><span>Page {{ page }} of {{ pages }}</span><UiButton size="small" :disabled="page >= pages" @click="move(page + 1)">Next</UiButton></div></footer>
    </UiCard>

    <ReminderEditorModal :open="showForm" :editing="Boolean(editingId)" :linked-from="linkedFrom" :busy="busy === 'create' || busy === 'edit'" :form="form" :clients="clients" :owners="owners" @close="closeForm" @submit="saveReminder" />
    <ReminderThreadModal :open="threadOpen" :loading="threadLoading" :error="threadError" :thread="thread" @close="threadOpen = false" @follow-up="openLinkedFollowUp" />
  </div></main>
</template>

<style scoped>
.reminder-page{background:var(--ui-bg)}.reminder-hero{align-items:center;padding-bottom:16px;border-bottom:1px solid var(--ui-border)}.hero-actions{display:flex;gap:8px;flex-wrap:wrap}.reminder-metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:18px 0}.reminder-metrics article{padding:14px 16px;border:1px solid var(--ui-border);border-top:3px solid var(--ui-primary);border-radius:var(--ui-radius-md);background:var(--ui-surface)}.reminder-metrics span{display:block;color:var(--ui-text-muted);font-size:.68rem;font-weight:700;text-transform:uppercase}.reminder-metrics strong{color:var(--ui-text-strong);font:700 1.8rem var(--ui-font-display)}.notification-panel{margin-bottom:14px}.panel-count{padding:4px 8px;border-radius:999px;background:var(--ui-primary-soft);color:var(--ui-primary);font-size:.7rem;font-weight:700}.notification-list{display:grid;gap:8px}.notification{display:flex;width:100%;align-items:center;justify-content:space-between;padding:11px 12px;border:1px solid var(--ui-border);border-radius:var(--ui-radius-sm);background:var(--ui-surface-muted);color:var(--ui-text);text-align:left;cursor:pointer}.notification span,.notification small{display:block}.notification small{margin-top:3px;color:var(--ui-text-muted)}.notification b{color:var(--ui-primary);font-size:.72rem}.ledger-panel{margin-top:14px}.ledger-filters,.filter-tabs,.row-actions,.cp-pager>div{display:flex;align-items:center;gap:7px;flex-wrap:wrap}.reminder-title{display:flex;align-items:center;gap:7px}.reminder-title span{padding:2px 6px;border-radius:999px;background:var(--ui-primary-soft);color:var(--ui-primary);font-size:.62rem;font-weight:800;text-transform:uppercase}.ledger-filters :deep(.choices){min-width:180px}.reminder-table-wrap{overflow:auto}.cp-pager{display:flex;align-items:center;justify-content:space-between;padding:12px 15px;border-top:1px solid var(--ui-border)}@media(max-width:900px){.reminder-metrics{grid-template-columns:repeat(2,1fr)}.ledger-filters{align-items:stretch;flex-direction:column}.cp-pager{align-items:flex-start;gap:10px;flex-direction:column}}
</style>
