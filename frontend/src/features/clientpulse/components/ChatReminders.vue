<script setup>
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import { FontAwesomeIcon } from '@fortawesome/vue-fontawesome'
import { faArrowLeft, faBell, faCalendarPlus, faCheck, faPlus } from '@fortawesome/free-solid-svg-icons'
import { clientPulseApi } from '@/api'
import { formatDateTime } from '@/utils/dateFormat'
import { useAuthStore } from '@/stores/auth'
import ReminderEditorModal from './ReminderEditorModal.vue'
import { normalizeReminderDefaults } from '../reminderDefaults.js'
import { blankReminderForm, followUpFields, reminderPayload } from '../reminderForm.js'

// Open reminders for the chat's ClientPulse client, beside the ClientPulse badge in the Inbox,
// with New reminder and Complete + follow-up (continues the reminder's thread).
const props = defineProps({
  profile: { type: Object, required: true },
  clientName: { type: String, default: '' },
})

const auth = useAuthStore()
const canManage = computed(() => auth.hasPermission('clientpulse.reminders.manage'))
const reminders = ref([])
const loaded = ref(false)
const open = ref(false)
// The panel opens rightwards from the chip, or leftwards when that would run past the window edge.
const alignRight = ref(false)
const PANEL_WIDTH = 380
const error = ref('')
const busy = ref('')
const root = ref(null)
const editorOpen = ref(false)
const editorError = ref('')
const linkedFrom = ref(null)
const owners = ref([])
const phrases = ref([])
const defaults = ref(normalizeReminderDefaults())
let referenceLoaded = false
const form = reactive(blankReminderForm({ defaults: defaults.value }))
const now = ref(Date.now())
const clients = computed(() => [{ id: props.profile.id, display_name: props.profile.display_name || props.clientName }])
const dueTime = item => new Date(item.snoozed_until || item.due_at)
const isOverdue = item => dueTime(item).getTime() < now.value
const overdueCount = computed(() => reminders.value.filter(isOverdue).length)

function message(exc, fallback) {
  const data = exc?.response?.data
  if (data?.detail) return data.detail
  if (data && typeof data === 'object') return Object.values(data).flat().join(' ')
  return fallback
}
async function load() {
  const profileId = props.profile.id
  error.value = ''
  try {
    const { data } = await clientPulseApi.reminders({ window: 'open', profile_id: profileId, page_size: 50 })
    if (profileId !== props.profile.id) return
    reminders.value = data.results
    now.value = Date.now()
  } catch (exc) {
    if (profileId === props.profile.id) error.value = message(exc, 'Unable to load reminders.')
  } finally {
    if (profileId === props.profile.id) loaded.value = true
  }
}
async function loadReference() {
  if (referenceLoaded) return
  const [options, phraseData] = await Promise.all([clientPulseApi.options(), clientPulseApi.reminderPhrases()])
  owners.value = options.data.owners
  defaults.value = normalizeReminderDefaults(options.data.reminder_defaults)
  phrases.value = phraseData.data
  referenceLoaded = true
}
async function startEditor(item = null) {
  busy.value = item ? `follow-${item.id}` : 'new'; error.value = ''
  try {
    await loadReference()
    if (item) await clientPulseApi.completeReminder(item.id)
    Object.assign(form, blankReminderForm({ defaults: defaults.value, owners: owners.value, profileId: props.profile.id }))
    if (item) Object.assign(form, followUpFields(item))
    linkedFrom.value = item ? { id: item.id, title: item.title } : null
    editorError.value = ''; editorOpen.value = true; open.value = false
    if (item) await load()
  } catch (exc) { error.value = message(exc, item ? 'Unable to complete the reminder.' : 'Unable to open the reminder form.') }
  finally { busy.value = '' }
}
async function complete(item) {
  busy.value = `complete-${item.id}`; error.value = ''
  try { await clientPulseApi.completeReminder(item.id); await load() }
  catch (exc) { error.value = message(exc, 'Unable to complete the reminder.') }
  finally { busy.value = '' }
}
async function save() {
  busy.value = 'save'; error.value = ''
  try {
    await clientPulseApi.createReminder(reminderPayload(form, { timezone: defaults.value.timezone }))
    editorOpen.value = false; linkedFrom.value = null
    await load()
  } catch (exc) { editorError.value = message(exc, 'Unable to create the reminder.') }
  finally { busy.value = '' }
}
function toggle() {
  open.value = !open.value
  if (!open.value) return
  const rect = root.value?.getBoundingClientRect()
  alignRight.value = Boolean(rect && rect.left + PANEL_WIDTH > window.innerWidth - 12)
  load()
}
function outside(event) { if (open.value && root.value && !root.value.contains(event.target)) open.value = false }
function escape(event) { if (event.key === 'Escape') open.value = false }

watch(() => props.profile.id, () => { reminders.value = []; loaded.value = false; open.value = false; load() }, { immediate: true })
document.addEventListener('pointerdown', outside)
document.addEventListener('keydown', escape)
onBeforeUnmount(() => {
  document.removeEventListener('pointerdown', outside)
  document.removeEventListener('keydown', escape)
})
</script>

<template>
  <div ref="root" class="chat-reminders">
    <button
      type="button" class="chat-reminders__chip" :class="{ 'has-overdue': overdueCount, active: open }"
      :title="`${reminders.length} open reminder${reminders.length === 1 ? '' : 's'}${overdueCount ? `, ${overdueCount} overdue` : ''}`"
      :aria-expanded="open" aria-label="Client reminders" @click="toggle"
    >
      <FontAwesomeIcon :icon="faBell" />
      <span>{{ loaded ? reminders.length : '…' }}</span>
    </button>
    <RouterLink to="/clientpulse-reminders" class="chat-reminders__chip chat-reminders__back" title="Back to the Reminders page">
      <FontAwesomeIcon :icon="faArrowLeft" /><span>Reminders</span>
    </RouterLink>
    <section v-if="open" class="chat-reminders__panel" :class="{ 'align-right': alignRight }" role="dialog" aria-label="Client reminders">
      <header>
        <strong>Open reminders</strong>
        <button v-if="canManage" type="button" class="chat-reminders__new" :disabled="busy === 'new'" @click="startEditor()">
          <FontAwesomeIcon :icon="faPlus" /> New reminder
        </button>
      </header>
      <p v-if="error" class="chat-reminders__error" role="alert">{{ error }}</p>
      <p v-if="loaded && !reminders.length" class="chat-reminders__empty">No open reminders for this client.</p>
      <ul v-else>
        <li v-for="item in reminders" :key="item.id" :class="{ overdue: isOverdue(item) }">
          <div class="chat-reminders__copy">
            <strong>{{ item.title }}</strong>
            <small>
              {{ isOverdue(item) ? 'Overdue' : item.status === 'snoozed' ? 'Snoozed until' : 'Due' }}
              {{ formatDateTime(dueTime(item)) }} · {{ item.assigned_to?.username || 'Unassigned' }}
            </small>
          </div>
          <div v-if="canManage" class="chat-reminders__actions">
            <button type="button" title="Complete" aria-label="Complete" :disabled="Boolean(busy)" @click="complete(item)"><FontAwesomeIcon :icon="faCheck" /></button>
            <button type="button" class="primary" title="Complete + follow-up" aria-label="Complete + follow-up" :disabled="Boolean(busy)" @click="startEditor(item)">
              <FontAwesomeIcon :icon="faCheck" /><FontAwesomeIcon :icon="faCalendarPlus" />
            </button>
          </div>
        </li>
      </ul>
    </section>
    <ReminderEditorModal
      :open="editorOpen" :busy="busy === 'save'" :form="form" :clients="clients" :owners="owners"
      :phrases="phrases" :linked-from="linkedFrom" :error="editorError" @close="editorOpen = false; linkedFrom = null" @submit="save"
    />
  </div>
</template>

<style scoped>
.chat-reminders{position:relative;display:flex;align-items:center;gap:6px}
.chat-reminders__back{text-decoration:none}
.chat-reminders__chip{display:inline-flex;align-items:center;gap:5px;min-height:32px;padding:4px 10px;border:1px solid var(--ui-border);border-radius:var(--ui-radius-pill);background:var(--ui-surface);color:var(--ui-text-muted);font:700 .72rem var(--ui-font-sans);cursor:pointer}
.chat-reminders__chip:hover,.chat-reminders__chip.active{border-color:var(--ui-primary);color:var(--ui-primary)}
.chat-reminders__chip.has-overdue{border-color:color-mix(in srgb,var(--ui-danger) 45%,var(--ui-border));background:var(--ui-danger-soft);color:var(--ui-danger)}
.chat-reminders__panel{position:absolute;top:calc(100% + 6px);left:0;z-index:60;width:min(380px,calc(100vw - 24px));max-height:60vh;display:flex;flex-direction:column;overflow:hidden;border:1px solid var(--ui-border);border-radius:12px;background:var(--ui-surface);box-shadow:0 18px 45px rgb(15 23 42 / 22%);color:var(--ui-text);font-family:var(--ui-font-sans)}
.chat-reminders__panel.align-right{left:auto;right:0}
.chat-reminders__panel header{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:10px 14px;border-bottom:1px solid var(--ui-border);background:var(--ui-surface-muted)}
.chat-reminders__panel header strong{font-size:.74rem;font-weight:800;letter-spacing:.08em;text-transform:uppercase}
.chat-reminders__new{display:inline-flex;align-items:center;gap:5px;padding:5px 9px;border:1px solid var(--ui-primary);border-radius:7px;background:var(--ui-primary);color:var(--ui-on-primary,#fff);font-size:.72rem;font-weight:700;cursor:pointer}
.chat-reminders__error{margin:0;padding:8px 14px;background:var(--ui-danger-soft);color:var(--ui-danger);font-size:.76rem;font-weight:600}
.chat-reminders__empty{margin:0;padding:18px 14px;color:var(--ui-text-muted);font-size:.8rem;text-align:center}
.chat-reminders__panel ul{margin:0;padding:0;list-style:none;overflow-y:auto}
.chat-reminders__panel li{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:10px 14px 10px 11px;border-bottom:1px solid var(--ui-border);border-left:3px solid var(--ui-warning,#e5a02f)}
.chat-reminders__panel li.overdue{border-left-color:var(--ui-danger)}
.chat-reminders__copy{min-width:0}
.chat-reminders__copy strong{display:block;overflow:hidden;font-size:.82rem;text-overflow:ellipsis;white-space:nowrap}
.chat-reminders__copy small{color:var(--ui-text-muted);font-size:.7rem}
.chat-reminders__panel li.overdue small{color:var(--ui-danger)}
@media(max-width:760px){.chat-reminders__back span{display:none}}
.chat-reminders__actions{display:flex;flex:none;gap:5px}
.chat-reminders__actions button{display:inline-flex;align-items:center;gap:4px;padding:5px 8px;border:1px solid var(--ui-border);border-radius:7px;background:var(--ui-surface);color:inherit;font-size:.72rem;cursor:pointer}
.chat-reminders__actions button.primary{border-color:var(--ui-primary);color:var(--ui-primary)}
.chat-reminders__actions button:disabled{opacity:.55;cursor:wait}
</style>
