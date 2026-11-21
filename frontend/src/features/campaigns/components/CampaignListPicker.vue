<script setup>
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { campaignListsApi } from '@/api'
import { useAuthStore } from '@/stores/auth'

// Adds a saved contact, group or product list to a campaign. `apply(listId, { replace })` is the
// campaign's own add-list request; its response data is emitted as `applied`. Given `clear` (the
// campaign's remove-all request) the picker can also replace the campaign's items with the list
// or clear them; `count` is how many the campaign holds now, for the confirmation.
const props = defineProps({
  kind: { type: String, required: true },
  apply: { type: Function, required: true },
  clear: { type: Function, default: null },
  count: { type: Number, default: 0 },
})
const emit = defineEmits(['applied'])

const auth = useAuthStore()
const canManage = computed(() => auth.hasPermission('campaigns.audiences.manage'))
const canApply = computed(() => auth.hasPermission('campaigns.campaigns.update'))
const NOUNS = { contacts: 'contact', groups: 'group', products: 'product' }
const UNAVAILABLE = { contacts: 'not on your accounts', groups: 'no longer sendable', products: 'inactive' }
const noun = computed(() => NOUNS[props.kind])
const lists = ref([])
const selected = ref('')
const busy = ref('')
const result = ref('')
const error = ref('')

function message(exc, fallback) {
  const data = exc?.response?.data
  if (data?.detail) return data.detail
  if (data && typeof data === 'object') return Object.values(data).flat().join(' ')
  return fallback
}
async function load() {
  try {
    lists.value = (await campaignListsApi.list({ kind: props.kind })).data
  } catch (exc) {
    error.value = message(exc, 'Unable to load saved lists.')
  }
}
function summary(data) {
  const parts = []
  if (data.removed) parts.push(`${data.removed} removed`)
  parts.push(`${data.added} added`)
  if (data.skipped) parts.push(`${data.skipped} already in this campaign`)
  if (data.unavailable) parts.push(`${data.unavailable} unavailable (${UNAVAILABLE[props.kind]})`)
  return parts.join(' · ')
}
const plural = n => `${n} ${noun.value}${n === 1 ? '' : 's'}`
async function run(action, request, describe, fallback) {
  busy.value = action; error.value = ''; result.value = ''
  try {
    const { data } = await request()
    result.value = describe(data)
    emit('applied', data)
  } catch (exc) {
    error.value = message(exc, fallback)
  } finally {
    busy.value = ''
  }
}
function add() {
  if (!selected.value) return
  run('add', () => props.apply(selected.value), summary, 'Unable to add the saved list.')
}
function replace() {
  if (!selected.value) return
  const name = lists.value.find(item => item.id === selected.value)?.name || 'the saved list'
  if (props.count && !window.confirm(`Remove this campaign's ${plural(props.count)} and use only "${name}"?`)) return
  run('replace', () => props.apply(selected.value, { replace: true }), summary, 'Unable to replace with the saved list.')
}
function clearAll() {
  if (!window.confirm(`Remove all ${plural(props.count)} from this campaign?`)) return
  run('clear', () => props.clear(), data => `${data.removed} removed`, `Unable to remove the ${noun.value}s.`)
}
onMounted(() => { if (canApply.value) load() })
</script>

<template>
  <div v-if="canApply" class="campaign-list-picker">
    <span class="campaign-list-picker__label">Saved list:</span>
    <select v-model="selected" :aria-label="`Saved ${noun} list`" :disabled="!!busy || !lists.length">
      <option value="">{{ lists.length ? `Choose a ${noun} list...` : `No saved ${noun} lists` }}</option>
      <option v-for="item in lists" :key="item.id" :value="item.id">{{ item.name }} ({{ item.member_count }})</option>
    </select>
    <button type="button" class="campaign-list-picker__add" :disabled="!!busy || !selected" @click="add">
      {{ busy === 'add' ? 'Adding...' : 'Add list' }}
    </button>
    <template v-if="clear">
      <button type="button" class="campaign-list-picker__secondary" :disabled="!!busy || !selected" title="Remove the campaign's current items, then add the list" @click="replace">
        {{ busy === 'replace' ? 'Replacing...' : 'Replace with list' }}
      </button>
      <button type="button" class="campaign-list-picker__danger" :disabled="!!busy || !count" @click="clearAll">
        {{ busy === 'clear' ? 'Clearing...' : `Clear ${noun}s` }}
      </button>
    </template>
    <RouterLink v-if="canManage" :to="{ name: 'campaign-lists', query: { kind } }" class="campaign-list-picker__manage">Manage lists</RouterLink>
    <span v-if="result" class="campaign-list-picker__result" role="status">{{ result }}</span>
    <span v-if="error" class="campaign-list-picker__error" role="alert">{{ error }}</span>
  </div>
</template>

<style scoped>
.campaign-list-picker{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin:8px 0}
.campaign-list-picker__label{color:var(--ui-text-muted,#64748b);font-size:.8rem}
.campaign-list-picker select{min-width:200px;max-width:100%;padding:6px 8px;border:1px solid var(--ui-border,#d0d7e2);border-radius:7px;background:var(--ui-surface,#fff);color:inherit;font:inherit;font-size:.82rem}
.campaign-list-picker button{padding:6px 12px;border-radius:7px;font-size:.8rem;font-weight:700;cursor:pointer}
.campaign-list-picker button:disabled{opacity:.55;cursor:default}
.campaign-list-picker__add{border:1px solid var(--ui-primary,#2563eb);background:var(--ui-primary,#2563eb);color:var(--ui-on-primary,#fff)}
.campaign-list-picker__secondary{border:1px solid var(--ui-primary,#2563eb);background:var(--ui-surface,#fff);color:var(--ui-primary,#2563eb)}
.campaign-list-picker__danger{border:1px solid var(--ui-danger,#dc2626);background:var(--ui-surface,#fff);color:var(--ui-danger,#dc2626)}
.campaign-list-picker__manage{color:var(--ui-primary,#2563eb);font-size:.8rem;font-weight:600}
.campaign-list-picker__result{color:var(--ui-success,#15803d);font-size:.78rem;font-weight:600}
.campaign-list-picker__error{color:var(--ui-danger,#dc2626);font-size:.78rem;font-weight:600}
</style>
