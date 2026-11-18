<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { FontAwesomeIcon } from '@fortawesome/vue-fontawesome'
import { faWhatsapp } from '@fortawesome/free-brands-svg-icons'
import { faClock, faEnvelopeOpen, faUser, faXmark } from '@fortawesome/free-solid-svg-icons'
import { clientPulseApi } from '@/api'
import { useAuthStore } from '@/stores/auth'
import { useClientInboxNavigation } from '../composables/useClientInboxNavigation'
import { playReminderSound, primeReminderAudio } from '../reminderSound'

// The bell in the top bar: due reminders collect here and are opened when the user chooses.
// New ones announce themselves only by the badge, the sound and (if enabled) a desktop notification.
defineProps({
  buttonClass: { type: String, default: '' },
  showLabel: { type: Boolean, default: false },
})

const auth = useAuthStore()
const router = useRouter()
const { openingContactId, openClientInbox } = useClientInboxNavigation()
const items = ref([])
const open = ref(false)
const error = ref('')
const root = ref(null)
const settings = ref({
  reminders_enabled: true,
  reminder_sound_enabled: true,
  reminder_sound: 'chime',
  reminder_sound_volume: 70,
  reminder_desktop_notifications_enabled: false,
  reminder_poll_interval_seconds: 30,
})
const companyId = computed(() => auth.currentCompany?.id)
const canManage = computed(() => auth.hasPermission('clientpulse.reminders.manage'))
const canOpenInbox = computed(() => auth.hasPermission('conversations.chats.view'))
const unreadCount = computed(() => items.value.filter(item => !item.read_at).length)
const ordered = computed(() => [...items.value].sort((a, b) => Number(Boolean(a.read_at)) - Number(Boolean(b.read_at))))
let timer
let running = false
let pendingSound = false
let seen = new Set()

function storageKey() { return `clientpulse-reminder-seen:${companyId.value || 'none'}` }
function restoreSeen() {
  try { seen = new Set(JSON.parse(sessionStorage.getItem(storageKey()) || '[]')) }
  catch { seen = new Set() }
}
function persistSeen() {
  sessionStorage.setItem(storageKey(), JSON.stringify([...seen].slice(-200)))
}
function reminderTime(item) {
  return new Date(item.reminder.snoozed_until || item.reminder.due_at).toLocaleString()
}
function whatsappChats(item) {
  if (!canOpenInbox.value) return []
  return (item.reminder.profile.communication_accounts || []).filter(account => account.whatsapp_contact_id)
}
function failure(exc, fallback) { return exc?.response?.data?.detail || fallback }
function showDesktop(item) {
  if (!settings.value.reminder_desktop_notifications_enabled) return
  if (!window.isSecureContext || !('Notification' in window) || Notification.permission !== 'granted') return
  const notification = new Notification(`Reminder: ${item.reminder.title}`, {
    body: `${item.reminder.profile.display_name} · due ${reminderTime(item)}`,
    tag: `clientpulse-reminder-${item.id}`,
  })
  notification.onclick = () => { window.focus(); open.value = true; notification.close() }
}
async function fetchSettings() {
  try { settings.value = { ...settings.value, ...(await clientPulseApi.notificationPreferences()).data } }
  catch { /* Notification polling still works with safe defaults. */ }
}
async function poll() {
  if (running || !companyId.value || !auth.hasPermission('clientpulse.reminders.view')) return
  if (!settings.value.reminders_enabled) { items.value = []; return }
  running = true
  try {
    items.value = (await clientPulseApi.notifications()).data
    const fresh = items.value.filter(item => !item.read_at && !seen.has(item.id))
    if (!fresh.length) return
    fresh.forEach(item => { seen.add(item.id); showDesktop(item) })
    persistSeen()
    if (settings.value.reminder_sound_enabled) {
      pendingSound = !(await playReminderSound(
        settings.value.reminder_sound, settings.value.reminder_sound_volume,
      ))
    }
  } catch { /* A background notifier must not interrupt the active page; the next poll retries. */ }
  finally { running = false }
}
function schedule() {
  clearInterval(timer)
  const seconds = Math.min(300, Math.max(10, Number(settings.value.reminder_poll_interval_seconds) || 30))
  timer = setInterval(poll, seconds * 1000)
}
async function start() {
  clearInterval(timer); items.value = []; open.value = false; restoreSeen()
  await fetchSettings(); await poll(); schedule()
}
async function markRead(item) {
  if (item.read_at) return
  await clientPulseApi.readNotification(item.id)
  item.read_at = new Date().toISOString()
}
async function act(action, fallback) {
  error.value = ''
  try { await action() } catch (exc) { error.value = failure(exc, fallback) }
}
function readOnly(item) { return act(() => markRead(item), 'Unable to mark the reminder as read.') }
function openClient(item) {
  return act(async () => {
    await markRead(item)
    open.value = false
    await router.push(`/clientpulse/${item.reminder.profile.id}`)
  }, 'Unable to open the client.')
}
function openWhatsapp(item, account) {
  return act(async () => {
    await markRead(item)
    await openClientInbox(account.id, account.whatsapp_contact_id)
    open.value = false
  }, 'Unable to open this conversation in WhatsApp Inbox.')
}
function dismiss(item) {
  return act(async () => {
    await clientPulseApi.dismissNotification(item.id)
    items.value = items.value.filter(other => other.id !== item.id)
  }, 'Unable to dismiss the reminder.')
}
function snooze(item) {
  return act(async () => {
    await clientPulseApi.snoozeReminder(item.reminder.id, new Date(Date.now() + 3600000).toISOString())
    items.value = items.value.filter(other => other.id !== item.id)
  }, 'Unable to snooze the reminder.')
}
function toggle() {
  open.value = !open.value
  error.value = ''
  if (open.value) poll()
}
async function prime() {
  try {
    await primeReminderAudio()
    if (pendingSound && settings.value.reminder_sound_enabled) {
      pendingSound = !(await playReminderSound(
        settings.value.reminder_sound, settings.value.reminder_sound_volume,
      ))
    }
  } catch { /* The bell badge remains available when audio is blocked. */ }
}
function visible() { if (!document.hidden) poll() }
function outside(event) { if (open.value && root.value && !root.value.contains(event.target)) open.value = false }
function escape(event) { if (event.key === 'Escape') open.value = false }
function applySettings(event) {
  settings.value = { ...settings.value, ...event.detail }
  if (!settings.value.reminders_enabled) { items.value = []; open.value = false }
  schedule()
}

watch(companyId, value => { if (value) start(); else clearInterval(timer) }, { immediate: true })
watch(() => settings.value.reminder_poll_interval_seconds, schedule)
document.addEventListener('pointerdown', prime, { once: true })
document.addEventListener('keydown', prime, { once: true })
document.addEventListener('pointerdown', outside)
document.addEventListener('keydown', escape)
document.addEventListener('visibilitychange', visible)
window.addEventListener('clientpulse-reminder-settings', applySettings)
onBeforeUnmount(() => {
  clearInterval(timer)
  document.removeEventListener('pointerdown', prime)
  document.removeEventListener('keydown', prime)
  document.removeEventListener('pointerdown', outside)
  document.removeEventListener('keydown', escape)
  document.removeEventListener('visibilitychange', visible)
  window.removeEventListener('clientpulse-reminder-settings', applySettings)
})
</script>

<template>
  <div v-if="settings.reminders_enabled" ref="root" class="reminder-bell">
    <button
      type="button" :class="[buttonClass, { active: open }]" :aria-expanded="open" aria-haspopup="dialog"
      :title="unreadCount ? `${unreadCount} unread reminder${unreadCount === 1 ? '' : 's'}` : 'Reminders'"
      aria-label="Reminders" @click="toggle"
    >
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 8a6 6 0 1 1 12 0c0 7 3 9 3 9H3s3-2 3-9M10.3 21a1.94 1.94 0 0 0 3.4 0"/></svg>
      <span v-if="showLabel">Reminders</span>
      <b v-if="unreadCount">{{ unreadCount > 99 ? '99+' : unreadCount }}</b>
    </button>
    <section v-if="open" class="reminder-panel" role="dialog" aria-label="Reminders">
      <header>
        <strong>Reminders</strong>
        <small>{{ unreadCount }} unread</small>
      </header>
      <p v-if="error" class="reminder-panel__error" role="alert">{{ error }}</p>
      <p v-if="!ordered.length" class="reminder-panel__empty">No reminders.</p>
      <ul v-else>
        <li v-for="item in ordered" :key="item.id" class="reminder-item" :class="[`priority-${item.reminder.priority}`, { unread: !item.read_at }]">
          <div class="reminder-item__head">
            <strong>{{ item.reminder.title }}</strong>
            <button type="button" class="reminder-item__close" title="Dismiss" aria-label="Dismiss reminder" @click="dismiss(item)"><FontAwesomeIcon :icon="faXmark" /></button>
          </div>
          <p>{{ item.reminder.profile.display_name }}</p>
          <small>Due {{ reminderTime(item) }}</small>
          <div class="reminder-item__actions">
            <button type="button" class="primary" title="Open client" aria-label="Open client" @click="openClient(item)"><FontAwesomeIcon :icon="faUser" /></button>
            <button
              v-for="account in whatsappChats(item)" :key="account.id" type="button" class="whatsapp"
              :disabled="openingContactId === account.whatsapp_contact_id"
              :title="`Open the WhatsApp conversation on ${account.name}`" :aria-label="`WhatsApp: ${account.name}`"
              @click="openWhatsapp(item, account)"
            >
              <FontAwesomeIcon :icon="faWhatsapp" />
              <template v-if="whatsappChats(item).length > 1">{{ account.name }}</template>
            </button>
            <button v-if="canManage" type="button" title="Snooze 1 hour" aria-label="Snooze 1 hour" @click="snooze(item)"><FontAwesomeIcon :icon="faClock" /> 1h</button>
            <button v-if="!item.read_at" type="button" title="Mark read" aria-label="Mark read" @click="readOnly(item)"><FontAwesomeIcon :icon="faEnvelopeOpen" /></button>
          </div>
        </li>
      </ul>
    </section>
  </div>
</template>

<style scoped>
.reminder-bell{position:relative;display:flex;align-items:center;height:100%}
.reminder-bell>button.inspinia-alert{border:0;cursor:pointer}.reminder-bell>button.inspinia-alert:not(:hover){background:transparent}
.reminder-bell>button svg{width:18px;height:18px;fill:none;stroke:currentColor;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round}
.reminder-panel{position:absolute;top:calc(100% + 4px);right:0;z-index:12000;width:min(390px,calc(100vw - 24px));max-height:calc(100vh - 90px);display:flex;flex-direction:column;overflow:hidden;border:1px solid var(--ui-border,#d9e1e7);border-radius:12px;background:var(--ui-surface,#fff);box-shadow:0 18px 45px rgb(15 23 42 / 22%);color:var(--ui-text,#263238);text-align:left;font-family:inherit}
.reminder-panel header{display:flex;align-items:baseline;justify-content:space-between;padding:12px 16px;border-bottom:1px solid var(--ui-border,#d9e1e7);background:var(--ui-surface-muted,#f4f7f8)}
.reminder-panel header strong{font-size:.8rem;font-weight:800;letter-spacing:.08em;text-transform:uppercase}
.reminder-panel header small{color:var(--ui-text-muted,#6b7280);font-size:.74rem}
.reminder-panel__error{margin:0;padding:9px 16px;background:#fdecee;color:var(--ui-danger,#c0392b);font-size:.78rem;font-weight:600}
.reminder-panel__empty{margin:0;padding:22px 16px;color:var(--ui-text-muted,#6b7280);font-size:.82rem;text-align:center}
.reminder-panel ul{margin:0;padding:0;list-style:none;overflow-y:auto}
.reminder-item{padding:12px 16px 13px 13px;border-bottom:1px solid var(--ui-border,#e5eaee);border-left:4px solid transparent;opacity:.72}
.reminder-item.unread{border-left-color:var(--ui-warning,#e5a02f);opacity:1}
.reminder-item.unread.priority-high{border-left-color:#f97316}
.reminder-item.unread.priority-critical{border-left-color:var(--ui-danger,#dc3545)}
.reminder-item__head{display:flex;align-items:flex-start;justify-content:space-between;gap:8px}
.reminder-item__head strong{font-size:.9rem}
.reminder-item__close{border:0;background:transparent;color:var(--ui-text-muted,#6b7280);font-size:.95rem;line-height:1;cursor:pointer}
.reminder-item p{margin:3px 0 1px;font-size:.82rem;font-weight:600}
.reminder-item small{color:var(--ui-text-muted,#6b7280);font-size:.74rem}
.reminder-item__actions{display:flex;flex-wrap:wrap;gap:6px;margin-top:9px}
.reminder-item__actions button{display:inline-flex;align-items:center;gap:5px;padding:5px 9px;border:1px solid var(--ui-border,#d9e1e7);border-radius:7px;background:var(--ui-surface,#fff);color:inherit;font-size:.73rem;font-weight:700;cursor:pointer}
.reminder-item__actions button:disabled{opacity:.6;cursor:wait}
.reminder-item__actions .primary{border-color:var(--ui-primary,#16a085);background:var(--ui-primary,#16a085);color:#fff}
.reminder-item__actions .whatsapp{border-color:#25d366;background:#25d366;color:#fff}
</style>
