<script setup>
import { computed, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import { chatsApi, clientPulseApi } from '@/api'
import { useAuthStore } from '@/stores/auth'

const props = defineProps({ chatId: { type: Number, required: true } })
const emit = defineEmits(['converted'])
const auth = useAuthStore()
const contact = ref(null)
const profile = ref(null)
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const canCreate = computed(() => auth.hasPermission('clientpulse.clients.create'))
const lifecycle = computed(() => (
  profile.value?.lifecycle_stage?.replaceAll('_', ' ') || 'client'
))

async function load() {
  const chatId = props.chatId
  contact.value = null
  profile.value = null
  error.value = ''
  loading.value = true
  try {
    const { data } = await chatsApi.info(chatId)
    if (chatId !== props.chatId) return
    contact.value = data.contact
    profile.value = data.contact?.clientpulse || null
  } catch (exc) {
    if (chatId === props.chatId) error.value = exc.response?.data?.detail || 'ClientPulse status unavailable.'
  } finally {
    if (chatId === props.chatId) loading.value = false
  }
}

async function addToClientPulse() {
  if (!contact.value?.id || saving.value) return
  saving.value = true
  error.value = ''
  try {
    const { data } = await clientPulseApi.convertConversationContact(contact.value.id, {
      lifecycle_stage: 'lead',
    })
    profile.value = data.profile
    emit('converted', data.profile)
  } catch (exc) {
    error.value = exc.response?.data?.detail || 'Unable to add this contact to ClientPulse.'
  } finally {
    saving.value = false
  }
}

watch(() => props.chatId, load, { immediate: true })
</script>

<template>
  <div v-if="!loading && contact" class="clientpulse-chat-action">
    <RouterLink
      v-if="profile"
      :to="`/clientpulse/${profile.id}`"
      class="clientpulse-chat-action__profile"
      title="Open ClientPulse profile"
    >
      <span>ClientPulse</span>
      <strong>{{ lifecycle }}</strong>
      <i>{{ profile.status || 'active' }}</i>
    </RouterLink>
    <button
      v-else-if="canCreate"
      type="button"
      class="clientpulse-chat-action__add"
      :disabled="saving"
      @click="addToClientPulse"
    >{{ saving ? 'Adding...' : 'Add to ClientPulse' }}</button>
    <span v-if="error" class="clientpulse-chat-action__error" :title="error">!</span>
  </div>
</template>

<style scoped>
.clientpulse-chat-action{display:flex;min-width:0;align-items:center;gap:6px}.clientpulse-chat-action__add,.clientpulse-chat-action__profile{min-height:32px;border:1px solid color-mix(in srgb,var(--ui-primary) 40%,var(--ui-border));border-radius:var(--ui-radius-pill);font-family:var(--ui-font-sans);font-size:.7rem;font-weight:700}.clientpulse-chat-action__add{padding:5px 11px;background:var(--ui-primary-soft);color:var(--ui-primary);cursor:pointer}.clientpulse-chat-action__add:hover{border-color:var(--ui-primary);background:var(--ui-primary);color:var(--ui-on-primary)}.clientpulse-chat-action__add:disabled{cursor:wait;opacity:.6}.clientpulse-chat-action__profile{display:flex;align-items:center;gap:6px;padding:4px 9px;background:var(--ui-success-soft);color:var(--ui-success);text-decoration:none}.clientpulse-chat-action__profile span{font-weight:800}.clientpulse-chat-action__profile strong{text-transform:capitalize}.clientpulse-chat-action__profile i{padding-left:6px;border-left:1px solid currentColor;font-size:.62rem;font-style:normal;font-weight:600;text-transform:capitalize;opacity:.75}.clientpulse-chat-action__error{display:grid;width:20px;height:20px;place-items:center;border-radius:50%;background:var(--ui-danger-soft);color:var(--ui-danger);font-size:.68rem;font-weight:800}@media(max-width:760px){.clientpulse-chat-action__profile i,.clientpulse-chat-action__profile span{display:none}.clientpulse-chat-action__add{max-width:120px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
</style>
