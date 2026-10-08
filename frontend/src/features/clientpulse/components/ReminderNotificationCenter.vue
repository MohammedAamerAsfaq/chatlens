<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { clientPulseApi } from '@/api'
import { useAuthStore } from '@/stores/auth'
import { playReminderSound, primeReminderAudio } from '../reminderSound'

const auth = useAuthStore()
const router = useRouter()
const alerts = ref([])
const settings = ref({
  reminders_enabled: true,
  reminder_popup_enabled: true,
  reminder_sound_enabled: true,
  reminder_sound: 'chime',
  reminder_sound_volume: 70,
  reminder_desktop_notifications_enabled: false,
  reminder_poll_interval_seconds: 30,
})
const companyId = computed(() => auth.currentCompany?.id)
const canManage = computed(() => auth.hasPermission('clientpulse.reminders.manage'))
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
function showDesktop(item) {
  if (!settings.value.reminder_desktop_notifications_enabled) return
  if (!window.isSecureContext || !('Notification' in window) || Notification.permission !== 'granted') return
  const notification = new Notification(`Reminder: ${item.reminder.title}`, {
    body: `${item.reminder.profile.display_name} · due ${reminderTime(item)}`,
    tag: `clientpulse-reminder-${item.id}`,
  })
  notification.onclick = () => { window.focus(); router.push('/clientpulse-reminders'); notification.close() }
}
async function fetchSettings() {
  try { settings.value = { ...settings.value, ...(await clientPulseApi.notificationPreferences()).data } }
  catch { /* Notification polling still works with safe defaults. */ }
}
async function poll() {
  if (running || !companyId.value || !auth.hasPermission('clientpulse.reminders.view')) return
  if (!settings.value.reminders_enabled) { alerts.value = []; return }
  running = true
  try {
    const items = (await clientPulseApi.notifications()).data.filter(item => !item.read_at)
    const fresh = items.filter(item => !seen.has(item.id))
    if (settings.value.reminder_popup_enabled) {
      alerts.value = items.slice(0, 5)
    } else {
      alerts.value = []
    }
    if (!fresh.length) return
    fresh.forEach(item => { seen.add(item.id); showDesktop(item) })
    persistSeen()
    if (settings.value.reminder_sound_enabled) {
      pendingSound = !(await playReminderSound(
        settings.value.reminder_sound, settings.value.reminder_sound_volume,
      ))
    }
  } catch { /* A background notifier must not interrupt the active page. */ }
  finally { running = false }
}
function schedule() {
  clearInterval(timer)
  const seconds = Math.min(300, Math.max(10, Number(settings.value.reminder_poll_interval_seconds) || 30))
  timer = setInterval(poll, seconds * 1000)
}
async function start() {
  clearInterval(timer); alerts.value = []; restoreSeen()
  await fetchSettings(); await poll(); schedule()
}
async function markRead(item, open = false) {
  try { await clientPulseApi.readNotification(item.id) } catch { /* remove locally */ }
  alerts.value = alerts.value.filter(alert => alert.id !== item.id)
  if (open) await router.push(`/clientpulse/${item.reminder.profile.id}`)
}
async function dismiss(item) {
  try { await clientPulseApi.dismissNotification(item.id) } catch { /* remove locally */ }
  alerts.value = alerts.value.filter(alert => alert.id !== item.id)
}
async function snooze(item) {
  try {
    await clientPulseApi.snoozeReminder(item.reminder.id, new Date(Date.now() + 3600000).toISOString())
    alerts.value = alerts.value.filter(alert => alert.id !== item.id)
  } catch { /* Keep the alert visible if snoozing fails. */ }
}
async function prime() {
  try {
    await primeReminderAudio()
    if (pendingSound && settings.value.reminder_sound_enabled) {
      pendingSound = !(await playReminderSound(
        settings.value.reminder_sound, settings.value.reminder_sound_volume,
      ))
    }
  } catch { /* The in-app alert remains available when audio is blocked. */ }
}
function visible() { if (!document.hidden) poll() }
function applySettings(event) {
  settings.value = { ...settings.value, ...event.detail }
  if (!settings.value.reminder_popup_enabled || !settings.value.reminders_enabled) alerts.value = []
  schedule()
}

watch(companyId, value => { if (value) start(); else clearInterval(timer) }, { immediate: true })
watch(() => settings.value.reminder_poll_interval_seconds, schedule)
document.addEventListener('pointerdown', prime, { once: true })
document.addEventListener('keydown', prime, { once: true })
document.addEventListener('visibilitychange', visible)
window.addEventListener('clientpulse-reminder-settings', applySettings)
onBeforeUnmount(() => {
  clearInterval(timer)
  document.removeEventListener('pointerdown', prime)
  document.removeEventListener('keydown', prime)
  document.removeEventListener('visibilitychange', visible)
  window.removeEventListener('clientpulse-reminder-settings', applySettings)
})
</script>

<template>
  <Teleport to="#ui-teleport-host">
    <aside v-if="alerts.length" class="reminder-alert-stack" aria-live="assertive" aria-label="Due reminders">
      <article v-for="item in alerts" :key="item.id" class="reminder-alert" :class="`priority-${item.reminder.priority}`">
        <header><span>ClientPulse reminder</span><button type="button" aria-label="Dismiss notification" @click="dismiss(item)">×</button></header>
        <strong>{{ item.reminder.title }}</strong>
        <p>{{ item.reminder.profile.display_name }}</p>
        <small>Due {{ reminderTime(item) }}</small>
        <div class="reminder-alert__actions">
          <button type="button" class="primary" @click="markRead(item, true)">Open client</button>
          <button v-if="canManage" type="button" @click="snooze(item)">Snooze 1h</button>
          <button type="button" @click="markRead(item)">Mark read</button>
        </div>
      </article>
    </aside>
  </Teleport>
</template>

<style scoped>
.reminder-alert-stack{position:fixed;right:22px;top:82px;z-index:12000;display:grid;width:min(390px,calc(100vw - 28px));gap:12px}.reminder-alert{overflow:hidden;padding:0 18px 16px;border:1px solid var(--ui-border,#d9e1e7);border-left:5px solid var(--ui-warning,#e5a02f);border-radius:12px;background:var(--ui-surface,#fff);box-shadow:0 18px 45px rgb(15 23 42 / 22%);color:var(--ui-text,#263238)}.reminder-alert.priority-critical{border-left-color:var(--ui-danger,#dc3545)}.reminder-alert.priority-high{border-left-color:#f97316}.reminder-alert header{display:flex;align-items:center;justify-content:space-between;margin:0 -18px 12px;padding:10px 12px 9px 16px;background:var(--ui-surface-muted,#f4f7f8)}.reminder-alert header span{font-size:.7rem;font-weight:800;letter-spacing:.1em;text-transform:uppercase}.reminder-alert header button{border:0;background:transparent;color:var(--ui-text-muted,#6b7280);font-size:1.45rem;line-height:1;cursor:pointer}.reminder-alert>strong{display:block;font-size:1rem}.reminder-alert p{margin:5px 0 2px;font-weight:600}.reminder-alert small{color:var(--ui-text-muted,#6b7280)}.reminder-alert__actions{display:flex;gap:7px;flex-wrap:wrap;margin-top:14px}.reminder-alert__actions button{padding:7px 10px;border:1px solid var(--ui-border,#d9e1e7);border-radius:7px;background:var(--ui-surface,#fff);color:inherit;font-size:.76rem;font-weight:700;cursor:pointer}.reminder-alert__actions .primary{border-color:var(--ui-primary,#16a085);background:var(--ui-primary,#16a085);color:#fff}@media(max-width:640px){.reminder-alert-stack{top:66px;right:14px}}
</style>
