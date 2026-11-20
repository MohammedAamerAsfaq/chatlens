<script setup>
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { campaignListsApi } from '@/api'
import { useAuthStore } from '@/stores/auth'

// Adds a saved contact, group or product list to a campaign. `apply(listId)` is the campaign's
// own add-list request; its response data is emitted as `applied`.
const props = defineProps({
  kind: { type: String, required: true },
  apply: { type: Function, required: true },
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
const busy = ref(false)
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
  const parts = [`${data.added} added`]
  if (data.skipped) parts.push(`${data.skipped} already in this campaign`)
  if (data.unavailable) parts.push(`${data.unavailable} unavailable (${UNAVAILABLE[props.kind]})`)
  return parts.join(' · ')
}
async function add() {
  if (!selected.value) return
  busy.value = true; error.value = ''; result.value = ''
  try {
    const { data } = await props.apply(selected.value)
    result.value = summary(data)
    emit('applied', data)
  } catch (exc) {
    error.value = message(exc, 'Unable to add the saved list.')
  } finally {
    busy.value = false
  }
}
onMounted(() => { if (canApply.value) load() })
</script>

<template>
  <div v-if="canApply" class="campaign-list-picker">
    <span class="campaign-list-picker__label">Add from saved list:</span>
    <select v-model="selected" :aria-label="`Saved ${noun} list`" :disabled="busy || !lists.length">
      <option value="">{{ lists.length ? `Choose a ${noun} list...` : `No saved ${noun} lists` }}</option>
      <option v-for="item in lists" :key="item.id" :value="item.id">{{ item.name }} ({{ item.member_count }})</option>
    </select>
    <button type="button" class="campaign-list-picker__add" :disabled="busy || !selected" @click="add">
      {{ busy ? 'Adding...' : 'Add list' }}
    </button>
    <RouterLink v-if="canManage" :to="{ name: 'campaign-lists', query: { kind } }" class="campaign-list-picker__manage">Manage lists</RouterLink>
    <span v-if="result" class="campaign-list-picker__result" role="status">{{ result }}</span>
    <span v-if="error" class="campaign-list-picker__error" role="alert">{{ error }}</span>
  </div>
</template>

<style scoped>
.campaign-list-picker{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin:8px 0}
.campaign-list-picker__label{color:var(--ui-text-muted,#64748b);font-size:.8rem}
.campaign-list-picker select{min-width:200px;max-width:100%;padding:6px 8px;border:1px solid var(--ui-border,#d0d7e2);border-radius:7px;background:var(--ui-surface,#fff);color:inherit;font:inherit;font-size:.82rem}
.campaign-list-picker__add{padding:6px 12px;border:1px solid var(--ui-primary,#2563eb);border-radius:7px;background:var(--ui-primary,#2563eb);color:var(--ui-on-primary,#fff);font-size:.8rem;font-weight:700;cursor:pointer}
.campaign-list-picker__add:disabled{opacity:.55;cursor:default}
.campaign-list-picker__manage{color:var(--ui-primary,#2563eb);font-size:.8rem;font-weight:600}
.campaign-list-picker__result{color:var(--ui-success,#15803d);font-size:.78rem;font-weight:600}
.campaign-list-picker__error{color:var(--ui-danger,#dc2626);font-size:.78rem;font-weight:600}
</style>
