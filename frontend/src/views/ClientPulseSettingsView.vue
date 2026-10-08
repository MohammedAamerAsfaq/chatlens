<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { clientPulseApi } from '@/api'
import UiButton from '@/components/ui/UiButton.vue'
import UiCard from '@/components/ui/UiCard.vue'
import UiFormField from '@/components/ui/UiFormField.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiSelect from '@/components/ui/UiSelect.vue'
import UiToggle from '@/components/ui/UiToggle.vue'
import { playReminderSound, primeReminderAudio } from '@/features/clientpulse/reminderSound'
import '@/assets/clientpulse.css'

const form = reactive({
  consent_mode: 'observational', reminders_enabled: true,
  reminder_popup_enabled: true, reminder_sound_enabled: true,
  reminder_sound: 'chime', reminder_sound_volume: 70,
  reminder_desktop_notifications_enabled: false,
  reminder_poll_interval_seconds: 30,
  default_timezone: 'Asia/Dubai', default_language: '',
})
const loading = ref(true), busy = ref(false), error = ref(''), success = ref('')
const browserPermission = ref('unsupported')
const sounds = [
  { value: 'chime', label: 'Three-note chime' },
  { value: 'bell', label: 'Bright bell' },
  { value: 'soft', label: 'Soft alert' },
]
const consentModes = [
  { value: 'observational', label: 'Observational' },
  { value: 'enforced', label: 'Enforced' },
]
const desktopHint = computed(() => {
  if (browserPermission.value === 'unsupported') return 'Desktop notifications are not supported by this browser.'
  if (browserPermission.value === 'insecure') return 'Desktop notifications require HTTPS or localhost. In-app alerts and sound still work.'
  if (browserPermission.value === 'granted') return 'This browser is allowed to show desktop notifications.'
  if (browserPermission.value === 'denied') return 'Permission is blocked in the browser site settings.'
  return 'Permission must be granted separately on every browser or workstation.'
})

async function load() {
  try { Object.assign(form, (await clientPulseApi.settings()).data) }
  catch (exc) { error.value = exc.response?.data?.detail || 'Unable to load settings.' }
  finally { loading.value = false }
}
async function save() {
  busy.value = true; error.value = ''; success.value = ''
  try {
    Object.assign(form, (await clientPulseApi.updateSettings(form)).data)
    window.dispatchEvent(new CustomEvent('clientpulse-reminder-settings', { detail: { ...form } }))
    success.value = 'ClientPulse reminder settings updated.'
  } catch (exc) { error.value = exc.response?.data?.detail || 'Unable to save settings.' }
  finally { busy.value = false }
}
async function testSound() {
  error.value = ''
  try {
    await primeReminderAudio()
    const played = await playReminderSound(form.reminder_sound, form.reminder_sound_volume)
    if (!played) error.value = 'The browser could not play notification audio.'
  } catch { error.value = 'The browser blocked notification audio. Interact with the page and try again.' }
}
async function requestDesktopPermission() {
  if (!window.isSecureContext || !('Notification' in window)) return
  browserPermission.value = await Notification.requestPermission()
}
onMounted(() => {
  browserPermission.value = !window.isSecureContext
    ? 'insecure'
    : ('Notification' in window ? Notification.permission : 'unsupported')
  load()
})
</script>

<template>
  <main class="cp-page reminder-settings"><div class="cp-shell">
    <header class="cp-hero"><div><p class="cp-eyebrow">Company settings</p><h1 class="cp-title">ClientPulse</h1><p class="cp-muted">Configure CRM defaults and how due reminders attract attention across the workspace.</p></div></header>
    <p v-if="error" class="cp-notice error">{{ error }}</p>
    <p v-if="success" class="cp-notice success">{{ success }}</p>
    <div v-if="loading" class="cp-empty">Loading settings...</div>
    <form v-else class="settings-grid" @submit.prevent="save">
      <UiCard title="Reminder notifications" subtitle="Controls the global in-app alert shown when a durable reminder becomes due.">
        <div class="toggle-list">
          <UiToggle v-model="form.reminders_enabled" label="Enable reminders" description="Allow scheduled reminder scans and delivery for this company." />
          <UiToggle v-model="form.reminder_popup_enabled" :disabled="!form.reminders_enabled" label="In-app alert cards" description="Show a persistent alert on any ChatLens page until it is handled." />
          <UiToggle v-model="form.reminder_sound_enabled" :disabled="!form.reminders_enabled" label="Notification sound" description="Play one alert sound when new due reminders are detected." />
          <UiToggle v-model="form.reminder_desktop_notifications_enabled" :disabled="!form.reminders_enabled" label="Desktop notifications" description="Show an operating-system notification when browser permission is granted." />
        </div>
        <div class="notification-controls">
          <UiFormField label="Sound"><UiSelect v-model="form.reminder_sound" :options="sounds" :disabled="!form.reminder_sound_enabled" /></UiFormField>
          <UiFormField label="Volume" :hint="`${form.reminder_sound_volume}%`"><input v-model.number="form.reminder_sound_volume" class="volume" type="range" min="0" max="100" step="5" :disabled="!form.reminder_sound_enabled" /></UiFormField>
          <UiFormField label="Check every" hint="10 to 300 seconds. This controls browser polling, not scheduler execution."><UiInput v-model.number="form.reminder_poll_interval_seconds" type="number" min="10" max="300" /></UiFormField>
        </div>
        <div class="test-row">
          <UiButton variant="outline" :disabled="!form.reminder_sound_enabled" @click="testSound">Test sound</UiButton>
          <UiButton v-if="!['granted','unsupported','insecure'].includes(browserPermission)" variant="outline" @click="requestDesktopPermission">Allow desktop notifications</UiButton>
          <span>{{ desktopHint }}</span>
        </div>
      </UiCard>

      <UiCard title="Client defaults" subtitle="Defaults applied to new ClientPulse records and consent checks.">
        <div class="field-grid">
          <UiFormField label="Consent policy"><UiSelect v-model="form.consent_mode" :options="consentModes" /></UiFormField>
          <UiFormField label="Default timezone"><UiInput v-model="form.default_timezone" required /></UiFormField>
          <UiFormField label="Default language"><UiInput v-model="form.default_language" placeholder="e.g. en" /></UiFormField>
        </div>
      </UiCard>

      <div class="save-row"><UiButton type="submit" variant="primary" :disabled="busy">{{ busy ? 'Saving...' : 'Save settings' }}</UiButton></div>
    </form>
  </div></main>
</template>

<style scoped>
.reminder-settings{overflow:auto;background:var(--ui-bg)}.settings-grid{display:grid;gap:16px;margin-top:18px}.toggle-list{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px;padding-bottom:20px;border-bottom:1px solid var(--ui-border)}.notification-controls,.field-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;margin-top:18px}.volume{width:100%;height:var(--ui-control-height);accent-color:var(--ui-primary)}.test-row{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-top:18px}.test-row span{color:var(--ui-text-muted);font-size:.75rem}.save-row{display:flex;justify-content:flex-end;padding-bottom:24px}@media(max-width:800px){.toggle-list,.notification-controls,.field-grid{grid-template-columns:1fr}}
</style>
