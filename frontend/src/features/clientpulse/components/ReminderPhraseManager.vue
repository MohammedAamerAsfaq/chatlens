<script setup>
import { onMounted, ref } from 'vue'
import { clientPulseApi } from '@/api'
import UiButton from '@/components/ui/UiButton.vue'
import UiCard from '@/components/ui/UiCard.vue'
import UiEmptyState from '@/components/ui/UiEmptyState.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiNotice from '@/components/ui/UiNotice.vue'

// Preset reminder actions offered in the reminder form's Action dropdown.
defineProps({ canEdit: { type: Boolean, default: false } })

const phrases = ref([])
const loading = ref(true)
const newText = ref('')
const editingId = ref(null)
const editText = ref('')
const busy = ref('')
const error = ref('')

function message(exc, fallback) {
  const data = exc.response?.data
  if (data?.detail) return data.detail
  if (data && typeof data === 'object') return Object.values(data).flat().join(' ')
  return fallback
}
async function run(key, action, fallback) {
  busy.value = key; error.value = ''
  try { await action() } catch (exc) { error.value = message(exc, fallback) }
  finally { busy.value = '' }
}
async function load() {
  try { phrases.value = (await clientPulseApi.reminderPhrases()).data }
  catch (exc) { error.value = message(exc, 'Unable to load reminder actions.') }
  finally { loading.value = false }
}
function add() {
  if (!newText.value.trim()) return
  return run('create', async () => {
    phrases.value.push((await clientPulseApi.createReminderPhrase({ text: newText.value })).data)
    newText.value = ''
  }, 'Unable to add the action.')
}
function beginEdit(phrase) { editingId.value = phrase.id; editText.value = phrase.text; error.value = '' }
function save(phrase) {
  return run(`edit-${phrase.id}`, async () => {
    Object.assign(phrase, (await clientPulseApi.updateReminderPhrase(phrase.id, { text: editText.value })).data)
    editingId.value = null
  }, 'Unable to save the action.')
}
function remove(phrase) {
  if (!confirm(`Delete the action “${phrase.text}”? Reminders already created keep their title.`)) return
  return run(`delete-${phrase.id}`, async () => {
    await clientPulseApi.deleteReminderPhrase(phrase.id)
    phrases.value = phrases.value.filter(item => item.id !== phrase.id)
  }, 'Unable to delete the action.')
}
function move(index, step) {
  const ids = phrases.value.map(item => item.id)
  ;[ids[index], ids[index + step]] = [ids[index + step], ids[index]]
  return run('order', async () => {
    phrases.value = (await clientPulseApi.reorderReminderPhrases(ids)).data
  }, 'Unable to change the order.')
}
onMounted(load)
</script>

<template>
  <UiCard title="Reminder actions" subtitle="Preset phrases offered in the Action dropdown when creating a reminder. Choosing one fills in the title.">
    <UiNotice v-if="error" tone="danger">{{ error }}</UiNotice>
    <form v-if="canEdit" class="phrase-manager__create" @submit.prevent="add">
      <UiInput v-model="newText" placeholder="e.g. Send price list" maxlength="255" />
      <UiButton type="submit" variant="primary" :disabled="busy === 'create'">{{ busy === 'create' ? 'Adding...' : 'Add action' }}</UiButton>
    </form>
    <div v-if="loading" class="phrase-manager__hint">Loading actions...</div>
    <ol v-else-if="phrases.length" class="phrase-manager__list">
      <li v-for="(phrase, index) in phrases" :key="phrase.id" class="phrase-manager__row">
        <template v-if="editingId === phrase.id">
          <UiInput v-model="editText" maxlength="255" @keyup.enter="save(phrase)" />
          <div class="phrase-manager__actions">
            <UiButton size="small" variant="primary" :disabled="busy === `edit-${phrase.id}`" @click="save(phrase)">Save</UiButton>
            <UiButton size="small" variant="outline" @click="editingId = null">Cancel</UiButton>
          </div>
        </template>
        <template v-else>
          <span class="phrase-manager__text">{{ phrase.text }}</span>
          <div v-if="canEdit" class="phrase-manager__actions">
            <UiButton size="small" variant="outline" :disabled="index === 0 || Boolean(busy)" aria-label="Move up" @click="move(index, -1)">↑</UiButton>
            <UiButton size="small" variant="outline" :disabled="index === phrases.length - 1 || Boolean(busy)" aria-label="Move down" @click="move(index, 1)">↓</UiButton>
            <UiButton size="small" variant="outline" @click="beginEdit(phrase)">Edit</UiButton>
            <UiButton size="small" variant="danger" :disabled="busy === `delete-${phrase.id}`" @click="remove(phrase)">Delete</UiButton>
          </div>
        </template>
      </li>
    </ol>
    <UiEmptyState v-else title="No reminder actions" :description="canEdit ? 'Add the first action above.' : 'An administrator can add actions here.'" />
  </UiCard>
</template>

<style scoped>
.phrase-manager__create{display:grid;grid-template-columns:minmax(200px,1fr) auto;gap:10px;margin-bottom:14px}
.phrase-manager__list{display:grid;gap:8px;margin:0;padding:0;list-style:none}
.phrase-manager__row{display:grid;grid-template-columns:minmax(0,1fr) auto;align-items:center;gap:10px;min-height:48px;padding:7px 10px;border:1px solid var(--ui-border);border-radius:var(--ui-radius-sm);background:var(--ui-surface-muted)}
.phrase-manager__text{overflow:hidden;color:var(--ui-text-strong);font-size:.82rem;font-weight:600;text-overflow:ellipsis;white-space:nowrap}
.phrase-manager__actions{display:flex;gap:6px;justify-content:flex-end}
.phrase-manager__hint{color:var(--ui-text-subtle);font-size:.75rem}
@media(max-width:620px){.phrase-manager__row{grid-template-columns:1fr}.phrase-manager__actions{justify-content:flex-start;flex-wrap:wrap}}
</style>
