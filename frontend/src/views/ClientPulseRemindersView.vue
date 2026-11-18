<script setup>
import { formatDateTime } from '@/utils/dateFormat'
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { clientPulseApi } from '@/api'
import { FontAwesomeIcon } from '@fortawesome/vue-fontawesome'
import { faWhatsapp } from '@fortawesome/free-brands-svg-icons'
import { faArrowsRotate, faBan, faBell, faEnvelope, faUsers, faCalendarPlus, faCheck, faEnvelopeOpen, faGear, faListUl, faPen, faPlus } from '@fortawesome/free-solid-svg-icons'
import UiButton from '@/components/ui/UiButton.vue'
import UiCard from '@/components/ui/UiCard.vue'
import UiSelect from '@/components/ui/UiSelect.vue'
import ReminderEditorModal from '@/features/clientpulse/components/ReminderEditorModal.vue'
import ReminderThreadModal from '@/features/clientpulse/components/ReminderThreadModal.vue'
import { normalizeReminderDefaults } from '@/features/clientpulse/reminderDefaults.js'
import { blankReminderForm, followUpFields, reminderPayload as buildReminderPayload } from '@/features/clientpulse/reminderForm.js'
import { useClientInboxNavigation } from '@/features/clientpulse/composables/useClientInboxNavigation'
import { useAuthStore } from '@/stores/auth'
import '@/assets/clientpulse.css'

const route = useRoute()
const auth = useAuthStore()
const { openingContactId, openClientInbox } = useClientInboxNavigation()
const canOpenInbox = computed(() => auth.hasPermission('conversations.chats.view'))
const reminders = ref([]), clients = ref([]), owners = ref([]), phrases = ref([]), notifications = ref([]), metrics = ref({})
const loading = ref(true), busy = ref(''), error = ref(''), success = ref('')
const showForm = ref(route.query.create === '1'), editingId = ref(null)
const linkedFrom = ref(null), threadOpen = ref(false), threadLoading = ref(false)
const thread = ref(null), threadError = ref('')
const windowFilter = ref('overdue'), page = ref(1), pages = ref(1), count = ref(0), assignedTo = ref('')
const reminderDefaults = ref(normalizeReminderDefaults())
const form = reactive(blankReminderForm({ defaults: reminderDefaults.value }))
const unreadNotifications = computed(() => notifications.value.filter(item => !item.read_at))
// Counts for each ledger tab, from the dashboard (same assignee filter as the ledger).
const tabs = computed(() => [
  { key: 'overdue', label: 'Overdue', count: metrics.value.overdue_reminders },
  { key: 'today', label: 'Today', count: metrics.value.due_today },
  { key: 'upcoming', label: 'Upcoming', count: metrics.value.upcoming },
  { key: 'completed', label: 'Completed', count: metrics.value.completed_reminders },
])
const ownerFilters = computed(() => [
  { value: '', label: 'All assignees' },
  ...owners.value.map(owner => ({ value: owner.id, label: owner.username })),
])

function localValue(value) {
  const date = new Date(value)
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16)
}
function resetForm() {
  Object.assign(form, blankReminderForm({
    defaults: reminderDefaults.value, owners: owners.value, profileId: Number(route.query.profile_id) || null,
  }))
  editingId.value = null
  linkedFrom.value = null
}
function message(exc, fallback) {
  const data = exc.response?.data
  return data?.detail || (data ? JSON.stringify(data) : fallback)
}
function reminderPayload() {
  return buildReminderPayload(form, { timezone: reminderDefaults.value.timezone, editing: Boolean(editingId.value) })
}
async function load() {
  loading.value = true; error.value = ''
  try {
    const params = { window: windowFilter.value, page: page.value, page_size: 25 }
    if (assignedTo.value) params.assigned_to_id = assignedTo.value
    const [reminderData, dashboardData, notificationData] = await Promise.all([
      clientPulseApi.reminders(params), clientPulseApi.dashboard(assignedTo.value ? { assigned_to_id: assignedTo.value } : {}),
      clientPulseApi.notifications(),
    ])
    reminders.value = reminderData.data.results; count.value = reminderData.data.count
    pages.value = Math.max(1, Math.ceil(count.value / 25)); metrics.value = dashboardData.data
    notifications.value = notificationData.data
  } catch (exc) { error.value = message(exc, 'Unable to load reminders.') }
  finally { loading.value = false }
}
function whatsappChats(item) {
  if (!canOpenInbox.value) return []
  return (item.profile.communication_accounts || []).filter(account => account.whatsapp_contact_id)
}
async function openChat(account) {
  error.value = ''
  try { await openClientInbox(account.id, account.whatsapp_contact_id) }
  catch (exc) { error.value = message(exc, 'Unable to open this conversation in WhatsApp Inbox.') }
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
    Object.assign(form, followUpFields(item))
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
    const [clientData, optionsData, phraseData] = await Promise.all([clientPulseApi.clients({ status: 'active', page_size: 100 }), clientPulseApi.options(), clientPulseApi.reminderPhrases()])
    clients.value = clientData.data.results
    phrases.value = phraseData.data
    owners.value = optionsData.data.owners
    reminderDefaults.value = normalizeReminderDefaults(optionsData.data.reminder_defaults)
    resetForm(); await load()
  } catch (exc) { error.value = message(exc, 'Unable to initialize reminders.') }
})
</script>

<template>
  <main class="cp-page reminder-page"><div class="cp-shell">
    <header class="cp-hero reminder-hero">
      <div><p class="cp-eyebrow">Follow-up control</p><h1 class="cp-title">Reminders</h1><p class="cp-muted">Durable internal follow-ups. No customer message is sent from this workspace.</p></div>
      <div class="hero-actions"><RouterLink class="ui-button ui-button--outline ui-button--medium" to="/clientpulse-settings"><FontAwesomeIcon :icon="faGear" /> Notification settings</RouterLink><UiButton variant="primary" @click="openCreate"><FontAwesomeIcon :icon="faPlus" /> New reminder</UiButton></div>
    </header>
    <p v-if="error" class="cp-notice error">{{ error }}</p><p v-if="success" class="cp-notice success">{{ success }}</p>

    <section class="reminder-metrics">
      <article title="Distinct clients with at least one active reminder"><span><FontAwesomeIcon :icon="faUsers" /> Clients</span><strong>{{ metrics.clients_with_reminders || 0 }}</strong><small>with active reminders</small></article>
      <article title="Pending, due or snoozed reminders"><span><FontAwesomeIcon :icon="faBell" /> Active</span><strong>{{ metrics.active_reminders || 0 }}</strong><small>reminders to do</small></article>
      <button
        v-for="tab in tabs" :key="tab.key" type="button" class="metric-tab" :class="[`metric-${tab.key}`, { active: windowFilter === tab.key }]"
        :aria-pressed="windowFilter === tab.key" :title="`Show ${tab.label.toLowerCase()} reminders`" @click="windowFilter = tab.key"
      ><span>{{ tab.label }}</span><strong>{{ tab.count || 0 }}</strong><small>show in ledger</small></button>
      <article title="Unread reminder notifications in the bell"><span><FontAwesomeIcon :icon="faEnvelope" /> Unread</span><strong>{{ metrics.unread_notifications || 0 }}</strong><small>notifications</small></article>
    </section>

    <UiCard v-if="unreadNotifications.length" title="Notifications" subtitle="Recent reminder alerts requiring attention." class="notification-panel">
      <template #actions><span class="panel-count">{{ unreadNotifications.length }} unread</span></template>
      <div class="notification-list"><button v-for="item in unreadNotifications" :key="item.id" class="notification" @click="markRead(item)"><span><strong>{{ item.reminder.title }}</strong><small>{{ item.reminder.profile.display_name }}</small></span><b title="Mark read" aria-label="Mark read"><FontAwesomeIcon :icon="faEnvelopeOpen" /></b></button></div>
    </UiCard>

    <UiCard title="Reminder ledger" :subtitle="`${count} reminders in this view`" flush class="ledger-panel">
      <template #actions><div class="ledger-filters"><div class="filter-tabs"><UiButton v-for="tab in tabs" :key="tab.key" size="small" :variant="windowFilter === tab.key ? 'primary' : 'soft'" @click="windowFilter = tab.key">{{ tab.label }} <b class="tab-count">{{ tab.count || 0 }}</b></UiButton></div><UiSelect v-model="assignedTo" :options="ownerFilters" /><UiButton size="small" variant="outline" title="Refresh" aria-label="Refresh" @click="load"><FontAwesomeIcon :icon="faArrowsRotate" /></UiButton></div></template>
      <div class="reminder-table-wrap">
        <div v-if="loading" class="cp-empty">Loading reminders...</div>
        <table v-else v-ui-data-table="'clientpulse-reminders'" class="cp-table"><thead><tr><th>Reminder</th><th>Client</th><th>Due</th><th>Assigned</th><th>Priority</th><th>Repeat</th><th>Actions</th></tr></thead><tbody>
          <tr v-for="item in reminders" :key="item.id">
            <td><div class="reminder-title"><strong>{{ item.title }}</strong><span v-if="item.linked_from">Linked</span></div><p class="cp-muted">{{ item.description }}</p></td>
            <td><div class="reminder-client"><RouterLink class="cp-name" :to="`/clientpulse/${item.profile.id}`">{{ item.profile.display_name }}</RouterLink><span
              v-if="item.profile.open_reminders" class="client-open-reminders" :class="{ several: item.profile.open_reminders > 1 }"
              :title="`${item.profile.open_reminders} active reminder${item.profile.open_reminders === 1 ? '' : 's'} for this client`"
              :aria-label="`${item.profile.open_reminders} active reminder${item.profile.open_reminders === 1 ? '' : 's'} for this client`"
            ><FontAwesomeIcon :icon="faBell" />{{ item.profile.open_reminders }}</span></div></td>
            <td>{{ formatDateTime(item.snoozed_until || item.due_at) }}<br><span class="cp-badge">{{ item.status }}</span></td>
            <td>{{ item.assigned_to?.username || 'Unassigned' }}</td><td>{{ item.priority }}</td><td>{{ item.recurrence_type }}</td>
            <td><div class="row-actions">
              <UiButton
                v-for="account in whatsappChats(item)" :key="`wa-${account.id}`" size="small" class="row-whatsapp"
                :disabled="openingContactId === account.whatsapp_contact_id"
                :title="`Open the WhatsApp conversation on ${account.name}`" :aria-label="`WhatsApp: ${account.name}`" @click="openChat(account)"
              ><FontAwesomeIcon :icon="faWhatsapp" /><template v-if="whatsappChats(item).length > 1">{{ account.name }}</template></UiButton>
              <UiButton size="small" variant="soft" title="Thread" aria-label="Thread" @click="viewThread(item)"><FontAwesomeIcon :icon="faListUl" /></UiButton>
              <template v-if="item.status !== 'completed' && item.status !== 'cancelled'">
                <UiButton size="small" variant="soft" title="Edit" aria-label="Edit" @click="edit(item)"><FontAwesomeIcon :icon="faPen" /></UiButton>
                <UiButton size="small" variant="primary" :disabled="busy === `complete-${item.id}`" title="Complete" aria-label="Complete" @click="complete(item)"><FontAwesomeIcon :icon="faCheck" /></UiButton>
                <UiButton size="small" variant="outline" :disabled="busy === `follow-${item.id}`" title="Complete + follow-up" aria-label="Complete + follow-up" @click="openLinkedFollowUp(item, true)"><FontAwesomeIcon :icon="faCheck" /><FontAwesomeIcon :icon="faCalendarPlus" /></UiButton>
                <UiButton size="small" title="Snooze 1 hour" @click="snooze(item, 1)">+1h</UiButton><UiButton size="small" title="Snooze 1 day" @click="snooze(item, 24)">+1d</UiButton>
                <UiButton size="small" variant="danger" title="Cancel reminder" aria-label="Cancel reminder" @click="cancel(item)"><FontAwesomeIcon :icon="faBan" /></UiButton>
              </template>
              <UiButton v-else-if="item.status === 'completed'" size="small" variant="outline" title="Add follow-up" aria-label="Add follow-up" @click="openLinkedFollowUp(item)"><FontAwesomeIcon :icon="faCalendarPlus" /></UiButton>
            </div></td>
          </tr>
        </tbody></table>
        <div v-if="!loading && !reminders.length" class="cp-empty">No reminders in this view.</div>
      </div>
      <footer class="cp-pager"><span>{{ count }} reminders</span><div><UiButton size="small" :disabled="page <= 1" @click="move(page - 1)">Previous</UiButton><span>Page {{ page }} of {{ pages }}</span><UiButton size="small" :disabled="page >= pages" @click="move(page + 1)">Next</UiButton></div></footer>
    </UiCard>

    <ReminderEditorModal :open="showForm" :editing="Boolean(editingId)" :linked-from="linkedFrom" :busy="busy === 'create' || busy === 'edit'" :form="form" :clients="clients" :owners="owners" :phrases="phrases" @close="closeForm" @submit="saveReminder" />
    <ReminderThreadModal :open="threadOpen" :loading="threadLoading" :error="threadError" :thread="thread" @close="threadOpen = false" @follow-up="openLinkedFollowUp" />
  </div></main>
</template>

<style scoped>
.reminder-page{background:var(--ui-bg)}.reminder-hero{align-items:center;padding-bottom:16px;border-bottom:1px solid var(--ui-border)}.hero-actions{display:flex;gap:8px;flex-wrap:wrap}.reminder-metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin:18px 0}.reminder-metrics article,.reminder-metrics .metric-tab{padding:14px 16px;border:1px solid var(--ui-border);border-top:3px solid var(--ui-primary);border-radius:var(--ui-radius-md);background:var(--ui-surface);color:inherit;font:inherit;text-align:left}.reminder-metrics .metric-tab{cursor:pointer}.reminder-metrics .metric-tab:hover{border-color:var(--ui-primary)}.reminder-metrics .metric-tab.active{background:var(--ui-primary-soft);border-color:var(--ui-primary)}.reminder-metrics .metric-overdue{border-top-color:var(--ui-danger)}.reminder-metrics .metric-today{border-top-color:var(--ui-warning,#b7791f)}.reminder-metrics .metric-completed{border-top-color:var(--ui-success,#16a34a)}.reminder-metrics span{display:flex;align-items:center;gap:6px;color:var(--ui-text-muted);font-size:.68rem;font-weight:700;text-transform:uppercase}.reminder-metrics strong{display:block;color:var(--ui-text-strong);font:700 1.8rem var(--ui-font-display)}.reminder-metrics small{color:var(--ui-text-subtle,var(--ui-text-muted));font-size:.68rem}.tab-count{margin-left:4px;padding:0 6px;border-radius:999px;background:rgb(255 255 255 / 35%);font-size:.68rem}.notification-panel{margin-bottom:14px}.panel-count{padding:4px 8px;border-radius:999px;background:var(--ui-primary-soft);color:var(--ui-primary);font-size:.7rem;font-weight:700}.notification-list{display:grid;gap:8px}.notification{display:flex;width:100%;align-items:center;justify-content:space-between;padding:11px 12px;border:1px solid var(--ui-border);border-radius:var(--ui-radius-sm);background:var(--ui-surface-muted);color:var(--ui-text);text-align:left;cursor:pointer}.notification span,.notification small{display:block}.notification small{margin-top:3px;color:var(--ui-text-muted)}.notification b{color:var(--ui-primary);font-size:.72rem}.ledger-panel{margin-top:14px}.ledger-filters,.filter-tabs,.row-actions,.cp-pager>div{display:flex;align-items:center;gap:7px;flex-wrap:wrap}.row-actions .row-whatsapp{border-color:#25d366;background:#25d366;color:#fff}.reminder-client{display:flex;align-items:center;gap:7px;flex-wrap:wrap}.client-open-reminders{display:inline-flex;align-items:center;gap:4px;padding:2px 7px;border-radius:999px;background:var(--ui-primary-soft);color:var(--ui-primary);font-size:.68rem;font-weight:800;white-space:nowrap}.client-open-reminders.several{background:var(--ui-warning-soft,#fdf1dc);color:var(--ui-warning,#b7791f)}.reminder-title{display:flex;align-items:center;gap:7px}.reminder-title span{padding:2px 6px;border-radius:999px;background:var(--ui-primary-soft);color:var(--ui-primary);font-size:.62rem;font-weight:800;text-transform:uppercase}.ledger-filters :deep(.choices){min-width:180px}.reminder-table-wrap{overflow:auto}.cp-pager{display:flex;align-items:center;justify-content:space-between;padding:12px 15px;border-top:1px solid var(--ui-border)}@media(max-width:900px){.ledger-filters{align-items:stretch;flex-direction:column}.cp-pager{align-items:flex-start;gap:10px;flex-direction:column}}
</style>
