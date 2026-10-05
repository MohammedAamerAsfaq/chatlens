<script setup>
import { computed, ref, watch } from 'vue'
import { clientPulseApi } from '@/api'
import { useAuthStore } from '@/stores/auth'

const props = defineProps({
  contactId: { type: Number, required: true },
  profile: { type: Object, default: null },
})
const emit = defineEmits(['converted'])
const auth = useAuthStore()
const stage = ref(props.profile?.lifecycle_stage || 'lead')
const busy = ref(false)
const error = ref('')
const success = ref('')

const canSave = computed(() => auth.hasPermission(
  props.profile ? 'clientpulse.clients.update' : 'clientpulse.clients.create',
))
const buttonLabel = computed(() => props.profile ? 'Update lifecycle' : 'Add to ClientPulse')

watch(() => props.profile, profile => {
  stage.value = profile?.lifecycle_stage || 'lead'
  error.value = ''
  success.value = ''
})

async function convert() {
  busy.value = true
  error.value = ''
  success.value = ''
  try {
    const { data } = await clientPulseApi.convertConversationContact(props.contactId, {
      lifecycle_stage: stage.value,
    })
    success.value = data.created ? 'ClientPulse profile created.' : (
      data.changed ? 'Lifecycle updated.' : 'ClientPulse profile is already up to date.'
    )
    emit('converted', data.profile)
  } catch (exc) {
    error.value = exc.response?.data?.detail || 'Unable to update ClientPulse.'
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <section class="clientpulse-conversion">
    <div class="clientpulse-conversion__head">
      <div>
        <strong>ClientPulse</strong>
        <span>{{ profile ? 'CRM profile linked' : 'Convert this contact into a client' }}</span>
      </div>
      <RouterLink v-if="profile" :to="`/clientpulse/${profile.id}`">Open profile</RouterLink>
    </div>
    <div v-if="canSave" class="clientpulse-conversion__form">
      <select v-model="stage" :disabled="busy" aria-label="Client lifecycle stage">
        <option value="lead">Lead</option>
        <option value="prospect">Prospect</option>
        <option value="active_customer">Active customer</option>
      </select>
      <button type="button" :disabled="busy" @click="convert">
        {{ busy ? 'Saving...' : buttonLabel }}
      </button>
    </div>
    <p v-else class="clientpulse-conversion__muted">You do not have permission to change this profile.</p>
    <p v-if="error" class="clientpulse-conversion__error">{{ error }}</p>
    <p v-if="success" class="clientpulse-conversion__success">{{ success }}</p>
  </section>
</template>

<style scoped>
.clientpulse-conversion{margin:14px;padding:13px;border:1px solid var(--ui-border);border-left:3px solid var(--ui-primary);border-radius:var(--ui-radius-md);background:var(--ui-surface)}
.clientpulse-conversion__head{display:flex;align-items:flex-start;justify-content:space-between;gap:8px}.clientpulse-conversion__head div{display:grid;gap:2px}.clientpulse-conversion__head strong{color:var(--ui-text-strong);font-size:.82rem}.clientpulse-conversion__head span,.clientpulse-conversion__muted{color:var(--ui-text-muted);font-size:.7rem}.clientpulse-conversion__head a{color:var(--ui-primary);font-size:.7rem;font-weight:700;text-decoration:none}
.clientpulse-conversion__form{display:grid;gap:7px;margin-top:10px}.clientpulse-conversion select,.clientpulse-conversion button{min-height:34px;padding:6px 8px;border:1px solid var(--ui-border-strong);border-radius:var(--ui-radius-sm);font:inherit}.clientpulse-conversion button{border-color:var(--ui-primary);background:var(--ui-primary);color:var(--ui-on-primary);font-size:.75rem;font-weight:700;cursor:pointer}.clientpulse-conversion button:disabled{cursor:not-allowed;opacity:.55}
.clientpulse-conversion__error,.clientpulse-conversion__success{margin:8px 0 0;font-size:.7rem}.clientpulse-conversion__error{color:var(--ui-danger)}.clientpulse-conversion__success{color:var(--ui-success)}
</style>
