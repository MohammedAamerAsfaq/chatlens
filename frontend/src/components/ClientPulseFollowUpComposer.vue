<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { accountsApi, clientPulseApi, outboundAssetsApi } from '@/api'

const props = defineProps({ client: { type: Object, required: true } })
const emit = defineEmits(['queued'])
const targetId = ref(props.client.whatsapp_contacts?.[0]?.id || '')
const text = ref(''), image = ref(null), preview = ref(''), assetId = ref(null)
const busy = ref(false), error = ref(''), feedback = ref(''), preflight = ref(null)
let attemptKey = ''

const contacts = computed(() => props.client.whatsapp_contacts || [])
const target = computed(() => contacts.value.find(item => item.id === Number(targetId.value)))
const limit = computed(() => image.value ? 1024 : 10000)
const count = computed(() => [...text.value].length)
const targetReady = computed(() => Boolean(
  target.value?.sending_enabled && target.value?.direct_sending_enabled
  && (!image.value || target.value?.image_sending_enabled)
))
const ready = computed(() => Boolean(
  target.value && (text.value.trim() || image.value) && count.value <= limit.value
  && targetReady.value && !busy.value && !props.client.do_not_contact
  && props.client.status === 'active'
))

function newKey() {
  return typeof globalThis.crypto?.randomUUID === 'function'
    ? globalThis.crypto.randomUUID()
    : `cp-${Date.now()}-${Math.random().toString(36).slice(2)}`
}
function resetAttempt() { attemptKey = '' }
function clearImage() {
  if (preview.value) URL.revokeObjectURL(preview.value)
  image.value = null; preview.value = ''; assetId.value = null; resetAttempt()
}
function selectImage(event) {
  const file = event.target.files?.[0]; event.target.value = ''
  if (!file) return
  if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type) || file.size > 10 * 1024 * 1024) {
    error.value = 'Select a JPEG, PNG, or WebP image no larger than 10 MB.'; return
  }
  clearImage(); image.value = file; preview.value = URL.createObjectURL(file)
}
function apiMessage(exc, fallback) {
  const data = exc.response?.data
  if (data?.detail) return data.detail
  if (data && typeof data === 'object') return Object.values(data).flat().join(' ')
  return fallback
}
async function queue(confirmNewChat = false) {
  if (!ready.value) return
  busy.value = true; error.value = ''; feedback.value = ''; preflight.value = null
  try {
    const check = await accountsApi.preflightMessage(target.value.account_id, target.value.wa_contact_id)
    preflight.value = check.data
    if (!check.data.allowed) throw new Error(`Preflight blocked: ${check.data.reason}`)
    if (image.value && !assetId.value) assetId.value = (await outboundAssetsApi.upload(image.value)).data.id
    if (!attemptKey) attemptKey = newKey()
    const response = await clientPulseApi.sendFollowUp(props.client.id, {
      whatsapp_contact_id: target.value.id, text: text.value.trim(),
      asset_id: assetId.value, idempotency_key: attemptKey,
      confirm_new_chat: confirmNewChat,
    })
    const result = response.data
    if (result.status === 'preflight_blocked') {
      error.value = `Sending blocked: ${result.status_reason}`; attemptKey = ''
    }
    else {
      const advisory = result.consent.mode === 'observational' && result.consent.status !== 'granted'
        ? ` Consent observed as ${result.consent.status}.` : ''
      feedback.value = `Queued as outbound #${result.id}.${advisory}`
      text.value = ''; clearImage(); attemptKey = ''; emit('queued', result)
    }
  } catch (exc) {
    if (exc.response?.status === 409 && exc.response?.data?.code === 'likely_new_chat_confirmation_required') {
      if (confirm('This may start a new WhatsApp chat and use new-chat capacity. Continue?')) {
        busy.value = false; await queue(true); return
      }
    } else {
      error.value = exc instanceof Error && !exc.response
        ? exc.message : apiMessage(exc, 'Unable to queue follow-up.')
    }
  } finally { busy.value = false }
}
watch([targetId, text], resetAttempt)
onBeforeUnmount(() => { if (preview.value) URL.revokeObjectURL(preview.value) })
</script>

<template>
  <section class="cp-panel cp-card cp-follow-up">
    <div class="cp-follow-head"><div><p class="cp-eyebrow">Manual contact</p><h2>WhatsApp follow-up</h2></div><span class="cp-badge">Outbound queue</span></div>
    <p class="cp-muted">Live preflight and every account sending restriction are checked before this message enters the durable queue.</p>
    <p v-if="client.do_not_contact" class="cp-notice error">Blocked by this client’s do-not-contact setting.</p>
    <p v-else-if="client.status !== 'active'" class="cp-notice error">Only active clients can receive a manual follow-up.</p>
    <p v-if="error" class="cp-notice error">{{ error }}</p><p v-if="feedback" class="cp-notice success">{{ feedback }}</p>
    <div v-if="contacts.length" class="cp-follow-grid">
      <label>Linked destination<select v-model="targetId" class="cp-select"><option v-for="item in contacts" :key="item.id" :value="item.id">{{ item.account_name }} · {{ item.display_name || item.phone_number }}</option></select></label>
      <div v-if="target" class="cp-target-state"><strong>{{ target.session_status }}</strong><span>{{ target.sending_enabled && target.direct_sending_enabled ? 'Direct sending enabled' : 'Direct sending disabled' }}</span><span>{{ target.is_existing_chat ? 'Existing chat' : 'Marked as new chat' }}</span></div>
      <p v-if="target && !targetReady" class="wide cp-notice error">Enable direct sending and, when attaching an image, image sending for the selected account.</p>
      <label class="wide">Message or image caption<textarea v-model="text" class="cp-textarea" rows="5" placeholder="Write a personal follow-up..." /></label>
      <div class="wide cp-character" :class="{ invalid: count > limit }"><strong>{{ count.toLocaleString() }} / {{ limit.toLocaleString() }}</strong><span>{{ image ? 'image caption' : 'text message' }}</span></div>
      <div class="wide cp-image-row"><label class="cp-button">{{ image ? 'Replace image' : 'Attach image' }}<input hidden type="file" accept="image/jpeg,image/png,image/webp" @change="selectImage" /></label><button v-if="image" type="button" class="cp-button cp-danger" @click="clearImage">Remove</button><span class="cp-muted">JPEG, PNG or WebP · maximum 10 MB</span></div>
      <div v-if="image" class="wide cp-image-preview"><img :src="preview" :alt="image.name" /><div><strong>{{ image.name }}</strong><p class="cp-muted">{{ Math.ceil(image.size / 1024).toLocaleString() }} KB</p></div></div>
      <div class="wide cp-actions"><button class="cp-button cp-primary" :disabled="!ready" @click="queue(false)">{{ busy ? 'Checking…' : 'Check and queue' }}</button></div>
    </div>
    <p v-else class="cp-empty">Link a WhatsApp contact to this client before sending a follow-up.</p>
  </section>
</template>
